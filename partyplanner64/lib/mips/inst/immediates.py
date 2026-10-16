"""Immediate value helpers (port of mips-inst immediates.js)."""

import re

from .._js import parse_int, to_uint32

_RADIX = {"b": 2, "o": 8, "x": 16}


def parse_immediate(imm_arr, max_bits, signed, shift):
    """Parses [neg, base, num] regex pieces. Returns None for NaN."""
    neg, base, num = imm_arr
    value = parse_int(num, _RADIX.get(base.lower(), 10))
    if value is None:
        return value  # Let the caller decide what to do with NaN.

    if shift:
        value = to_uint32(value) >> shift

    if max_bits == 16:
        if signed:
            value = make_int16(value)

    if neg:
        value = -value

    return value


def format_immediate(value, max_bits=None):
    if max_bits == 16:
        value = int(value) & 0xFFFF
    return value


def make_int16(value):
    value = int(value) & 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


_imm_cache = {}
_digits = re.compile(r"\d+")


def get_imm_format_details(format_val):
    """Returns {signed, bits, shift} for an immediate format value, else None."""
    try:
        return _imm_cache[format_val]
    except KeyError:
        pass
    result = _compute_imm_format_details(format_val)
    _imm_cache[format_val] = result
    return result


def _compute_imm_format_details(format_val):
    # Remove optional indicator
    if format_val.endswith("?"):
        format_val = format_val[:-1]

    if "int" not in format_val:
        if format_val[:2] == "cc":
            return {"signed": False, "bits": 4, "shift": 0}
        return None  # Not an immediate

    shift = 0
    shift_index = format_val.find("shift")
    if shift_index > 0:
        shift = int(_digits.findall(format_val[shift_index:])[0])

    return {
        "signed": format_val[0] != "u",
        "bits": int(_digits.findall(format_val)[0]),
        "shift": shift,
    }
