"""Transform maths for the exporters (the parts of three.js Object3D they need)."""

import math


def quaternion_from_euler(x, y, z, order="ZYX"):
    """Return [x, y, z, w] of a three.js Euler (Quaternion.setFromEuler)."""
    c1, c2, c3 = math.cos(x / 2), math.cos(y / 2), math.cos(z / 2)
    s1, s2, s3 = math.sin(x / 2), math.sin(y / 2), math.sin(z / 2)
    if order == "XYZ":
        return [s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3,
                c1 * c2 * s3 + s1 * s2 * c3, c1 * c2 * c3 - s1 * s2 * s3]
    if order == "ZYX":
        return [s1 * c2 * c3 - c1 * s2 * s3, c1 * s2 * c3 + s1 * c2 * s3,
                c1 * c2 * s3 - s1 * s2 * c3, c1 * c2 * c3 + s1 * s2 * s3]
    raise ValueError("Unsupported rotation order %s" % order)


def compose(position, quaternion, scale):
    """Return the 4x4 matrix (row-major nested lists) of a position, rotation and scale."""
    x, y, z, w = quaternion
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz = x * x2, x * y2, x * z2
    yy, yz, zz = y * y2, y * z2, z * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    sx, sy, sz = scale
    return [
        [(1 - (yy + zz)) * sx, (xy - wz) * sy, (xz + wy) * sz, position[0]],
        [(xy + wz) * sx, (1 - (xx + zz)) * sy, (yz - wx) * sz, position[1]],
        [(xz - wy) * sx, (yz + wx) * sy, (1 - (xx + yy)) * sz, position[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def node_matrix(node):
    """The local matrix of a scene description node."""
    rotation = node.get("rotation", [0, 0, 0])
    q = quaternion_from_euler(rotation[0], rotation[1], rotation[2], node.get("rotation_order", "XYZ"))
    return compose(node.get("position", [0, 0, 0]), q, node.get("scale", [1, 1, 1]))


def transform_point(m, p):
    return [m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3],
            m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3],
            m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3]]


def normal_matrix(m):
    """Inverse transpose of the upper 3x3 (None when singular)."""
    a, b, c = m[0][0], m[0][1], m[0][2]
    d, e, f = m[1][0], m[1][1], m[1][2]
    g, h, i = m[2][0], m[2][1], m[2][2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if det == 0:
        return None
    # inverse = adj / det; transpose of inverse = cofactor matrix / det
    return [
        [(e * i - f * h) / det, -(d * i - f * g) / det, (d * h - e * g) / det],
        [-(b * i - c * h) / det, (a * i - c * g) / det, -(a * h - b * g) / det],
        [(b * f - c * e) / det, -(a * f - c * d) / det, (a * e - b * d) / det],
    ]


def transform_normal(nm, n):
    if nm is None:
        return list(n)
    v = [nm[0][0] * n[0] + nm[0][1] * n[1] + nm[0][2] * n[2],
         nm[1][0] * n[0] + nm[1][1] * n[1] + nm[1][2] * n[2],
         nm[2][0] * n[0] + nm[2][1] * n[1] + nm[2][2] * n[2]]
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1
    return [v[0] / length, v[1] / length, v[2] / length]
