"""String helpers (port of utils/string.ts)."""

import builtins
import re


def from_u32(u32):
    """Return the four characters packed big-endian in a 32-bit value."""
    u32 &= 0xFFFFFFFF
    return (chr((u32 >> 24) & 0xFF) + chr((u32 >> 16) & 0xFF)
            + chr((u32 >> 8) & 0xFF) + chr(u32 & 0xFF))


def to_u32(str):
    """Pack the first four character codes of a string big-endian.

    As in the TypeScript (32-bit bit operations), the result is a signed
    32-bit number.
    """
    char_codes = to_char_codes(str)
    u32 = 0
    u32 |= char_codes[0] << 24
    u32 |= char_codes[1] << 16
    u32 |= char_codes[2] << 8
    u32 |= char_codes[3]
    u32 &= 0xFFFFFFFF
    return u32 - 0x100000000 if u32 & 0x80000000 else u32


def to_char_codes(str):
    """Return the UTF-16 code units of a string (charCodeAt)."""
    data = str.encode("utf-16-be", "surrogatepass")
    return [(data[i] << 8) | data[i + 1] for i in range(0, len(data), 2)]


def string_to_array_buffer(str):
    """Converts a string to a bytearray (UTF-8, as TextEncoder)."""
    return bytearray(str.encode("utf-8", "replace"))


def string_from_array_buffer(buffer):
    """Decodes UTF-8 bytes to a string (as TextDecoder: a leading BOM is dropped)."""
    from .arrays import to_bytes
    return to_bytes(buffer).decode("utf-8-sig", "replace")


def pad(str, len, pad_char):
    while builtins.len(str) < len:
        str = pad_char + str
    return str


def splice(value, start, del_count, new_sub_str):
    return value[:start] + new_sub_str + value[start + abs(del_count):]


def string_comparer(a, b):
    """String comparer function compatible with `sort` (use functools.cmp_to_key)."""
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def normalize_line_endings(str):
    if not str:
        return str
    return re.sub(r"\r\n|\r", "\n", str)


_COLOR_TAG = re.compile(r"<\w+>", re.ASCII)


def mp_format_to_plain_text(value):
    if not value:
        return ""
    value = _COLOR_TAG.sub("", value)  # Remove color tags
    # As in the TypeScript, each of these replaces only the first occurrence.
    for code, char in (
        ("　", "Ⓐ"),  # ! A button
        ("、", "Ⓑ"),  # " B button
        ("。", "▲"),  #  C-up button
        ("〃", "►"),  #  C-right button
        ("〄", "◄"),  #  C-left button
        ("々", "▼"),  # & C-down button
        ("〆", "Ⓩ"),  # ' Z button
        ("〇", "\U0001f579️"),  # ( Analog stick
        ("〈", "✪"),  # ) (coin)
        ("〉", "★"),  # * Star
        ("【", "Ⓢ"),  # , S button
        ("】", "Ⓡ"),  # , R button
    ):
        value = value.replace(code, char, 1)
    return value
