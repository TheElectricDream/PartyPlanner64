"""JavaScript number semantics used by the MIPS ports.

mips-inst and mips-assembler rely on a few JavaScript behaviours (32-bit
bit operations, parseInt's lenient prefix parsing, number-to-string
conversion); these helpers reproduce them so the ports behave the same.
"""

import math

# Characters JavaScript's String.prototype.trim / parseInt treat as white space.
JS_WHITESPACE = ("\t\n\v\f\r          "
                 "        　﻿")

_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def to_int32(value):
    """JavaScript ToInt32 (what `x | 0` and the bit operators apply)."""
    if not isinstance(value, int):
        if value is None or isinstance(value, str):
            value = js_to_number(value)
        if math.isnan(value) or math.isinf(value):
            return 0
        value = int(value)  # Truncates toward zero, like ToInt32.
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def to_uint32(value):
    """JavaScript ToUint32 (what `x >>> 0` applies)."""
    return to_int32(value) & 0xFFFFFFFF


def js_to_number(value):
    """A small subset of JavaScript's Number() conversion."""
    if value is None:
        return math.nan
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip(JS_WHITESPACE)
    if s == "":
        return 0
    try:
        if s[:2].lower() == "0x":
            return int(s[2:], 16)
        if s[:2].lower() == "0b":
            return int(s[2:], 2)
        if s[:2].lower() == "0o":
            return int(s[2:], 8)
        f = float(s)
        return int(f) if f.is_integer() and "." not in s and "e" not in s.lower() else f
    except ValueError:
        return math.nan


def parse_int(s, radix=10):
    """JavaScript parseInt(s, radix): parses the longest valid prefix.

    Returns None where JavaScript gives NaN.
    """
    if s is None:
        s = "undefined"
    s = str(s).lstrip(JS_WHITESPACE)
    sign = 1
    if s[:1] in ("+", "-"):
        if s[0] == "-":
            sign = -1
        s = s[1:]
    if radix == 16 and s[:2] in ("0x", "0X"):
        s = s[2:]
    n = 0
    count = 0
    for ch in s:
        d = _DIGITS.find(ch.lower())
        if d < 0 or d >= radix:
            break
        n = n * radix + d
        count += 1
    if not count:
        return None
    if n >= 9007199254740992:
        n = int(float(n))  # JavaScript numbers are doubles.
    return sign * n


def is_number(value):
    """typeof value === "number"."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def num_to_string(value, radix=10):
    """JavaScript Number.prototype.toString(radix) for the values we see."""
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value.is_integer() and abs(value) < 1e21:
            value = int(value)
        elif radix == 10:
            r = repr(value)
            if "e" in r:
                mant, exp = r.split("e")
                exp = int(exp)
                if mant.endswith(".0"):
                    mant = mant[:-2]
                r = mant + "e" + ("+" if exp > 0 else "-") + str(abs(exp))
            return r
        else:
            # Fractional values in other bases are rare here; approximate.
            neg = value < 0
            value = abs(value)
            ipart = int(value)
            frac = value - ipart
            digits = []
            while frac and len(digits) < 52:
                frac *= radix
                d = int(frac)
                digits.append(_DIGITS[d])
                frac -= d
            return ("-" if neg else "") + num_to_string(ipart, radix) + "." + "".join(digits)
    if radix == 10:
        return str(value)
    if value == 0:
        return "0"
    neg = value < 0
    value = abs(value)
    out = []
    while value:
        value, d = divmod(value, radix)
        out.append(_DIGITS[d])
    return ("-" if neg else "") + "".join(reversed(out))


def js_str(value):
    """String(value) as JavaScript would produce it for our value types."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if is_number(value):
        return num_to_string(value)
    if isinstance(value, (list, tuple)):
        return ",".join("" if v is None else js_str(v) for v in value)
    return str(value)
