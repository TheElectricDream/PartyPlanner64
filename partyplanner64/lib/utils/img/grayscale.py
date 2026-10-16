"""Grayscale -> RGBA32 (port of utils/img/Grayscale.ts)."""

from ..arrays import _region

_NIBBLE = bytes(((v * 0xFF) // 0x0F) & 0xFF for v in range(16))
_HI_NIBBLE = bytes(_NIBBLE[v >> 4] for v in range(256))
_LO_NIBBLE = bytes(_NIBBLE[v & 0x0F] for v in range(256))


def grayscale_to_rgba32(buffer, width, height, bpp):
    """Return RGBA32 bytes of 4 or 8 bpp grayscale pixels."""
    count = int(width) * int(height)
    if count and bpp not in (4, 8):
        raise ValueError("bpp must be 4 or 8")
    buf, start, avail = _region(buffer)
    if bpp == 8:
        if count > avail:
            raise IndexError("Offset is outside the bounds of the DataView")
        values = bytes(buf[start:start + count])
    else:
        nbytes = (count + 1) // 2
        if nbytes > avail:
            raise IndexError("Offset is outside the bounds of the DataView")
        data = bytes(buf[start:start + nbytes])
        merged = bytearray(nbytes * 2)
        merged[0::2] = data.translate(_HI_NIBBLE)
        merged[1::2] = data.translate(_LO_NIBBLE)
        values = bytes(merged[:count])
    out = bytearray(b"\xff" * (count * 4))
    out[0::4] = values
    out[1::4] = values
    out[2::4] = values
    return out


def grayscale_from_rgba32(buffer, width, height, bpp):
    raise NotImplementedError("Grayscale.fromRGBA32 not implemented")
