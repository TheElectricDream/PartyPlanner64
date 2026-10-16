"""Expressions, immediates and built-in functions (port of mips-assembler
expressions.js, functions.js, functions/*.js and immediates.js)."""

import re

from .._js import JS_WHITESPACE, is_number, js_str, num_to_string, parse_int, to_int32, to_uint32
from .state import get_symbol_value, throw_error
from .strings import first_index_of, unescape_string

EXPR_CHARS = ",\\-A-Za-z0-9_\\s\\(\\)\\?\\!\\@"


# Immediates

def parse_immediate(value):
    """Parses a number like 10, -0x10, 0b101, o17. Returns None if not a number."""
    if not isinstance(value, str):
        return None
    negative = value[:1] == "-"
    if negative:
        value = value[1:]
    c0 = value[:1]
    c1 = value[1:2]
    if c0 == "b" or (c0 == "0" and c1 == "b"):
        result = parse_int(value[2:], 2)
    elif c0 == "o" or (c0 == "0" and c1 == "o"):
        result = parse_int(value[2:], 8)
    elif c0 == "x" or (c0 == "0" and c1 == "x"):
        result = parse_int(value[2:], 16)
    else:
        result = parse_int(value, 10)
    if result is None:
        return None
    if negative:
        result = -result if result else -0.0  # (JavaScript has a negative zero.)
    return result


def format_immediate(value):
    """Formats a numeric value for use in final assembly."""
    if value == 0:
        return "0"
    if value < 0:
        return "-0x" + num_to_string(-value, 16).upper()
    return "0x" + num_to_string(value, 16).upper()


# Built-in functions

def _abs(state, value):
    """Absolute value of the given `value`."""
    if isinstance(value, str):
        throw_error("Assembler function abs cannot be called with string \"" + value
                    + "\", value must be a number.", state)
    return abs(value)


def _hi(state, value):
    """Returns the high half of a 32-bit `value`, adjusted for sign extension
    of the low half."""
    if isinstance(value, str):
        throw_error("Assembler function hi cannot be called with string \"" + value
                    + "\", value must be a number.", state)
    lower = to_int32(value) & 0x0000FFFF
    upper = to_uint32(value) >> 16
    if lower & 0x8000:
        upper += 1
    return upper


def _lo(state, value):
    """Returns the sign-extended low half of a 32-bit `value`."""
    if isinstance(value, str):
        throw_error("Assembler function lo cannot be called with string \"" + value
                    + "\", value must be a number.", state)
    return to_int32(value) & 0x0000FFFF


def _org(state, value):
    """Current memory address."""
    return state.mem_pos + state.out_index


fns = {"abs": _abs, "hi": _hi, "lo": _lo, "org": _org}

_fn_regex = re.compile("^([\\-A-Za-z0-9_]+)\\(([\\(\\),\\-A-Za-z0-9_\\?\\!\\@]*)\\)\\Z", re.I)


def run_function(value, state):
    """Runs any built-in functions, and also resolves symbols.

    Returns a number, a string, or None when the value could not be evaluated.
    """
    if "(" not in value:
        results = None
    else:
        results = _fn_regex.match(value)
    if results is None:  # Not a function
        # Symbol?
        symbol_value = get_symbol_value(state, value)
        if symbol_value is not None:
            return symbol_value

        # Number?
        imm = parse_immediate(value)
        if imm is not None:
            return imm

        # String?
        s = unescape_string(value)
        if isinstance(s, str):
            return s

        return None

    fn = results.group(1)
    if fn not in fns:
        # Did a symbol label accidentally look like a function?
        symbol_value = get_symbol_value(state, fn)
        if symbol_value is not None:
            return symbol_value
        return None  # Might have been something like 0x10(V0)

    # Parse args slightly different than the regex suggests,
    # to support lo(label)(V0)
    fn_args = ""
    paren_level = 0
    i = len(fn) + 1
    end = len(value) - 1
    while i < end:
        ch = value[i]
        if ch == "(":
            paren_level += 1
        elif ch == ")":
            paren_level -= 1
            if paren_level < 0:
                i += 1
                break
        fn_args += ch
        i += 1

    extra_str = ""
    if i < len(value) - 1:
        # There was extra content after the end of the function,
        # like the (VO) of lo(label)(V0)
        extra_str = value[i:]

    # TODO: Doesn't support nested calls, multiple arguments.
    arg = 0
    if fn_args:
        arg = run_function(fn_args, state)
    if arg is None:
        throw_error("Could not evaluate " + fn_args, state)

    result = fns[fn](state, arg)
    if extra_str:
        result = js_str(result) + extra_str
    return result


# Expressions

def parse_expressions_on_current_line(state):
    line = state.line
    first_whitespace_index = first_index_of(line, " ", "\t")
    if first_whitespace_index == -1:
        state.line_expressions = []
        return  # Must not have any arguments, there would need to be whitespace for those.
    exprs = []
    split_expression_list(line[first_whitespace_index + 1:], exprs, state)
    state.line_expressions = exprs


def evaluate_expressions_on_current_line(state):
    line = state.line
    first_whitespace_index = first_index_of(line, " ", "\t")
    if first_whitespace_index == -1:
        return line  # Must not have any arguments, there would need to be whitespace for those.

    first_piece = line[:first_whitespace_index]
    exprs = []
    split_expression_list(line[first_whitespace_index + 1:], exprs, state)
    state.line_expressions = exprs

    if exprs:
        evaluated_exprs = []
        last = len(exprs) - 1
        for i, expr in enumerate(exprs):
            evaluated = run_function(expr, state)
            # For the last piece, do extra logic to fix branch values.
            if i == last and is_number(evaluated):
                evaluated = _fix_branch(first_piece, evaluated, state)
            evaluated_exprs.append(evaluated)
        state.evaluated_line_expressions = evaluated_exprs
        formatted = []
        for value, original in zip(evaluated_exprs, exprs):
            if value is None:
                formatted.append(original)
            elif is_number(value):
                formatted.append(format_immediate(value))
            else:
                formatted.append(value)
        line = first_piece + " " + " ".join(formatted)
    return line


_BRANCHES = frozenset((
    "bc1f", "bc1fl", "bc1t", "bc1tl", "beq", "beql", "bgez", "bgezal", "bgezall", "bgezl",
    "bgtz", "bgtzl", "blez", "blezl", "bltz", "bltzal", "bltzall", "bltzl", "bne", "bnel",
))


def _fix_branch(inst, offset, state):
    """Transforms branches from absolute to relative."""
    if inst.lower() in _BRANCHES:
        mem_offset = state.mem_pos + state.out_index
        offset_diff = offset - mem_offset
        if offset_diff % 4 != 0:
            throw_error("Misaligned branch instruction detected", state)
        if isinstance(offset_diff, int):
            return offset_diff // 4 - 1
        diff = offset_diff / 4 - 1
        return int(diff) if diff.is_integer() else diff
    return offset  # Leave as is.


_SPLITTERS = (",", " ", "\t")
_simple_split = re.compile("[, \t]+")


def split_expression_list(s, pieces, state):
    if "\"" not in s and "'" not in s and "(" not in s and ")" not in s:
        # Fast path, equivalent to the loop below when there are no strings
        # or groupings: pieces are separated by runs of commas/spaces/tabs.
        for piece in _simple_split.split(s):
            piece = piece.strip(JS_WHITESPACE)
            if piece:
                _end_piece(piece, pieces, state)
        return pieces

    current_piece = []
    current_str_quote_char = ""  # When set, we're writing a string
    current_paren_level = 0  # When > 0, we're inside a parenthesis grouper
    escaped = False
    prev_char = ""

    for ch in s:
        # End the piece if applicable.
        if (not current_str_quote_char and not current_paren_level
                and prev_char in _SPLITTERS):
            piece = "".join(current_piece).rstrip(", \t").strip(JS_WHITESPACE)
            # We actually have only seen white spaces, so don't create a separate piece yet.
            if piece:
                _end_piece(piece, pieces, state)
            current_piece = []

        if ch == "(":
            if not escaped and not current_str_quote_char:
                current_paren_level += 1
        elif ch == ")":
            if not escaped and not current_str_quote_char:
                if current_paren_level <= 0:
                    throw_error("Imbalanced parenthesis in expression: " + s, state)
                current_paren_level -= 1
        elif ch == "\"" or ch == "'":
            if not escaped:
                if current_str_quote_char:
                    if current_str_quote_char == ch:  # Ending string
                        current_str_quote_char = ""
                    # Else just writing a quote inside, ex: "assembler's"
                else:  # Beginning string
                    current_str_quote_char = ch

        current_piece.append(ch)
        escaped = not escaped and ch == "\\"
        prev_char = ch

    if current_paren_level > 0:
        throw_error("Imbalanced parenthesis in expression: " + s, state)
    if current_str_quote_char:
        throw_error("Unterminated string: " + "".join(current_piece), state)

    piece = "".join(current_piece).rstrip(", \t").strip(JS_WHITESPACE)
    if piece:
        _end_piece(piece, pieces, state)
    return pieces


def _end_piece(piece, pieces, state):
    # If this piece directly evaluates to an equ replacement symbol,
    # then handle the replacement here.
    # This is what makes equ work, in a limited capacity.
    sym_value = get_symbol_value(state, piece)
    if isinstance(sym_value, str):
        split_expression_list(sym_value, pieces, state)
    else:
        pieces.append(piece)
