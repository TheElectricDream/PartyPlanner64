"""JavaScript semantics the adapters depend on (private helpers).

The TypeScript relied on a few behaviours of JavaScript that Python does
differently; reproducing them keeps the written ROM bytes identical:

- Plain objects iterate integer-like keys in ascending numeric order, then
  the other keys in insertion order ({"5":..,"-2":..,"1":..} iterates
  1, 5, -2).
- Math.round rounds halves up (towards +Infinity).
- Number#toString prints integral numbers without ".0".
- Indexing an array out of range gives undefined instead of raising.
"""

import math
from enum import Enum


def _array_index(key):
    """Return the int for a canonical array-index key ("0", "12", 3), else None."""
    if isinstance(key, bool):
        return None
    if isinstance(key, int):
        return key if 0 <= key < 0xFFFFFFFF else None
    if isinstance(key, str) and key.isdigit() and key.isascii():
        if key != "0" and key.startswith("0"):
            return None
        value = int(key)
        return value if value < 0xFFFFFFFF else None
    return None


def js_keys(obj):
    """Return the keys of a dict in the order a JS `for...in` would visit them."""
    if not obj:
        return []
    indexed = []
    others = []
    for key in obj:
        idx = _array_index(key)
        if idx is None:
            others.append(key)
        else:
            indexed.append((idx, key))
    indexed.sort(key=lambda pair: pair[0])
    return [key for _, key in indexed] + others


def js_round(x):
    """Math.round: round to the nearest integer, halves towards +Infinity."""
    if x != x or x in (math.inf, -math.inf):
        return x
    r = math.floor(x)
    if x - r >= 0.5:
        r += 1
    return int(r)


def js_number_str(num):
    """Number#toString (and JSON.stringify) of a number: 5.0 -> "5", 1e-7 -> "1e-7"."""
    if isinstance(num, bool):
        return "true" if num else "false"
    if isinstance(num, int):
        return str(num)
    num = float(num)
    if num != num:
        return "NaN"
    if num in (math.inf, -math.inf):
        return "Infinity" if num > 0 else "-Infinity"
    if num == 0:
        return "0"
    sign = "-" if num < 0 else ""
    # The shortest round-tripping digits, as both JavaScript and repr() find them.
    mantissa, _, exp = ("%r" % abs(num)).partition("e")
    int_part, _, frac_part = mantissa.partition(".")
    if frac_part == "0":
        frac_part = ""
    digits = (int_part + frac_part).lstrip("0")
    point = len(int_part) + (int(exp) if exp else 0)  # Position of the decimal point.
    point -= len(int_part + frac_part) - len((int_part + frac_part).lstrip("0"))
    digits = digits.rstrip("0") or "0"
    k = len(digits)
    n = point
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        out = digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + out


def json_stringify(value):
    """JSON.stringify(value), compact, with JavaScript's number formatting and key order."""
    import json

    def key(k):
        k = getattr(k, "value", k) if isinstance(k, Enum) else k
        return json.dumps(js_number_str(k) if isinstance(k, (int, float)) else str(k), ensure_ascii=False)

    def enc(v):
        if isinstance(v, Enum):
            v = v.value
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            if isinstance(v, float) and (v != v or v in (math.inf, -math.inf)):
                return "null"
            return js_number_str(int(v) if isinstance(v, int) else v)
        if isinstance(v, str):
            return json.dumps(str(v), ensure_ascii=False)
        if isinstance(v, dict):
            return "{" + ",".join(key(k) + ":" + enc(v[k]) for k in js_keys(v)) + "}"
        if isinstance(v, (list, tuple)):
            return "[" + ",".join(enc(item) for item in v) + "]"
        raise TypeError("Object of type %s is not JSON serializable" % type(v).__name__)

    return enc(value)


def at(lst, index):
    """lst[index] with JavaScript semantics: None (undefined) when out of range."""
    if lst is None or index is None or isinstance(index, bool):
        return None
    if not isinstance(index, int):
        if isinstance(index, float) and index.is_integer():
            index = int(index)
        else:
            return None
    if 0 <= index < len(lst):
        return lst[index]
    return None


def index_of(lst, value):
    """Array#indexOf (strict equality, -1 when absent)."""
    for i, item in enumerate(lst):
        if item == value and not isinstance(item, bool) and not isinstance(value, bool):
            return i
    return -1


def is_number(value):
    """typeof value === "number"."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def link_key(links, index):
    """The key board.links uses for a space index.

    Board JSON keeps links keyed by strings ("3"); the Python boards module
    normalizes them to ints. Prefer whichever the dict already has (ints
    for an empty dict).
    """
    if index in links:
        return index
    skey = str(index)
    if skey in links:
        return skey
    for key in links:
        if isinstance(key, str):
            return skey
        break
    return index


def get_link(links, index):
    """board.links[index] (None when absent)."""
    if not links:
        return None
    if index in links:
        return links[index]
    return links.get(str(index))


def substring(s, start, end=None):
    """String#substring: clamps to the string and swaps reversed bounds."""
    length = len(s)
    start = min(max(int(start), 0), length)
    end = length if end is None else min(max(int(end), 0), length)
    if start > end:
        start, end = end, start
    return s[start:end]


def count_occurrences(s, sub):
    """Count matches the way `while ((i = s.indexOf(sub, i + 1)) !== -1)` does."""
    count = 0
    last_index = s.find(sub, 0)
    while last_index != -1:
        count += 1
        last_index = s.find(sub, last_index + 1)
    return count


def to_bytes_array(arr):
    """arrayToArrayBuffer: a list of numbers as bytes (each wrapped to 8 bits)."""
    return bytearray((int(v) & 0xFF) for v in arr)
