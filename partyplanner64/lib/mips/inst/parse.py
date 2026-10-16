"""Parses MIPS instruction text into machine code (port of mips-inst parse.js)."""

import re

from .._js import js_str, to_int32
from .bitstrings import is_binary_literal, make_bit_mask, make_bit_mask_from_string
from .immediates import get_imm_format_details, parse_immediate
from .opcodes import get_opcode_details, get_value_bit_length
from .regex import get_opcode, make_regex_for_opcode
from .regs import get_cond_bits, get_fmt_bits, get_reg_bits

_newline = re.compile(r"\r?\n")


def parse(value, intermediate=False):
    """Parses a string MIPS instruction, returning numeric machine code.

    With `intermediate`, this returns the dict of values instead, which can
    be manipulated and passed back to `parse`.

    Args:
        value: Instruction text (several lines give a list), a list of
            them, or an intermediate dict (with "op").
    Returns:
        An int (or dict), or a list of them when several values are given.
    """
    if isinstance(value, (list, tuple)):
        return [_parse(s, intermediate) for s in value]
    if isinstance(value, dict):
        return _parse(value, intermediate)
    if isinstance(value, str):
        values = [v for v in _newline.split(value) if v.strip()]
        if len(values) == 1:
            return _parse(values[0], intermediate)
        return [_parse(s, intermediate) for s in values]

    raise ValueError("Unexpected input to parse. Pass a string or array of strings.")


_line_cache = {}


def _parse(value, intermediate=False):
    if isinstance(value, str):
        if not intermediate:
            cached = _line_cache.get(value)
            if cached is not None:
                return cached

        opcode = get_opcode(value)
        if not opcode:
            raise ValueError("Could not parse opcode from %s" % value)

        opcode_obj = get_opcode_details(opcode)
        if not opcode_obj:
            raise ValueError("Opcode %s was not recognized" % opcode)

        values = _parse_values(opcode, opcode_obj, value)
        if intermediate:
            return values
        result = bits_from_format(opcode_obj["format"], values)
        if len(_line_cache) > 50000:
            _line_cache.clear()
        _line_cache[value] = result
        return result

    if isinstance(value, dict):
        opcode = get_opcode(value.get("op") or "")
        if not opcode:
            raise ValueError("Object input to parse did not contain 'op'")

        opcode_obj = get_opcode_details(opcode)
        if not opcode_obj:
            raise ValueError("Opcode %s was not recognized" % opcode)

        if intermediate:
            return value
        return bits_from_format(opcode_obj["format"], value)

    raise ValueError("Unexpected input to parse. Pass a string or array of strings.")


def _undef(v):
    return "undefined" if v is None else v


def _parse_values(opcode, opcode_obj, value):
    regex = make_regex_for_opcode(opcode, opcode_obj)
    match = regex.match(value)
    if not match:
        raise ValueError("Could not parse instruction: %s" % value)
    groups = (match.group(0),) + match.groups()

    values = {"op": opcode}

    if ".fmt" in opcode or ".cond" in opcode:
        _determine_opcode_values(groups[1], opcode, opcode_obj.get("fmts"),
                                 opcode_obj["format"], values)

    display = opcode_obj["display"]
    match_index = 2  # 0 is whole match, 1 is opcode - skip both
    for display_entry in display:
        parsed_val = groups[match_index] if match_index < len(groups) else None

        optional = display_entry.endswith("?")
        if optional:
            display_entry = display_entry.replace("?", "", 1)

        if display_entry in ("(", ")"):
            continue  # (Doesn't consume a match group.)

        if display_entry in ("rs", "rd", "rt"):
            try_reg = get_reg_bits(parsed_val)
            if try_reg is None:
                if optional:
                    match_index += 1
                    continue
                raise ValueError("Unrecognized %s register %s" % (display_entry, _undef(parsed_val)))
            values[display_entry] = try_reg
            match_index += 1
            continue

        if display_entry in ("fs", "ft", "fd", "fr"):
            v = None
            if parsed_val is not None and parsed_val.isdigit():
                v = int(parsed_val)
            if v is None:
                raise ValueError("Unrecognized %s register %s" % (display_entry, _undef(parsed_val)))
            values[display_entry] = v
            match_index += 1
            continue

        imm_details = get_imm_format_details(display_entry)
        if imm_details:
            imm_pieces = [groups[match_index], groups[match_index + 1], groups[match_index + 2]]

            if not optional or imm_pieces[2]:
                v = parse_immediate(imm_pieces, imm_details["bits"], imm_details["signed"],
                                    imm_details["shift"])
                if v is None:
                    raise ValueError("Could not parse immediate %s"
                                     % "".join(p or "" for p in imm_pieces))
                values[display_entry] = v

            match_index += 3
            continue

        raise ValueError("Unrecognized opcode display entry %s" % display_entry)

    return values


def bits_from_format(fmt_list, values):
    output = 0
    bit_offset = 0
    for piece in fmt_list:
        if isinstance(piece, list):
            bit_length = get_value_bit_length(piece[0])
            output = (output << bit_length) & 0xFFFFFFFF
            for alt in piece:
                wrote, output = _write_bits_for_piece(alt, output, values)
                if wrote:
                    break
        else:
            bit_length = get_value_bit_length(piece)
            output = (output << bit_length) & 0xFFFFFFFF
            wrote, new_output = _write_bits_for_piece(piece, output, values)
            if wrote:
                output = new_output
        bit_offset += bit_length

    if bit_offset != 32:
        raise ValueError("Incorrect number of bits written for format " + js_str(fmt_list))

    return output


def _write_bits_for_piece(piece, output, values):
    if is_binary_literal(piece):
        return True, (output | make_bit_mask_from_string(piece)) & 0xFFFFFFFF
    v = values.get(piece)
    if v is not None:
        v = to_int32(v) & make_bit_mask(get_value_bit_length(piece))
        return True, (output | v) & 0xFFFFFFFF
    return False, output


def _determine_opcode_values(given_opcode, generic_opcode, allowed_formats, fmt_list, values):
    given_pieces = given_opcode.split(".")
    generic_pieces = generic_opcode.split(".")
    if len(given_pieces) != len(generic_pieces):
        raise ValueError("Given opcode %s does not have all pieces (%s)" % (given_opcode, generic_opcode))

    for i, generic_piece in enumerate(generic_pieces):
        # (The original checks for "ftm3", so fmt3 values are never set here.)
        if generic_piece == "fmt":
            if given_pieces[i].upper() not in allowed_formats:
                raise ValueError("Format %s is not allowed for %s. Allowed values are %s"
                                 % (given_pieces[i], generic_piece, ",".join(allowed_formats)))
            values["fmt"] = get_fmt_bits(given_pieces[i])

        if generic_piece == "cond":
            values["cond"] = get_cond_bits(given_pieces[i])
