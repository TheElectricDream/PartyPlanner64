"""Converts from a set of tiles to a single chunk, and vice-versa.

Port of utils/img/tiler.ts. Widths are in bytes (pixel count times bytes
per pixel), as in the TypeScript.
"""

from ..arrays import _region


def from_tiles(tile_views, tile_x_count, tile_y_count, tile_x_width, tile_y_width):
    """Takes a set of image tiles and reconstructs the entire image.

    tile_views are DataViews (or buffers) of the tiles, row-major.
    """
    width = tile_x_count * tile_x_width
    height = tile_y_count * tile_y_width
    out = bytearray(width * height)
    regions = [_region(t) for t in tile_views]

    if tile_x_width % 4 == 0:
        # Whole tile rows at a time (same bytes as the 4-byte copies).
        for y in range(height):
            tile_y = y % tile_y_width
            tile_view_index_partial = (y // tile_y_width) * tile_x_count
            tile_index = tile_y * tile_x_width
            out_index = y * width
            for tx in range(tile_x_count):
                buf, start, length = regions[tile_view_index_partial + tx]
                if tile_index + tile_x_width > length:
                    raise IndexError("Offset is outside the bounds of the DataView")
                s = start + tile_index
                out[out_index:out_index + tile_x_width] = buf[s:s + tile_x_width]
                out_index += tile_x_width
        return out

    # The general case: 4 bytes at a time, as the TypeScript does.
    for y in range(height):
        tile_y = y % tile_y_width
        tile_view_index_partial = (y // tile_y_width) * tile_x_count
        tile_index_partial = tile_y * tile_x_width
        out_index_partial = y * width
        for x in range(0, width, 4):
            tile_x = x % tile_x_width
            buf, start, length = regions[tile_view_index_partial + x // tile_x_width]
            tile_index = tile_index_partial + tile_x
            out_index = out_index_partial + x
            if tile_index + 4 > length or out_index + 4 > len(out):
                raise IndexError("Offset is outside the bounds of the DataView")
            s = start + tile_index
            out[out_index:out_index + 4] = buf[s:s + 4]
    return out


def to_tiles(img_arr, tile_x_count, tile_y_count, tile_x_width, tile_y_width):
    """Takes an image (bytes) and splits it into tiles (a list of bytearrays)."""
    width = tile_x_count * tile_x_width
    height = tile_y_count * tile_y_width
    if isinstance(img_arr, (list, tuple)):
        img_arr = bytes(v & 0xFF for v in img_arr)
    buf, start, length = _region(img_arr)
    data = bytes(buf[start:start + min(length, width * height)])
    if len(data) < width * height:
        # Reading past the end gave undefined (written as 0).
        data += bytes(width * height - len(data))

    tiles = [bytearray(tile_x_width * tile_y_width) for _ in range(tile_x_count * tile_y_count)]
    for y in range(height):
        tile_view_index_partial = (y // tile_y_width) * tile_x_count
        tile_index = (y % tile_y_width) * tile_x_width
        img_index = y * width
        for tx in range(tile_x_count):
            tiles[tile_view_index_partial + tx][tile_index:tile_index + tile_x_width] = \
                data[img_index:img_index + tile_x_width]
            img_index += tile_x_width
    return tiles
