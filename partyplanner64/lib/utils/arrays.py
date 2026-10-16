"""Buffer and array helpers (port of utils/arrays.ts).

ArrayBuffers are bytearrays (bytes when read-only); DataViews are
partyplanner64.lib.utils.dataview.DataView. Functions taking a buffer
accept either, and memoryviews too.
"""

import base64
import builtins
import hashlib

from .dataview import DataView
from .debug import hexstr


def is_array_buffer_like(value):
    """Whether a value is a raw buffer (bytearray, bytes or memoryview)."""
    return isinstance(value, (bytearray, bytes, memoryview))


def _region(arr):
    """Return (buffer, start, length) for a DataView or buffer."""
    if isinstance(arr, DataView):
        return arr.buffer, arr.byte_offset, arr.byte_length
    if isinstance(arr, memoryview):
        if arr.format != "B":
            arr = arr.cast("B")
        return arr, 0, arr.nbytes
    return arr, 0, len(arr)


def byte_length(arr):
    """Return the byteLength of a buffer or DataView."""
    return _region(arr)[2]


def to_bytes(arr):
    """Return a copy of the bytes of a buffer or DataView as bytes."""
    buf, start, length = _region(arr)
    return bytes(buf[start:start + length])


def copy_range(out_arr, in_arr, out_offset, in_offset, len):
    """Copy len bytes from in_arr[in_offset:] to out_arr[out_offset:].

    out_arr is a bytearray (or writable memoryview) or a DataView; in_arr is
    a buffer, a DataView or a list of byte values.
    """
    if len <= 0:
        return
    out_buf, out_start, out_length = _region(out_arr)
    if out_offset < 0 or out_offset + len > out_length:
        raise IndexError("Offset is outside the bounds of the DataView")
    dst = out_start + out_offset
    if isinstance(in_arr, (list, tuple)):
        values = in_arr[in_offset:in_offset + len]
        if builtins.len(values) < len:
            raise IndexError("copyRange: source is too short")
        out_buf[dst:dst + len] = bytes(v & 0xFF for v in values)
        return
    in_buf, in_start, in_length = _region(in_arr)
    if in_offset < 0 or in_offset + len > in_length:
        raise IndexError("Offset is outside the bounds of the DataView")
    src = in_start + in_offset
    out_buf[dst:dst + len] = in_buf[src:src + len]


def array_to_array_buffer(arr):
    """Return a bytearray of a list of byte values."""
    return bytearray(v & 0xFF for v in arr)


def hash(arr, start_offset, len):
    """Return the MD5 hex digest of len bytes of arr from start_offset.

    Can't be equal if our length would extend out of bounds: returns "".
    """
    buf, start, length = _region(arr)
    if start_offset + len > length:
        return ""
    begin = start + start_offset
    return hashlib.md5(bytes(buf[begin:begin + len])).hexdigest()


def hash_equal(hash_args, expected):
    """Whether hash(*hash_args) equals an expected hex digest (case-insensitive)."""
    return hash(*hash_args).lower() == expected.lower()


def to_hex_string(buffer, len=None, line_len=0):
    """Return the bytes as space-separated upper-case hex pairs."""
    buf, start, length = _region(buffer)
    if len is None:
        len = length
    if len > length:
        raise IndexError("Offset is outside the bounds of the DataView")
    parts = []
    for i in range(len):
        sep = "\n" if (i and line_len and (i + 1) % line_len == 0) else " "
        parts.append(hexstr(buf[start + i], "") + sep)
    return "".join(parts)


def print(buffer, len=None, line_len=0):
    """Print the bytes as hex (console.log(toHexString(...)))."""
    builtins.print(to_hex_string(buffer, len, line_len))


def read_bit_at_offset(buffer, bit_offset):
    buf, start, length = _region(buffer)
    byte_offset = bit_offset // 8
    in_byte_offset = bit_offset % 8
    mask = 0x80 >> in_byte_offset
    if byte_offset >= length:
        raise IndexError("Offset is outside the bounds of the DataView")
    return 1 if buf[start + byte_offset] & mask else 0


def read_byte_at_bit_offset(buffer, bit_offset):
    buf, start, length = _region(buffer)
    short_offset = bit_offset // 8
    in_short_offset = bit_offset % 8
    mask = 0xFF00 >> in_short_offset
    if short_offset + 2 > length:
        raise IndexError("Offset is outside the bounds of the DataView")
    value = (buf[start + short_offset] << 8) | buf[start + short_offset + 1]
    return (value & mask) >> (8 - in_short_offset)


def array_buffer_to_image_data(buffer, width, height):
    """Return an ImageData holding RGBA32 bytes."""
    from .canvas import ImageData
    image_data = ImageData(width, height)
    data = to_bytes(buffer)
    image_data.data[:builtins.len(data)] = data
    return image_data


def array_buffer_to_data_url(buffer, width, height):
    """Return a PNG data URL for RGBA32 bytes."""
    from .canvas import image_data_to_data_url
    return image_data_to_data_url(array_buffer_to_image_data(buffer, width, height))


def data_url_to_array_buffer(data_url):
    """Converts a Data URL (`data:mime;base64,...`) to a bytearray."""
    return bytearray(base64.b64decode(data_url.split(",")[1]))


def array_buffers_equal(first, second):
    """Whether two buffers hold the same bytes."""
    if byte_length(first) != byte_length(second):
        return False
    return to_bytes(first) == to_bytes(second)


def join(buffer1, buffer2):
    """Joins two buffers into a new bytearray (or returns the one given)."""
    if buffer1 is None or buffer2 is None:
        return buffer1 if buffer1 is not None else buffer2
    return bytearray(to_bytes(buffer1) + to_bytes(buffer2))


def equal(a, b):
    """Tests if two lists are equal.

    They are equal if:
      - They are the same reference.
      - They have the same number of items
      - Each item is === across arrays.
    """
    if a is b:
        return True
    if builtins.len(a) != builtins.len(b):
        return False
    for x, y in zip(a, b):
        if not _strict_equal(x, y):
            return False
    return True


def _strict_equal(x, y):
    # JavaScript's === compares objects by identity and primitives by value.
    if isinstance(x, (dict, list)) or isinstance(y, (dict, list)):
        return x is y
    return x == y


def intersection(a, b, equality_fn=None):
    """Creates the intersection of two lists.

    equality_fn takes two values and decides if they're equal.
    """
    if equality_fn is None:
        equality_fn = _strict_equal
    output = []
    for a_val in a:
        for b_val in b:
            if equality_fn(a_val, b_val):
                output.append(a_val)
                break
    return output


def create_filled_array(value, count):
    """Creates a list filled with `count` entries of `value`."""
    return [value] * count
