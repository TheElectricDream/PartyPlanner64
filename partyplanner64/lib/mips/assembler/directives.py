"""Directives and macros (port of mips-assembler directives.js,
directives/*.js and macros/*.js)."""

import re
import struct

from .._js import is_number, js_str, to_int32, to_uint32
from .state import (
    FIRST_PASS, SECOND_PASS, IfElseBlockStateMask, IfElseStateFlags, LABEL_CHARS,
    LABEL_REGEX_STR, add_symbol, pop_static_label_state_level, push_static_label_state_level,
    set_if_else_block_state, throw_error,
)
from .expressions import run_function


def _basic_directive_regex(directive_alias, no_args=False):
    return re.compile("^\\." + directive_alias + ("" if no_args else "\\s+"), re.I)


# General directives

def definelabel(state):
    """.definelabel adds a new symbol."""
    if len(state.line_expressions) != 2:
        throw_error(".definelabel must have two arguments, a label name and value", state)
    name = state.line_expressions[0]
    value = run_function(state.line_expressions[1], state)
    if not is_number(value):
        throw_error("The value in .definelabel must evaluate to a numeric value", state)
    add_symbol(state, name, value)
    return True  # Symbol added


_define_label_regex = re.compile(
    "^\\.definelabel\\s+(" + LABEL_REGEX_STR + ")[\\s,]+([\\-A-Za-z0-9_" + LABEL_CHARS + "]+)\\Z",
    re.I)

_equ_regex = re.compile("^\\s*(" + LABEL_REGEX_STR + ")\\s+equ(?:\\Z|(?:\\s+(.+)\\Z))", re.I)


def equ(state):
    """`equ` is used for direct text replacement."""
    match = _equ_regex.match(state.line)
    if not match:
        throw_error("equ directive was not able to be parsed", state)
    # lineExpressions only has ["equ", value] and might split the value, so use regex.
    name = match.group(1)
    value = match.group(2) or ""
    add_symbol(state, name, value)
    return True  # Symbol added


def org(state):
    """.org changes the effective memory position."""
    if len(state.line_expressions) != 1:
        throw_error(".org directive requires one numeric argument", state)
    imm = run_function(state.line_expressions[0], state)
    if not is_number(imm):
        throw_error("Could not parse .org immediate " + js_str(imm), state)
    if imm < 0:
        throw_error(".org directive cannot be negative", state)
    state.mem_pos = to_uint32(imm)  # Better be 32-bit
    return True


def orga(state):
    """.orga updates the current output buffer index."""
    if len(state.line_expressions) != 1:
        throw_error(".orga directive requires one numeric argument", state)
    imm = run_function(state.line_expressions[0], state)
    if not is_number(imm):
        throw_error("Could not parse .orga immediate " + js_str(imm), state)
    if imm < 0:
        throw_error(".orga directive cannot be negative.", state)
    state.out_index = to_uint32(imm)  # Better be 32-bit
    return True


def align(state):
    """.align pads zeroes until the output position is aligned with the
    specified alignment."""
    if len(state.line_expressions) != 1:
        throw_error(".align requires one power of two number argument", state)
    imm = run_function(state.line_expressions[0], state)
    if imm is None:
        throw_error("Could not parse .align immediate " + js_str(state.line_expressions), state)
    if not is_number(imm):
        throw_error(".align requires one power of two number argument", state)
    if imm % 2:
        throw_error(".align directive requires a power of two.", state)
    if imm < 0:
        throw_error(".align directive cannot align by a negative value.", state)
    if imm == 0:
        return True  # (x % 0 is NaN in JavaScript, so nothing is padded.)
    while state.out_index % imm:
        if state.current_pass == SECOND_PASS:
            state.data_view.set_uint8(state.out_index, 0)
        state.out_index += 1
    return True


def skip(state):
    """.skip passes over a given amount of bytes without overwriting them."""
    if len(state.line_expressions) != 1:
        throw_error(".skip directive requires one numeric argument", state)
    imm = run_function(state.line_expressions[0], state)
    if not is_number(imm):
        throw_error("Could not parse .skip immediate " + js_str(imm), state)
    if imm < 0:
        throw_error(".skip directive cannot skip a negative length.", state)
    state.out_index += imm
    return True


def fill(state):
    """.fill length[,value]"""
    if not state.line_expressions or len(state.line_expressions) > 2:
        throw_error(".fill directive takes a length and optional value", state)
    length = run_function(state.line_expressions[0], state)
    if not is_number(length):
        throw_error("Could not parse .fill length " + state.line_expressions[0], state)
    if length < 0:
        throw_error(".fill length must be positive.", state)
    if len(state.line_expressions) > 1:
        value = run_function(state.line_expressions[1], state)
        if not is_number(value):
            throw_error("Could not parse .fill value " + state.line_expressions[1], state)
    else:
        value = 0
    if state.current_pass == SECOND_PASS:
        count = int(-(-length // 1))
        if count > 0:
            dv = state.data_view
            if state.out_index < 0 or state.out_index + count > dv.byte_length:
                for i in range(count):
                    dv.set_int8(state.out_index + i, value)
            else:
                start = dv.byte_offset + state.out_index
                dv.buffer[start:start + count] = bytes([to_int32(value) & 0xFF]) * count
    state.out_index += length
    return True


# Text and data directives

def ascii(state, append_zero=False):
    """Writes ascii bytes.

    .ascii value[,...]
    .asciiz value[,...]

    `value` can either be a string or byte value.
    """
    numbers = []
    for expr in state.line_expressions:
        value = run_function(expr, state)
        if value is None:
            throw_error("Could not parse .ascii value " + expr, state)
        if is_number(value):
            numbers.append(value)
        elif isinstance(value, str):
            # (charCodeAt gives UTF-16 code units.)
            if value.isascii():
                numbers.extend(value.encode("ascii"))
            else:
                data = value.encode("utf-16-be", "surrogatepass")
                numbers.extend((data[i] << 8) | data[i + 1] for i in range(0, len(data), 2))
    if append_zero:
        numbers.append(0)  # Add NULL byte.
    if state.current_pass == SECOND_PASS:
        dv = state.data_view
        for i, n in enumerate(numbers):
            if n < 0:
                dv.set_int8(state.out_index + i, n)
            else:
                dv.set_uint8(state.out_index + i, n)
    state.out_index += len(numbers)
    return True


def asciiz(state):
    """Writes ascii bytes with a trailing zero."""
    return ascii(state, True)


def byte(state):
    """.byte value[,...]  /  .db value[,...]"""
    if state.current_pass == SECOND_PASS:
        numbers = state.evaluated_line_expressions
        if not numbers:
            throw_error(".byte directive requires arguments", state)
        dv = state.data_view
        for i, num in enumerate(numbers):
            if not is_number(num):
                throw_error(".byte directive requires numeric arguments, saw: " + js_str(num), state)
            if num < 0:
                dv.set_int8(state.out_index + i, num)
            else:
                dv.set_uint8(state.out_index + i, num)
    state.out_index += len(state.line_expressions)
    return True


def halfword(state):
    """Writes 16-bit values.  .halfword value[,...]  /  .dh value[,...]"""
    if state.current_pass == SECOND_PASS:
        numbers = state.evaluated_line_expressions
        if not numbers:
            throw_error(".halfword directive requires arguments", state)
        dv = state.data_view
        for i, num in enumerate(numbers):
            if not is_number(num):
                throw_error(".halfword directive requires numeric arguments, saw: " + js_str(num),
                            state)
            if num < 0:
                dv.set_int16(state.out_index + (i * 2), num)
            else:
                dv.set_uint16(state.out_index + (i * 2), num)
    state.out_index += 2 * len(state.line_expressions)
    return True


def word(state):
    """Writes 32-bit values.  .word value[,...]  /  .dw value[,...]"""
    if state.current_pass == SECOND_PASS:
        numbers = state.evaluated_line_expressions
        if not numbers:
            throw_error(".word directive requires arguments", state)
        dv = state.data_view
        for i, num in enumerate(numbers):
            if not is_number(num):
                throw_error(".word directive requires numeric arguments, saw: " + js_str(num), state)
            if num < 0:
                dv.set_int32(state.out_index + (i * 4), num)
            else:
                dv.set_uint32(state.out_index + (i * 4), num)
    state.out_index += 4 * len(state.line_expressions)
    return True


def _float32_bytes(value):
    try:
        return struct.pack(">f", value)
    except OverflowError:
        return struct.pack(">f", float("inf") if value > 0 else float("-inf"))


def float_(state):
    """Writes 32-bit float values.  .float value[,...]"""
    if state.current_pass == SECOND_PASS:
        numbers = state.evaluated_line_expressions
        if not numbers:
            throw_error(".float directive requires arguments", state)
        if any(not is_number(v) for v in numbers):
            throw_error(".float directive requires numeric arguments", state)
        dv = state.data_view
        for i, num in enumerate(numbers):
            offset = state.out_index + (i * 4)
            if offset < 0 or offset + 4 > dv.byte_length:
                dv.set_float32(offset, num)  # Raises the range error.
            start = dv.byte_offset + offset
            dv.buffer[start:start + 4] = _float32_bytes(float(num))
    state.out_index += 4 * len(state.line_expressions)
    return True


# Conditional directives

def ifcond(state):
    """.if cond  (`cond` is met if it evaluates to a non-zero integer.)"""
    if not state.line_expressions:
        throw_error("A condition must be passed to an if directive", state)
    if len(state.line_expressions) > 1:
        throw_error("Only a single condition can be passed to an if directive", state)
    value = run_function(state.line_expressions[0], state)
    if value is None:
        throw_error("Could not parse .if condition", state)
    if not is_number(value):
        throw_error("Condition of if directive must evaluate to a numeric value, saw: " + value,
                    state)
    if value:
        state.if_else_stack.append(IfElseStateFlags.ExecutingBlock)
    else:
        state.if_else_stack.append(IfElseStateFlags.AcceptingBlock)
    return True


def elseif(state):
    """.elseif cond"""
    if not state.line_expressions:
        throw_error("A condition must be passed to an elseif directive", state)
    if len(state.line_expressions) > 1:
        throw_error("Only a single condition can be passed to an elseif directive", state)
    if not state.if_else_stack:
        throw_error("An elseif directive was reached, but there was no previous if directive", state)
    cur_state = state.if_else_stack[-1]
    if cur_state & IfElseStateFlags.SawElse:
        throw_error("Encountered an elseif after seeing an else directive", state)
    value = run_function(state.line_expressions[0], state)
    if value is None:
        throw_error("Could not parse .elseif condition", state)
    if not is_number(value):
        throw_error("Condition of elseif directive must evaluate to a numeric value, saw: " + value,
                    state)
    block_state = cur_state & IfElseBlockStateMask
    if block_state == IfElseStateFlags.AcceptingBlock:
        if value:
            set_if_else_block_state(state, IfElseStateFlags.ExecutingBlock)
    elif block_state == IfElseStateFlags.ExecutingBlock:
        set_if_else_block_state(state, IfElseStateFlags.NoLongerAcceptingBlock)
    elif block_state == IfElseStateFlags.NoLongerAcceptingBlock:
        pass
    else:
        throw_error("Unexpected conditional block state: " + format(cur_state, "x"), state)
    return True


def elseblock(state):
    """.else"""
    if state.line_expressions:
        throw_error("The else directive cannot take a condition or parameters", state)
    if not state.if_else_stack:
        throw_error("An else directive was reached, but there was no previous if directive", state)
    cur_state = state.if_else_stack[-1]
    if cur_state & IfElseStateFlags.SawElse:
        throw_error("Encountered another else directive, but an else directive was already passed",
                    state)
    block_state = cur_state & IfElseBlockStateMask
    if block_state == IfElseStateFlags.AcceptingBlock:
        set_if_else_block_state(state, IfElseStateFlags.ExecutingBlock)
    elif block_state == IfElseStateFlags.ExecutingBlock:
        set_if_else_block_state(state, IfElseStateFlags.NoLongerAcceptingBlock)
    elif block_state == IfElseStateFlags.NoLongerAcceptingBlock:
        pass
    else:
        throw_error("Unexpected conditional block state: " + format(cur_state, "x"), state)
    state.if_else_stack[-1] |= IfElseStateFlags.SawElse
    return True


def endif(state):
    """.endif  Ends the last open if or else block."""
    if state.line_expressions:
        throw_error("The endif directive cannot take a condition or parameters", state)
    if not state.if_else_stack:
        throw_error("An endif directive was reached, but there was no previous if directive", state)
    state.if_else_stack.pop()
    return True


# Files

def include(state):
    """.include FileName  (`FileName` is a key in the `files` passed to `assemble`.)"""
    if not state.line_expressions:
        throw_error("A file name must be passed to an include directive", state)
    if len(state.line_expressions) > 1:
        throw_error("Only a single file name can be passed to an include directive", state)
    filename = run_function(state.line_expressions[0], state)
    if filename is None:
        throw_error("Could not parse .include file name", state)
    if not isinstance(filename, str):
        throw_error("File name of include directive must evaluate to a string, saw: "
                    + js_str(filename), state)
    file = state.files.get(filename)
    if not isinstance(file, str):
        throw_error("The " + filename + " file was not a string", state)
    if state.current_pass != FIRST_PASS:
        throw_error("The `include` directive shouldn't be present after the first assembly phase",
                    state)
    state.lines_to_insert = ".beginfile\n" + file + "\n.endfile"
    state.line = ""  # Delete this directive.


def beginfile(state):
    """.beginfile"""
    if state.line_expressions:
        throw_error("The beginfile directive takes no arguments", state)
    push_static_label_state_level(state)
    return True


def endfile(state):
    """.endfile"""
    if state.line_expressions:
        throw_error("The endfile directive takes no arguments", state)
    pop_static_label_state_level(state)
    return True


# Macros ("pseudo-instructions")

def _check_macro_pass(state, name):
    if state.current_pass != FIRST_PASS:
        throw_error("The `" + name + "` macro shouldn't be present after the first assembly phase",
                    state)


def beqz(state):
    """beqz reg,dest"""
    _check_macro_pass(state, "beqz")
    if len(state.line_expressions) != 2:
        throw_error("The `beqz` macro must take a register and label", state)
    state.line = ""  # Delete this line.
    state.lines_to_insert = "BEQ " + state.line_expressions[0] + " R0 " + state.line_expressions[1]


def bnez(state):
    """bnez reg,dest"""
    _check_macro_pass(state, "bnez")
    if len(state.line_expressions) != 2:
        throw_error("The `bnez` macro must take a register and label", state)
    state.line = ""  # Delete this line.
    state.lines_to_insert = "BNE " + state.line_expressions[0] + " R0 " + state.line_expressions[1]


def bnezl(state):
    """bnezl reg,dest"""
    _check_macro_pass(state, "bnezl")
    if len(state.line_expressions) != 2:
        throw_error("The `bnezl` macro must take a register and label", state)
    state.line = ""  # Delete this line.
    state.lines_to_insert = "BNEL " + state.line_expressions[0] + " R0 " + state.line_expressions[1]


def li(state):
    """li dest,value"""
    _check_macro_pass(state, "li")
    if len(state.line_expressions) <= 1:
        throw_error("The `li` macro must take a register and immediate", state)
    dest = state.line_expressions[0]
    value = run_function(state.line_expressions[1], state)
    if value is None:
        # Most likely a label is not yet defined in the first pass.
        # We can try to salvage this situation with "worst case" handling.
        state.line = ""  # Delete this line.
        state.lines_to_insert = ("LUI " + dest + ", hi(" + state.line_expressions[1] + ")\nADDIU "
                                 + dest + ", " + dest + ", lo(" + state.line_expressions[1] + ")")
        return
    if not is_number(value):
        throw_error("Immediate value of `li` macro must evaluate to a number, saw: " + value, state)
    state.line = ""  # Delete this line.
    if -32768 <= value <= 32767:
        state.lines_to_insert = "ADDIU " + dest + ", R0, " + js_str(value)
    elif 0 < value <= 65535:
        state.lines_to_insert = "ORI " + dest + ", R0, " + js_str(value)
    elif (to_int32(value) & 0xFFFF) == 0:
        state.lines_to_insert = "LUI " + dest + ", " + js_str(to_int32(value) >> 16)
    elif -0xFFFFFFFF <= value <= 0xFFFEFFFF:
        needs_sign_adjust = (to_int32(value) & 0x8000) != 0
        state.lines_to_insert = ("LUI " + dest + ", "
                                 + js_str((to_uint32(value) >> 16) + (1 if needs_sign_adjust else 0))
                                 + "\nADDIU " + dest + ", " + dest + ", "
                                 + js_str(to_int32(value) & 0xFFFF))
    else:
        throw_error("li immediate value " + js_str(value) + " seems out of range", state)


def move(state):
    """move dest,reg"""
    _check_macro_pass(state, "move")
    if len(state.line_expressions) != 2:
        throw_error("The `move` macro must take two registers", state)
    state.line = ""  # Delete this line.
    state.lines_to_insert = "ADDU " + state.line_expressions[0] + " " + state.line_expressions[1] + " R0"


# Lines starting with "." can only be one of these; the order is the original's.
_dot_directives = [
    (_define_label_regex, definelabel),
    (_basic_directive_regex("org"), org),
    (_basic_directive_regex("orga"), orga),
    (_basic_directive_regex("align"), align),
    (_basic_directive_regex("skip"), skip),
    (_basic_directive_regex("fill"), fill),
    (_basic_directive_regex("ascii"), ascii),
    (_basic_directive_regex("asciiz"), asciiz),
    (_basic_directive_regex("byte"), byte),
    (_basic_directive_regex("db"), byte),
    (_basic_directive_regex("halfword"), halfword),
    (_basic_directive_regex("dh"), halfword),
    (_basic_directive_regex("word"), word),
    (_basic_directive_regex("dw"), word),
    (_basic_directive_regex("float"), float_),
    (_basic_directive_regex("if"), ifcond),
    (_basic_directive_regex("elseif"), elseif),
    (_basic_directive_regex("else", True), elseblock),
    (_basic_directive_regex("endif", True), endif),
    (_basic_directive_regex("include"), include),
    (_basic_directive_regex("beginfile", True), beginfile),
    (_basic_directive_regex("endfile", True), endfile),
]

_macro_regex = re.compile("^(beqz|bnezl|bnez|li|move)\\s+", re.I)
_macros = {"beqz": beqz, "bnez": bnez, "bnezl": bnezl, "li": li, "move": move}


def get_directive_to_run(state):
    """Returns a directive (or macro) function to run for the current line, or None."""
    line = state.line
    if line[:1] == ".":
        for regex, directive in _dot_directives:
            if regex.match(line):
                return directive
        return None
    if "equ" in line or "EQU" in line.upper():
        if _equ_regex.match(line):
            return equ
    match = _macro_regex.match(line)
    if match:
        return _macros[match.group(1).lower()]
    return None


def is_conditional_directive(line):
    """Tests if a line represents a conditional block directive."""
    normalized = line[:6].lower()
    return (normalized.startswith(".if") or normalized.startswith(".else")
            or normalized.startswith(".endif"))
