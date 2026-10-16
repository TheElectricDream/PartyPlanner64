"""Helpers that reproduce how JavaScript turns values into text.

The event code is built from template literals (`${value}`), where JavaScript's
string conversion applies: `true`, `undefined`, `1,2,3` for arrays, no ".0"
on whole floats. The Python port builds the same text with these helpers.
"""

import math
from enum import Enum


def js_str(value):
    """String(value), as JavaScript would print it in a template literal."""
    if isinstance(value, Enum):
        return js_str(value.value)
    if value is None:
        return "undefined"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value == int(value) and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    if isinstance(value, (list, tuple)):
        return ",".join("" if v is None else js_str(v) for v in value)
    if isinstance(value, int):
        return str(int(value))
    return str(value)


def js_or(value, default):
    """`value || default`."""
    if value is None or value is False or value == "" or value == 0:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    return value


def js_join(values, sep=","):
    """array.join(sep): null and undefined entries become empty strings."""
    return sep.join("" if v is None else js_str(v) for v in values)


def is_nan(value):
    """isNaN(value) for the values events deal with (numbers or undefined)."""
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return isinstance(value, float) and math.isnan(value)
    try:
        float(value)
        return False
    except (TypeError, ValueError):
        return True


_JS_WS = ("\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007"
          "\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff")


def js_trim(s):
    """String.prototype.trim(): JavaScript's set of whitespace differs from Python's."""
    return s.strip(_JS_WS)
