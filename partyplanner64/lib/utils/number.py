"""Number and geometry helpers (port of utils/number.ts)."""

import math
import struct


def distance(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2))


def midpoint(x1, y1, x2, y2):
    return {"x": (x1 + x2) / 2, "y": (y1 + y2) / 2}


def line_distance(tx, ty, x1, y1, x2, y2):
    """Distance from tx,ty to the line made from x1,y1 --- x2,y2."""
    return (abs((y2 - y1) * tx - (x2 - x1) * ty + x2 * y1 - y2 * x1)
            / math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2))


def point_falls_within(x, y, xs, ys, xf, yf):
    """Test if (x,y) falls within the square formed from (xs,ys) - (xf,yf).

    Being exactly at (xs,ys) or (xf,yf) is considered in.
    """
    min_x, max_x = min(xs, xf), max(xs, xf)
    min_y, max_y = min(ys, yf), max(ys, yf)
    return min_x <= x <= max_x and min_y <= y <= max_y


def make_divisible_by(num, by):
    return by * math.ceil(num / by)


def degrees_to_radians(degrees):
    return degrees * math.pi / 180


def radians_to_degrees(radians):
    return radians * 180 / math.pi


def determine_angle(x_origin, y_origin, x, y):
    """Determine the angle made by two points.

    Returns:
        Radians counter-clockwise from the +x axis.
    """
    angle = math.atan2(y - y_origin, x - x_origin)
    if angle < 0:
        return abs(angle)
    return abs(angle - math.pi) + math.pi


def get_raw_float32_format(num):
    """Return the IEEE-754 float32 bits of a number (1.0 -> 0x3F800000)."""
    return struct.unpack(">I", struct.pack(">f", num))[0]
