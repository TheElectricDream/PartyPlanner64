"""Regular expressions for parsing instructions (port of mips-inst regex.js).

JavaScript's \\w is ASCII-only, so it is spelled out as [A-Za-z0-9_] here.
"""

import re

from .immediates import get_imm_format_details
from .regs import is_cond_string, is_fmt_string

op_regex = "([A-Za-z0-3.]+)"
imm_regex = "(-)?0?([xbo]?)([A-Fa-f0-9]+)"
reg_regex = "\\$?([A-Za-z0-9_]+)"
float_reg_regex = "\\$?[Ff]([0-9]+)"

_opcode_regex = re.compile("^\\s*" + op_regex)

_regex_cache = {}
_opcode_cache = {}


def get_opcode(s):
    """Gets the op string from a given entire instruction.

    This is a general form (.fmt rather than .S, .D, etc.)
    """
    match = _opcode_regex.match(s)
    if match:
        whole = match.group(1)
        try:
            return _opcode_cache[whole]
        except KeyError:
            pass
        pieces = whole.split(".")  # Could be .fmt, .cond.fmt, etc
        if len(pieces) == 1:
            result = pieces[0].lower()
        else:
            # Loop from the end, as the end has the .fmt for tricky things like .D.W
            result = ""
            found_fmt = False
            found_cond = False
            for i in range(len(pieces) - 1, 0, -1):
                piece = pieces[i]
                if not found_fmt:
                    if piece == "fmt" or is_fmt_string(piece):
                        found_fmt = True
                        piece = "fmt"
                if not found_cond:
                    if is_cond_string(piece):
                        found_cond = True
                        piece = "cond"
                result = "." + piece + result
            result = (pieces[0] + result).lower()
        if len(_opcode_cache) < 4096:
            _opcode_cache[whole] = result
        return result
    return None


def make_regex_for_opcode(opcode, opcode_obj):
    try:
        return _regex_cache[opcode]
    except KeyError:
        pass

    parts = [op_regex]
    display = opcode_obj["display"]
    i = 0
    while i < len(display):
        part = display[i]
        optional = part.endswith("?")

        regex_part = ""
        if optional:
            regex_part += "(?:[,\\s]+"

        if i + 1 < len(display) and display[i + 1] == "(":
            if optional:
                raise ValueError("Not prepared to generate optional regex with parenthesis")
            if i + 3 >= len(display) or display[i + 3] != ")":
                raise ValueError("Not prepared to generate regex for multiple values in parenthesis")
            regex_part += _make_parenthesis_regex(_get_regex_for_part(part),
                                                  _get_regex_for_part(display[i + 2]))
            i = i + 3
        else:
            regex_part += _get_regex_for_part(part)

        if optional:
            regex_part += ")?"

        parts.append(regex_part)
        i += 1

    regex_str = "^\\s*"
    for index, nxt in enumerate(parts):
        if index == 0 or _part_is_optional(nxt):
            regex_str += nxt
        else:
            regex_str += "[,\\s]+" + nxt
    regex_str += "\\s*\\Z"

    regex = re.compile(regex_str)
    _regex_cache[opcode] = regex
    return regex


def _get_regex_for_part(part):
    if is_reg(part):
        return reg_regex
    if is_float_reg(part):
        return float_reg_regex
    if get_imm_format_details(part):
        return imm_regex
    raise ValueError("Unrecognized display entry %s" % part)


def _make_parenthesis_regex(regex1, regex2):
    return regex1 + "\\s*" + "\\(?" + regex2 + "\\)?"


def _part_is_optional(part_str):
    return part_str.startswith("(?:")


def is_reg(entry):
    if not entry:
        return False
    return entry[:2] in ("rs", "rt", "rd")


def is_float_reg(entry):
    if not entry:
        return False
    return entry[:2] in ("fs", "ft", "fd")
