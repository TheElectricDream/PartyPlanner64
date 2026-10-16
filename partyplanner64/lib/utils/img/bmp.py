"""Bitmap (palette) format utility methods (port of utils/img/BMP.ts).

IPaletteInfo is a dict: {"colors": [int, ...], "bpp": int}.
"""

from ..arrays import _region

_OUT_FORMATS = {8: 1, 16: 2, 32: 4}


def _pack_entry(value, out_bpp):
    size = _OUT_FORMATS.get(out_bpp)
    if size is None:
        raise TypeError("outView.setUint%s is not a function" % out_bpp)
    return (int(value) & ((1 << out_bpp) - 1)).to_bytes(size, "big")


def bm_pto_rgba(buffer, palette, in_bpp, out_bpp):
    """Decode palette-indexed pixels (2, 4 or 8 bpp) to out_bpp-bit palette values.

    (BMPtoRGBA; the name is what the naming rule gives.)
    """
    buf, start, length = _region(buffer)
    data = bytes(buf[start:start + length])
    if not in_bpp:
        return bytearray()  # NaN output length: nothing written.
    out_byte_length = int(length * (out_bpp / in_bpp))
    if out_byte_length <= 0:
        return bytearray(max(out_byte_length, 0))
    if in_bpp == 8:
        indices = data
    elif in_bpp == 4:
        pairs = bytearray(len(data) * 2)
        pairs[0::2] = data.translate(_HI4)
        pairs[1::2] = data.translate(_LO4)
        indices = bytes(pairs)
    elif in_bpp == 2:
        quads = bytearray(len(data) * 4)
        quads[0::4] = data.translate(_Q0)
        quads[1::4] = data.translate(_Q1)
        quads[2::4] = data.translate(_Q2)
        quads[3::4] = data.translate(_Q3)
        indices = bytes(quads)
    else:
        raise ValueError("Cannot decode palette with bpp: %s" % in_bpp)

    if indices and max(indices) >= len(palette):
        # Find the first bad index, as the TypeScript would hit it.
        bad = next(i for i in indices if i >= len(palette))
        raise ValueError("Invalid palette access (index %d of palette length %d)"
                         % (bad, len(palette)))
    entries = [_pack_entry(c, out_bpp) for c in palette]
    out = bytearray(b"".join([entries[i] for i in indices]))
    if len(out) != out_byte_length:
        # Fractional sizes: the loop stopped once out_byte_length was reached.
        out = out[:out_byte_length] + bytearray(max(0, out_byte_length - len(out)))
    return out


_HI4 = bytes((v & 0xF0) >> 4 for v in range(256))
_LO4 = bytes(v & 0x0F for v in range(256))
_Q0 = bytes((v & 0xC0) >> 6 for v in range(256))
_Q1 = bytes((v & 0x30) >> 4 for v in range(256))
_Q2 = bytes((v & 0x0C) >> 2 for v in range(256))
_Q3 = bytes(v & 0x03 for v in range(256))


def bm_pfrom_rgba(buffer, in_bpp, out_bpp):
    """Index the colors of in_bpp-bit pixels into an out_bpp-bit bitmap.

    (BMPfromRGBA.) Returns (bitmap bytearray, {"colors": [...], "bpp": in_bpp}).
    """
    buf, start, length = _region(buffer)
    data = bytes(buf[start:start + length])
    palette = {"colors": [], "bpp": in_bpp}
    palette_key_map = {}

    # Go through and determine the palette.
    pixel_byte_count = in_bpp // 8
    if pixel_byte_count not in (1, 2, 4):
        raise TypeError("pixelView.getUint%s is not a function" % in_bpp)
    usable = length - (length % pixel_byte_count)
    if usable != length:
        # The last partial pixel read would be out of bounds.
        raise IndexError("Offset is outside the bounds of the DataView")
    if pixel_byte_count == 1:
        colors = list(data)
    else:
        colors = [int.from_bytes(data[i:i + pixel_byte_count], "big")
                  for i in range(0, length, pixel_byte_count)]
    for color in colors:
        if color not in palette_key_map:
            palette_key_map[color] = len(palette["colors"])
            palette["colors"].append(color)

    # Now write the bitmap itself.
    bmp_length = int((length / pixel_byte_count) * (out_bpp / 8))
    if bmp_length > 0 and out_bpp != 8:
        raise ValueError("Cannot encode palette with bpp: %s" % out_bpp)
    bmp = bytearray((palette_key_map[c] & 0xFF) for c in colors[:bmp_length])
    return bmp, palette


def _get_palette_entry(palette, index):
    if index >= len(palette):
        raise ValueError("Invalid palette access (index %d of palette length %d)"
                         % (index, len(palette)))
    return palette[index]
