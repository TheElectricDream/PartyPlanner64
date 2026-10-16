"""Assembler state, labels and symbols (port of mips-assembler state.js,
labels.js, symbols.js, errors.js, types.js and conditionals.js)."""

import re

from .._js import js_str

# AssemblerPhase
FIRST_PASS = 0
SECOND_PASS = 1


class AssemblerError(ValueError):
    """An assembly error. The message ends with the offending line."""


def throw_error(message, state):
    raise AssemblerError(js_str(message) + "\nLine: " + state.line)


class AssemblerState:
    __slots__ = (
        "buffer", "data_view", "line", "mem_pos", "out_index", "symbols", "symbols_by_value",
        "symbol_output_map", "current_label", "local_symbols", "static_symbols",
        "static_symbol_indices", "static_symbol_indices_before", "static_index_pos",
        "current_pass", "line_expressions", "evaluated_line_expressions", "if_else_stack",
        "files", "lines_to_insert",
    )

    def __init__(self, files=None, symbol_output_map=None):
        self.buffer = None
        self.data_view = None
        self.line = ""
        self.mem_pos = 0
        self.out_index = 0
        self.symbols = {}
        self.symbols_by_value = {}
        self.symbol_output_map = symbol_output_map
        self.current_label = None
        self.local_symbols = {}
        self.static_symbols = [{}]
        self.static_symbol_indices = [0]
        self.static_symbol_indices_before = {}
        # In the second pass the original shifts static_symbol_indices;
        # we move this position along instead.
        self.static_index_pos = 0
        self.current_pass = FIRST_PASS
        self.line_expressions = []
        self.evaluated_line_expressions = None
        self.if_else_stack = []
        self.files = files if files is not None else {}
        self.lines_to_insert = None


# Labels

LABEL_CHARS = "\\?\\!\\@"
LABEL_REGEX_STR = "@?@?[A-Za-z0-9_\\?\\!]+"
_label_regex = re.compile("^(" + LABEL_REGEX_STR + ")\\:")


def parse_global_label(state):
    """Parses a LABEL: expression and adds it to the symbol table.

    Examples of valid labels:
       basicLabel:    excited!Label!:    mystery?Label?:
       @@localLabel:  12345:             !?!:
    """
    results = _label_regex.match(state.line)
    if results is None:
        return False  # Not a label.
    name = results.group(1)
    if not is_local_label(name) and not is_static_label(name):
        state.current_label = name
    add_symbol(state, name, (state.mem_pos + state.out_index) & 0xFFFFFFFF)
    return name


def is_local_label(name):
    return name.startswith("@@")


def is_static_label(name):
    return name.startswith("@") and name[1:2] != "@"


# Symbols

def add_symbol(state, name, value):
    """Adds a symbol (global, static or local) to the symbol table."""
    if is_local_label(name):
        if not state.current_label:
            throw_error("Local label " + name + " (starts with @@) cannot be used before a global label",
                        state)
        add_local_symbol(state, name, value)
    elif is_static_label(name):
        add_static_label(state, name, value)
    else:
        add_global_symbol(state, name, value)


def add_global_symbol(state, name, value):
    state.symbols[name] = value
    state.symbols_by_value[js_str(value)] = name
    if state.symbol_output_map is not None:
        state.symbol_output_map[name] = state.out_index


def add_local_symbol(state, name, value):
    local_table = state.local_symbols.get(state.current_label)
    if local_table is None:
        local_table = state.local_symbols[state.current_label] = {}
    local_table[name] = value


def add_static_label(state, name, value):
    state.static_symbols[-1][name] = value


def push_static_label_state_level(state):
    if state.current_pass == FIRST_PASS:
        state.static_symbols.append({})
        prev_index = state.static_symbol_indices[-1]
        new_index = len(state.static_symbols) - 1
        state.static_symbol_indices_before[new_index] = prev_index
        state.static_symbol_indices.append(new_index)
    else:
        state.static_index_pos += 1


def pop_static_label_state_level(state):
    if state.current_pass == FIRST_PASS:
        indices = state.static_symbol_indices
        indices.append(state.static_symbol_indices_before.get(indices[-1]))
    else:
        state.static_index_pos += 1


def current_static_index(state):
    if state.current_pass == FIRST_PASS:
        return state.static_symbol_indices[-1]
    if state.static_index_pos < len(state.static_symbol_indices):
        return state.static_symbol_indices[state.static_index_pos]
    return None


def _get_current_static_symbols(state):
    index = current_static_index(state)
    if index is None or index >= len(state.static_symbols):
        raise TypeError("Cannot convert undefined or null to object")
    return state.static_symbols[index]


def get_symbol_value(state, name):
    """Retrieves a symbol by name (global, static or local). None if not found."""
    if name.startswith("@"):
        if name.startswith("@@"):
            if not state.current_label:
                throw_error("Local label " + name + " cannot be referenced in the current scope", state)
            local_table = state.local_symbols.get(state.current_label)
            if local_table is not None:
                return local_table.get(name)
            return None
        return _get_current_static_symbols(state).get(name)
    return state.symbols.get(name)


def get_symbol_by_value(state, value):
    """Retrieves a global symbol name by value, or None."""
    return state.symbols_by_value.get(js_str(value)) or None


# Conditionals (IfElseStateFlags)

class IfElseStateFlags:
    None_ = 0
    # We are within an if block, but haven't reached a part we should execute.
    AcceptingBlock = 1
    # We are executing code within an if/else block.
    ExecutingBlock = 2
    # We have already executed an if or elseif block, and are passing over
    # remaining instructions.
    NoLongerAcceptingBlock = 4
    # Flag set once a plain else directive is encountered.
    SawElse = 8


# Mask for checking current block state.
IfElseBlockStateMask = (IfElseStateFlags.AcceptingBlock | IfElseStateFlags.ExecutingBlock
                        | IfElseStateFlags.NoLongerAcceptingBlock)


def set_if_else_block_state(state, new_block_state):
    state.if_else_stack[-1] &= ~IfElseBlockStateMask
    state.if_else_stack[-1] |= new_block_state
