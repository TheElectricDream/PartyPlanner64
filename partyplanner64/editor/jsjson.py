"""JSON as JavaScript writes it (JSON.stringify), for board and event files.

Two differences from Python's json module matter for files the TypeScript
editor must read back identically:

- JavaScript objects list integer-like keys first, in ascending order, then the
  others in insertion order (`links` maps space indices to spaces).
- JavaScript numbers have no int/float distinction: 100.0 is written "100".
"""

import json
import math
from enum import Enum


def _is_array_index(key):
    """Whether a key is a canonical array index (JS orders these first)."""
    return (isinstance(key, str) and key.isdigit() and (key == "0" or key[0] != "0")
            and int(key) < 4294967295)


def js_ordered_items(obj):
    """The items of a dict in the order JavaScript would enumerate them."""
    items = list(obj.items())
    if not any(_is_array_index(_key(k)) for k, _ in items):
        return items
    index_items = sorted(((k, v) for k, v in items if _is_array_index(_key(k))),
                         key=lambda kv: int(_key(kv[0])))
    other_items = [(k, v) for k, v in items if not _is_array_index(_key(k))]
    return index_items + other_items


def _key(key):
    if isinstance(key, Enum):
        key = key.value
    return str(int(key) if isinstance(key, int) else key)


def to_js_value(value):
    """A copy of value normalized as JSON.parse(JSON.stringify(value)) would give it.

    Keys become strings in JS order, integral floats become ints, NaN and
    infinities become None, tuples become lists, enums their values.
    """
    if isinstance(value, Enum):
        return to_js_value(value.value)
    if isinstance(value, dict):
        return {_key(k): to_js_value(v) for k, v in js_ordered_items(value)}
    if isinstance(value, (list, tuple)):
        return [to_js_value(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        if value.is_integer() and abs(value) < 2 ** 53:
            return int(value)
        return value
    if hasattr(value, "value"):
        return to_js_value(value.value)
    if hasattr(value, "to_json"):
        return to_js_value(value.to_json())
    raise TypeError("Value of type %s is not JSON serializable" % type(value).__name__)


def stringify(value, indent=None):
    """JSON.stringify(value) (compact), or with indent."""
    if indent is None:
        return json.dumps(to_js_value(value), ensure_ascii=False, separators=(",", ":"))
    return json.dumps(to_js_value(value), ensure_ascii=False, indent=indent)


def parse(text):
    """JSON.parse(text), from str or bytes (a UTF-8 BOM is allowed)."""
    if isinstance(text, (bytes, bytearray, memoryview)):
        text = bytes(text).decode("utf-8-sig")
    elif text.startswith("﻿"):
        text = text[1:]
    return json.loads(text)
