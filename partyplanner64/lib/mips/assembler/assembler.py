"""The assembler's two passes (port of mips-assembler assembler.js)."""

import re

from ..inst.parse import parse
from ...utils.dataview import DataView
from .._js import JS_WHITESPACE, js_str
from .directives import get_directive_to_run, is_conditional_directive
from .expressions import evaluate_expressions_on_current_line, parse_expressions_on_current_line
from .state import (
    SECOND_PASS, AssemblerError, AssemblerState, IfElseStateFlags, current_static_index,
    get_symbol_by_value, parse_global_label, throw_error,
)


def assemble(input, buffer=None, files=None, symbol_output_map=None, text=False):
    """Assembles the given input instructions.

    Args:
        input: Assembly text, or a list of lines.
        buffer: A bytearray to assemble into (in place); by default a new one
            is made, as large as the output.
        files: A dict of "file names" to assembly text, for `.include`.
        symbol_output_map: If a dict is passed, it is filled with symbol
            names -> their output offset in the buffer.
        text: Return the instructions as text (a list of str) instead.
    Returns:
        The bytearray (`buffer` if given), or a list of str with `text`.
    """
    lines = _normalize_input(input)
    state = AssemblerState(files, symbol_output_map)
    out_strs = []

    # First pass, calculate label positions.
    # Lines inserted by directives (macros, .include) are processed next,
    # before the remaining input.
    arr_new = []
    pending = []
    index = 0
    count = len(lines)
    while True:
        if pending:
            line = pending.pop()
        elif index < count:
            line = lines[index]
            index += 1
        else:
            break
        state.line = line
        if _should_skip_current_instruction(state):
            if line:
                arr_new.append(line)
            continue

        line = _process_labels_on_current_line(state)

        directive = get_directive_to_run(state) if line else None
        if directive:
            parse_expressions_on_current_line(state)
            directive(state)
            line = state.line  # Directive may change the line.
        elif line:
            # If !line, then only labels were on the line.
            state.out_index += 4

        if line:
            arr_new.append(line)

        if state.lines_to_insert:
            to_insert = _normalize_input(state.lines_to_insert)
            pending.extend(reversed(to_insert))
            state.lines_to_insert = None

    if buffer is None:
        buffer = bytearray(state.out_index)
    state.buffer = buffer
    data_view = state.data_view = DataView(buffer)
    state.mem_pos = 0
    state.out_index = 0
    state.current_pass = SECOND_PASS

    # Second pass, assemble!
    set_uint32 = data_view.set_uint32
    symbols_by_value = state.symbols_by_value
    for line in arr_new:
        state.line = line
        state.line_expressions = []
        state.evaluated_line_expressions = []
        if state.if_else_stack and _should_skip_current_instruction(state):
            continue

        directive = get_directive_to_run(state)
        if directive:
            evaluate_expressions_on_current_line(state)
            directive(state)
            continue

        # Start a new "area" if we hit a global symbol boundary.
        if symbols_by_value:
            global_symbol = get_symbol_by_value(state, state.mem_pos + state.out_index)
            if global_symbol is not None:
                state.current_label = global_symbol

        # Apply any built-in functions, symbols.
        line = state.line = evaluate_expressions_on_current_line(state)
        if text:
            out_strs.append(line)

        # At this point, we should be able to parse the instruction.
        try:
            inst = parse(line)
        except Exception as e:  # noqa: BLE001 (any parse error is reported for the line)
            throw_error("Error: " + str(e), state)
        set_uint32(state.out_index, inst)
        state.out_index += 4

    if state.if_else_stack:
        throw_error("An if directive was used without an endif directive", state)
    if current_static_index(state) != 0:
        throw_error("A beginfile directive was used without an endfile directive", state)

    if text:
        return out_strs
    return buffer


def _should_skip_current_instruction(state):
    """Tests if the current state deems we shouldn't execute the current line."""
    if state.if_else_stack:
        if_else_state = state.if_else_stack[-1]
        return (not (if_else_state & IfElseStateFlags.ExecutingBlock)
                and not is_conditional_directive(state.line))
    return False


def _process_labels_on_current_line(state):
    while True:
        line = state.line
        if ":" not in line:
            return line
        parsed_label = parse_global_label(state)
        if not parsed_label:
            return line
        state.line = line[len(parsed_label) + 1:].strip(JS_WHITESPACE)


_newline = re.compile(r"\r?\n")


def _normalize_input(input):
    if isinstance(input, str):
        arr = _newline.split(input)
    elif isinstance(input, (list, tuple)):
        arr = [s for s in input if isinstance(s, str)]
    else:
        raise ValueError("Input must be a string or array of strings")
    arr = _strip_comments(arr)
    return [s for s in (s.strip(JS_WHITESPACE) for s in arr) if s]


def _strip_comments(lines):
    """Strips single line ; or // comments, and /* */ block comments.

    This isn't perfect, but it does try to detect cases where the comment
    characters are within a quoted string.
    """
    within_block_comment = False
    output = []
    for line in lines:
        if within_block_comment:
            # The only thing that can break us out is the closing block comment.
            block_comment_end_index = line.find("*/")
            if block_comment_end_index >= 0:
                line = line[block_comment_end_index + 2:]
                within_block_comment = False
        if within_block_comment:
            output.append("")
            continue

        if "/" not in line and ";" not in line:
            output.append(line)
            continue

        block_comment_index = line.find("/*")
        while block_comment_index >= 0:
            if not _appears_surrounded_by_quotes(line, block_comment_index):
                block_comment_end_index = line.find("*/", block_comment_index + 2)
                if block_comment_end_index >= 0:
                    line = line[:block_comment_index] + line[block_comment_end_index + 2:]
                else:
                    line = line[:block_comment_index]
                    within_block_comment = True
                    break
            else:
                block_comment_index += 1  # Avoid infinite loop
            block_comment_index = line.find("/*", block_comment_index)

        semicolon_index = line.find(";")
        while semicolon_index >= 0:
            if not _appears_surrounded_by_quotes(line, semicolon_index):
                line = line[:semicolon_index]
                # This invalidates any block comment we found earlier this iteration.
                within_block_comment = False
                break
            semicolon_index = line.find(";", semicolon_index + 1)

        slashes_index = line.find("//")
        while slashes_index >= 0:
            if not _appears_surrounded_by_quotes(line, slashes_index):
                line = line[:slashes_index]
                # This invalidates any block comment we found earlier this iteration.
                within_block_comment = False
                break
            slashes_index = line.find("//", slashes_index + 2)

        output.append(line)

    if within_block_comment:
        raise AssemblerError("Unclosed block comment detected.")
    return output


def _appears_surrounded_by_quotes(line, position):
    return (_appears_surrounded_by_character(line, position, "\"")
            or _appears_surrounded_by_character(line, position, "'"))


def _appears_surrounded_by_character(line, position, char):
    first_char_index = line.find(char)
    if first_char_index == -1:
        return False
    if first_char_index > position:
        return False
    after_pos_char_index = line.find(char, position)
    if after_pos_char_index == -1:
        return False
    return True  # Position seems to be surrounded by character.
