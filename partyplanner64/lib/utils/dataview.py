"""A Python stand-in for JavaScript's DataView over an ArrayBuffer.

The original TypeScript reads and writes ROM data through DataView, which
is big-endian unless told otherwise. This class keeps the same method
names (in snake_case) so the ported code reads like the original:

    view = DataView(buffer)            # buffer: a bytearray
    view.get_uint32(0)                 # big-endian
    view.set_uint16(4, 0x1234, True)   # little-endian

Views share their buffer: writes through any view of a bytearray are seen
by every other view of it (as with an ArrayBuffer). A view over `bytes`
is read-only.
"""

import struct

_FORMATS = {
    "int8": "b", "uint8": "B", "int16": "h", "uint16": "H", "int32": "i", "uint32": "I",
    "float32": "f", "float64": "d", "bigint64": "q", "biguint64": "Q",
}


def _struct(kind, little_endian):
    return struct.Struct(("<" if little_endian else ">") + _FORMATS[kind])


_STRUCTS = {(kind, le): _struct(kind, le) for kind in _FORMATS for le in (False, True)}


class DataView:
    """A typed window onto a buffer, like JavaScript's DataView.

    Attributes:
        buffer: The underlying bytearray (or bytes).
        byte_offset: Where the view starts in the buffer.
        byte_length: How many bytes the view covers.
    """

    __slots__ = ("buffer", "byte_offset", "byte_length")

    def __init__(self, buffer, byte_offset=0, byte_length=None):
        if isinstance(buffer, DataView):
            byte_offset += buffer.byte_offset
            buffer = buffer.buffer
        elif isinstance(buffer, memoryview):
            buffer = buffer.obj if buffer.obj is not None else bytearray(buffer)
        if byte_length is None:
            byte_length = len(buffer) - byte_offset
        if byte_offset < 0 or byte_length < 0 or byte_offset + byte_length > len(buffer):
            raise IndexError("DataView out of range: offset %d, length %d, buffer %d"
                             % (byte_offset, byte_length, len(buffer)))
        self.buffer = buffer
        self.byte_offset = byte_offset
        self.byte_length = byte_length

    def __len__(self):
        return self.byte_length

    def _get(self, kind, offset, little_endian):
        s = _STRUCTS[(kind, bool(little_endian))]
        if offset < 0 or offset + s.size > self.byte_length:
            raise IndexError("Offset %d is outside the bounds of the DataView" % offset)
        return s.unpack_from(self.buffer, self.byte_offset + offset)[0]

    def _set(self, kind, offset, value, little_endian):
        s = _STRUCTS[(kind, bool(little_endian))]
        if offset < 0 or offset + s.size > self.byte_length:
            raise IndexError("Offset %d is outside the bounds of the DataView" % offset)
        if value is None:
            raise ValueError("Invalid value in set_%s" % kind)
        if kind in ("float32", "float64"):
            value = float(value)
        else:
            # JavaScript wraps integers to the type's width; so do we.
            bits = s.size * 8
            value = int(value) & ((1 << bits) - 1)
            if kind[0] != "u" and kind != "biguint64" and value >= 1 << (bits - 1):
                value -= 1 << bits
        s.pack_into(self.buffer, self.byte_offset + offset, value)

    def get_int8(self, offset):
        return self._get("int8", offset, False)

    def get_uint8(self, offset):
        return self._get("uint8", offset, False)

    def get_int16(self, offset, little_endian=False):
        return self._get("int16", offset, little_endian)

    def get_uint16(self, offset, little_endian=False):
        return self._get("uint16", offset, little_endian)

    def get_int32(self, offset, little_endian=False):
        return self._get("int32", offset, little_endian)

    def get_uint32(self, offset, little_endian=False):
        return self._get("uint32", offset, little_endian)

    def get_float32(self, offset, little_endian=False):
        return self._get("float32", offset, little_endian)

    def get_float64(self, offset, little_endian=False):
        return self._get("float64", offset, little_endian)

    def get_big_int64(self, offset, little_endian=False):
        return self._get("bigint64", offset, little_endian)

    def get_big_uint64(self, offset, little_endian=False):
        return self._get("biguint64", offset, little_endian)

    def set_int8(self, offset, value):
        self._set("int8", offset, value, False)

    def set_uint8(self, offset, value):
        self._set("uint8", offset, value, False)

    def set_int16(self, offset, value, little_endian=False):
        self._set("int16", offset, value, little_endian)

    def set_uint16(self, offset, value, little_endian=False):
        self._set("uint16", offset, value, little_endian)

    def set_int32(self, offset, value, little_endian=False):
        self._set("int32", offset, value, little_endian)

    def set_uint32(self, offset, value, little_endian=False):
        self._set("uint32", offset, value, little_endian)

    def set_float32(self, offset, value, little_endian=False):
        self._set("float32", offset, value, little_endian)

    def set_float64(self, offset, value, little_endian=False):
        self._set("float64", offset, value, little_endian)

    def set_big_int64(self, offset, value, little_endian=False):
        self._set("bigint64", offset, value, little_endian)

    def set_big_uint64(self, offset, value, little_endian=False):
        self._set("biguint64", offset, value, little_endian)

    def bytes(self, start=0, end=None):
        """Return a copy of the viewed bytes [start, end) as a new bytearray.

        Like `new Uint8Array(view.buffer, view.byteOffset, ...).slice()`.
        """
        end = self.byte_length if end is None else min(end, self.byte_length)
        return bytearray(self.buffer[self.byte_offset + start:self.byte_offset + end])

    def subview(self, start=0, length=None):
        """Return a DataView of part of this view (sharing the buffer)."""
        if length is None:
            length = self.byte_length - start
        return DataView(self.buffer, self.byte_offset + start, length)

    def __repr__(self):
        return "DataView(offset=0x%X, length=0x%X)" % (self.byte_offset, self.byte_length)
