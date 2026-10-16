"""Image helpers (port of utils/image.ts)."""

from .arrays import _region


def cut_from_whole(src_buffer, src_width, src_height, bpp, x, y, width, height):
    """Cuts an image from a bigger image at x,y coordinates.

    A mystery: why didn't I use canvas?
    """
    piece_width = int(width * (bpp / 8))
    buf, start, length = _region(src_buffer)
    out = bytearray(piece_width * height)
    src_byte_width = int(src_width * (bpp / 8))
    piece_x_start = int(x * (bpp / 8))
    out_pos = 0
    for yi in range(y, y + height):
        row_idx = piece_x_start + src_byte_width * yi
        row = buf[start + row_idx:start + min(row_idx + piece_width, length)] if row_idx < length else b""
        # Reading past the end gave undefined (stored as 0).
        out[out_pos:out_pos + len(row)] = row
        out_pos += piece_width
    return out


def to_array_buffer(image, width, height):
    """Retrieves the RGBA32 data for an image source, sized to width x height.

    image is anything partyplanner64.lib.utils.canvas.open_image accepts
    (the TypeScript took a loaded Image element).
    """
    from .img.get_image_data import get_image_data
    return get_image_data(image, width, height).data


def invert_color(hex):
    r_orig = (hex >> 16) & 0xFF
    g_orig = (hex >> 8) & 0xFF
    b_orig = hex & 0xFF

    r = 255 - r_orig
    g = 255 - g_orig
    b = 255 - b_orig

    return (r << 16) | (g << 8) | b
