"""Prints MIPS machine code as text (port of mips-inst print.js)."""

from .._js import is_number, num_to_string, to_int32
from ...utils.dataview import DataView
from .bitstrings import is_binary_literal, make_bit_mask, pad_bit_string
from .immediates import get_imm_format_details, make_int16
from .opcodes import find_match, get_opcode_details, get_value_bit_length
from .regs import get_cond_name, get_float_reg_name, get_fmt3_name, get_fmt_name, get_reg_name


def print(inst, commas=False, include_dollar=False, casing="toUpperCase", num_base=16,
          intermediate=False):
    """Prints a string representation of a MIPS instruction.

    With `intermediate`, this returns the dict of values instead, which can
    be manipulated and passed back to `print`.

    Args:
        inst: An instruction (int), an intermediate dict, a list of either,
            or bytes/bytearray/memoryview/DataView of big-endian words.
        commas: Separate values by commas.
        include_dollar: Prefix registers with a dollar sign.
        casing: "toUpperCase" (default) or "toLowerCase".
        num_base: Number format: 16 (hex, default), 10, 8 or 2.
    Returns:
        A str (or dict), or a list of them when several values are given.
    """
    opts = (casing, commas, include_dollar, intermediate, num_base)

    if isinstance(inst, (list, tuple)):
        return [_print(i, opts) for i in inst]

    if isinstance(inst, (bytes, bytearray, memoryview, DataView)):
        data_view = inst if isinstance(inst, DataView) else DataView(
            bytes(inst) if isinstance(inst, memoryview) else inst)
        return [_print(data_view.get_uint32(i), opts) for i in range(0, data_view.byte_length, 4)]

    if is_number(inst) or isinstance(inst, dict):
        return _print(inst, opts)

    raise ValueError("Unexpected input to print.")


def _print(inst, opts):
    if is_number(inst):
        inst = to_int32(inst) & 0xFFFFFFFF
        op_name = find_match(inst)
        if not op_name:
            raise ValueError("Unrecognized instruction")

        opcode_obj = get_opcode_details(op_name)
        values = _extract_values(inst, opcode_obj["format"])
        values["op"] = op_name
    elif isinstance(inst, dict):
        if not inst.get("op"):
            raise ValueError("Instruction object did not contain op")
        opcode_obj = get_opcode_details(inst["op"])
        values = inst
    else:
        raise ValueError("Unexpected value %s" % inst)

    if not opcode_obj:
        raise ValueError("Invalid opcode")

    if opts[3]:
        return values

    return _print_values(values, opcode_obj, opts)


def _print_values(values, opcode_obj, opts):
    casing, commas, include_dollar, _, num_base = opts
    result = _format_opcode(values, casing)

    display = opcode_obj["display"]
    last = len(display) - 1
    for i, display_entry in enumerate(display):
        if display_entry.endswith("?"):
            display_entry = display_entry.replace("?", "", 1)
            if values.get(display_entry) is None:
                continue  # Optional value, not set.

        value = values.get(display_entry)
        if value is None and display_entry != "(" and display_entry != ")":
            raise ValueError("Expected %s value, got undefined" % display_entry)

        add_comma = commas

        if display_entry in ("rs", "rt", "rd", "fs", "ft", "fd"):
            if not result.endswith("("):
                result += " "
            if display_entry[0] == "r":
                reg_name = get_reg_name(value)
            else:
                reg_name = get_float_reg_name(value)
            result += ("$" if include_dollar else "") + _apply_casing(reg_name, casing)
        elif display_entry in ("(", ")"):
            add_comma = False
            if result.endswith(","):
                result = result[:-1]  # Lop off comma, since we are involved in a parenthesis open/close
            result += display_entry

        imm_details = get_imm_format_details(display_entry)
        if imm_details:
            if not result.endswith("("):
                result += " "
            if imm_details["signed"] and imm_details["bits"] == 16:
                value = make_int16(value)
            if imm_details["shift"]:
                value = to_int32(to_int32(value) << imm_details["shift"])
            result += _format_number(value, num_base, casing)

        if add_comma and i != last and not result.endswith(","):
            result += ","

    return result.strip(" ")


def _extract_values(inst, fmt_list):
    values = {}
    for piece in reversed(fmt_list):
        if isinstance(piece, list):
            for alt in reversed(piece):
                bit_length = get_value_bit_length(alt)
                value = inst & make_bit_mask(bit_length)
                if is_binary_literal(alt):
                    if alt == pad_bit_string(format(value, "b"), bit_length):
                        piece = alt
                        break
                else:
                    piece = alt
                    break
        else:
            bit_length = get_value_bit_length(piece)
            value = inst & make_bit_mask(bit_length)

        if not is_binary_literal(piece):
            values[piece] = value
        inst >>= bit_length
    return values


def _format_number(num, num_base, casing):
    if num == 0:
        return num_to_string(num, num_base)

    value = ""
    if num < 0:
        value += "-"

    if num_base == 16:
        value += "0x"
    elif num_base == 8:
        value += "0o"
    elif num_base == 2:
        value += "0b"

    value += _apply_casing(num_to_string(abs(num), num_base), casing)
    return value


def _format_opcode(values, casing):
    pieces = values["op"].split(".")
    for i, piece in enumerate(pieces):
        if piece == "fmt":
            if "fmt3" in values:
                pieces[i] = get_fmt3_name(values["fmt3"])
            elif "fmt" in values:
                pieces[i] = get_fmt_name(values["fmt"])
            else:
                raise ValueError("Format value not available")
        elif piece == "cond":
            if "cond" in values:
                pieces[i] = get_cond_name(values["cond"])
            else:
                raise ValueError("Condition value not available")
    return _apply_casing(".".join(pieces), casing)


def _apply_casing(value, casing):
    if casing == "toLowerCase":
        return value.lower()
    return value.upper()
