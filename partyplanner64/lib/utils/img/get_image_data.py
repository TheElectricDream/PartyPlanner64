"""Image sources to ImageData (port of utils/img/getImageData.ts).

Resizing uses an exact port of the npm package resize-image-data (0.3.1,
bilinear interpolation), which the TypeScript used, so that images written
to the ROM come out byte-identical.
"""

import math

from ..canvas import ImageData, from_pil, open_image


def _js_round(x):
    """Math.round: halves round up."""
    r = math.floor(x)
    return r + 1 if x - r >= 0.5 else r


def _nearest_neighbor(src, dst):
    pos = 0
    sdata = src.data
    ddata = dst.data
    for y in range(dst.height):
        src_y = math.floor(y * src.height / dst.height)
        for x in range(dst.width):
            src_x = math.floor(x * src.width / dst.width)
            src_pos = ((src_y * src.width) + src_x) * 4
            ddata[pos:pos + 4] = sdata[src_pos:src_pos + 4]
            pos += 4


def _bilinear_interpolation(src, dst):
    sw, sh = src.width, src.height
    sdata = src.data
    ddata = dst.data

    def interpolate(k, k_min, k_max, v_min, v_max):
        return _js_round((k - k_min) * v_max + (k_max - k) * v_min)

    # Per destination column: srcX, xMin, xMax.
    cols = []
    for x in range(dst.width):
        src_x = x * sw / dst.width
        x_min = math.floor(src_x)
        x_max = min(math.ceil(src_x), sw - 1)
        cols.append((src_x, x_min, x_max))

    row_cache = {}

    def horizontal_row(y):
        """interpolateHorizontal for every column and channel of source row y."""
        row = row_cache.get(y)
        if row is not None:
            return row
        base = y * sw * 4
        row = []
        for src_x, x_min, x_max in cols:
            p_min = base + x_min * 4
            if x_min == x_max:
                row.append(tuple(sdata[p_min:p_min + 4]))
            else:
                p_max = base + x_max * 4
                row.append((
                    interpolate(src_x, x_min, x_max, sdata[p_min], sdata[p_max]),
                    interpolate(src_x, x_min, x_max, sdata[p_min + 1], sdata[p_max + 1]),
                    interpolate(src_x, x_min, x_max, sdata[p_min + 2], sdata[p_max + 2]),
                    interpolate(src_x, x_min, x_max, sdata[p_min + 3], sdata[p_max + 3]),
                ))
        row_cache[y] = row
        return row

    pos = 0
    for y in range(dst.height):
        src_y = y * sh / dst.height
        y_min = math.floor(src_y)
        y_max = min(math.ceil(src_y), sh - 1)
        top = horizontal_row(y_min)
        if y_min == y_max:
            out = bytes(v for px in top for v in px)
        else:
            bottom = horizontal_row(y_max)
            out = bytes(
                min(255, max(0, interpolate(src_y, y_min, y_max, a, b)))
                for pa, pb in zip(top, bottom) for a, b in zip(pa, pb))
        ddata[pos:pos + len(out)] = out
        pos += len(out)
        # Rows above y_min are never needed again.
        for key in [k for k in row_cache if k < y_min]:
            del row_cache[key]


def resize_image_data(image, width, height, algorithm=None):
    """Return a resized copy of an ImageData (npm resize-image-data)."""
    algorithm = algorithm or "bilinear-interpolation"
    if algorithm == "nearest-neighbor":
        resize = _nearest_neighbor
    elif algorithm in ("bilinear-interpolation", "biliniear-interpolation"):
        resize = _bilinear_interpolation
    else:
        raise ValueError("Unknown algorithm: %s" % algorithm)
    result = ImageData(width, height)
    resize(image, result)
    return result


def get_image_data(src, width, height):
    """Retrieves the ImageData for a source image, sized to particular dimensions.

    Args:
        src: Image source (a data URL, path, bytes or Pillow Image).
        width: Output data width.
        height: Output data height.
    """
    img_data = from_pil(open_image(src))
    if width != img_data.width or height != img_data.height:
        img_data = resize_image_data(img_data, int(width), int(height))
    return img_data
