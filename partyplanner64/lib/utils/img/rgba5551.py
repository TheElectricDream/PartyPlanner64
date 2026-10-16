"""RGBA5551 <-> RGBA32 conversions (port of utils/img/RGBA5551.ts).

5 bits each for RGB, 1 for alpha. The conversions work a whole channel
at a time with bytes.translate, so a full board background converts in a
fraction of a second.
"""

from ..arrays import _region

# RGBA5551 (big-endian hi, lo bytes) -> RGBA32 channels.
_HI_TO_R = bytes((v & 0xF8) for v in range(256))
_HI_TO_G = bytes(((v & 0x07) << 5) for v in range(256))
_LO_TO_G = bytes(((v >> 6) << 3) for v in range(256))
_LO_TO_B = bytes(((v & 0x3E) << 2) for v in range(256))
_LO_TO_A = bytes((0xFF if v & 1 else 0) for v in range(256))

# RGBA32 channels -> RGBA5551 hi and lo bytes.
_R_TO_HI = bytes((v & 0xF8) for v in range(256))
_G_TO_HI = bytes((v >> 5) for v in range(256))
_G_TO_LO = bytes((((v >> 3) & 3) << 6) for v in range(256))
_B_TO_LO = bytes(((v >> 3) << 1) for v in range(256))
_A_TO_LO = bytes((v >> 7) for v in range(256))


def _or(*parts):
    """Bytewise OR of equal-length byte strings."""
    n = len(parts[0])
    value = 0
    for part in parts:
        value |= int.from_bytes(part, "big")
    return value.to_bytes(n, "big")


def _input(buffer, length):
    buf, start, avail = _region(buffer)
    data = bytes(buf[start:start + min(avail, length)])
    if len(data) < length:
        # Reading past the end gave undefined (NaN -> 0) in the TypeScript.
        data += bytes(length - len(data))
    return data


def rgba5551to_rgba32(buffer, width, height):
    """Return RGBA32 bytes of big-endian RGBA5551 pixels."""
    count = int(width) * int(height)
    buf, start, avail = _region(buffer)
    if count * 2 > avail:
        raise IndexError("Offset is outside the bounds of the DataView")
    data = bytes(buf[start:start + count * 2])
    hi = data[0::2]
    lo = data[1::2]
    out = bytearray(count * 4)
    out[0::4] = hi.translate(_HI_TO_R)
    out[1::4] = _or(hi.translate(_HI_TO_G), lo.translate(_LO_TO_G)) if count else b""
    out[2::4] = lo.translate(_LO_TO_B)
    out[3::4] = lo.translate(_LO_TO_A)
    return out


def rgba5551from_rgba32(buffer, width, height):
    """Return big-endian RGBA5551 bytes of RGBA32 pixels."""
    count = int(width) * int(height)
    data = _input(buffer, count * 4)
    r = data[0::4]
    g = data[1::4]
    b = data[2::4]
    a = data[3::4]
    out = bytearray(count * 2)
    if count:
        out[0::2] = _or(r.translate(_R_TO_HI), g.translate(_G_TO_HI))
        out[1::2] = _or(g.translate(_G_TO_LO), b.translate(_B_TO_LO), a.translate(_A_TO_LO))
    return out
