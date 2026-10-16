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
    """Number#toString for the numbers boards hold (5 -> "5", 2.5 -> "2.5")."""
    if isinstance(num, bool):
        return "true" if num else "false"
    if isinstance(num, float):
        if num != num:
            return "NaN"
        if num in (math.inf, -math.inf):
            return "Infinity" if num > 0 else "-Infinity"
        if num.is_integer() and abs(num) < 1e21:
            return str(int(num))
        return repr(num)
    return str(num)


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

    Board JSON keeps links keyed by strings ("3"); boards built in Python
    may use ints. Prefer whichever the dict already has.
    """
    if index in links:
        return index
    skey = str(index)
    if skey in links:
        return skey
    for key in links:
        if isinstance(key, int) and not isinstance(key, bool):
            return index
        break
    return skey


def get_link(links, index):
    """board.links[index] (None when absent)."""
    if not links:
        return None
    if index in links:
        return links[index]
    return links.get(str(index))
