"""The bits of three.js maths the adapters use (perspective projection).

A line-by-line port of three.js r179 (src/math/Vector3.js, Matrix4.js,
Quaternion.js, MathUtils.js, core/Object3D.js, cameras/Camera.js and
cameras/PerspectiveCamera.js), restricted to what
AdapterBase._applyPerspective and _reversePerspective call. JavaScript
numbers are IEEE doubles like Python floats, and the operations are done
in the same order, so the results match the TypeScript bit for bit
(save for the last ulp of Math.tan, which may differ between V8 and libm).
"""

import math


class MathUtils:
    DEG2RAD = math.pi / 180
    RAD2DEG = 180 / math.pi

    @staticmethod
    def deg_to_rad(degrees):
        return degrees * MathUtils.DEG2RAD

    @staticmethod
    def rad_to_deg(radians):
        return radians * MathUtils.RAD2DEG


class Vector3:
    __slots__ = ("x", "y", "z")
    is_vector3 = True

    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    def set(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        return self

    def clone(self):
        return Vector3(self.x, self.y, self.z)

    def copy(self, v):
        self.x = v.x
        self.y = v.y
        self.z = v.z
        return self

    def add(self, v):
        self.x += v.x
        self.y += v.y
        self.z += v.z
        return self

    def sub(self, v):
        self.x -= v.x
        self.y -= v.y
        self.z -= v.z
        return self

    def sub_vectors(self, a, b):
        self.x = a.x - b.x
        self.y = a.y - b.y
        self.z = a.z - b.z
        return self

    def multiply_scalar(self, scalar):
        self.x *= scalar
        self.y *= scalar
        self.z *= scalar
        return self

    def divide_scalar(self, scalar):
        return self.multiply_scalar(_div(1, scalar))

    def apply_matrix4(self, m):
        x, y, z = self.x, self.y, self.z
        e = m.elements
        w = _div(1, e[3] * x + e[7] * y + e[11] * z + e[15])
        self.x = (e[0] * x + e[4] * y + e[8] * z + e[12]) * w
        self.y = (e[1] * x + e[5] * y + e[9] * z + e[13]) * w
        self.z = (e[2] * x + e[6] * y + e[10] * z + e[14]) * w
        return self

    def project(self, camera):
        return self.apply_matrix4(camera.matrix_world_inverse).apply_matrix4(camera.projection_matrix)

    def unproject(self, camera):
        return self.apply_matrix4(camera.projection_matrix_inverse).apply_matrix4(camera.matrix_world)

    def set_from_matrix_position(self, m):
        e = m.elements
        self.x = e[12]
        self.y = e[13]
        self.z = e[14]
        return self

    def length_sq(self):
        return self.x * self.x + self.y * self.y + self.z * self.z

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalize(self):
        return self.divide_scalar(self.length() or 1)

    def cross_vectors(self, a, b):
        ax, ay, az = a.x, a.y, a.z
        bx, by, bz = b.x, b.y, b.z
        self.x = ay * bz - az * by
        self.y = az * bx - ax * bz
        self.z = ax * by - ay * bx
        return self

    def to_array(self):
        return [self.x, self.y, self.z]

    def __repr__(self):
        return "Vector3(%r, %r, %r)" % (self.x, self.y, self.z)


class Quaternion:
    __slots__ = ("_x", "_y", "_z", "_w")

    def __init__(self, x=0, y=0, z=0, w=1):
        self._x = x
        self._y = y
        self._z = z
        self._w = w

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def z(self):
        return self._z

    @property
    def w(self):
        return self._w

    def set_from_rotation_matrix(self, m):
        # http://www.euclideanspace.com/maths/geometry/rotations/conversions/matrixToQuaternion/index.htm
        # assumes the upper 3x3 of m is a pure rotation matrix (i.e, unscaled)
        te = m.elements
        m11, m12, m13 = te[0], te[4], te[8]
        m21, m22, m23 = te[1], te[5], te[9]
        m31, m32, m33 = te[2], te[6], te[10]
        trace = m11 + m22 + m33

        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            self._w = 0.25 / s
            self._x = (m32 - m23) * s
            self._y = (m13 - m31) * s
            self._z = (m21 - m12) * s
        elif m11 > m22 and m11 > m33:
            s = 2.0 * math.sqrt(1.0 + m11 - m22 - m33)
            self._w = (m32 - m23) / s
            self._x = 0.25 * s
            self._y = (m12 + m21) / s
            self._z = (m13 + m31) / s
        elif m22 > m33:
            s = 2.0 * math.sqrt(1.0 + m22 - m11 - m33)
            self._w = (m13 - m31) / s
            self._x = (m12 + m21) / s
            self._y = 0.25 * s
            self._z = (m23 + m32) / s
        else:
            s = 2.0 * math.sqrt(1.0 + m33 - m11 - m22)
            self._w = (m21 - m12) / s
            self._x = (m13 + m31) / s
            self._y = (m23 + m32) / s
            self._z = 0.25 * s
        return self


class Matrix4:
    """A 4x4 matrix, elements in column-major order as in three.js."""

    __slots__ = ("elements",)

    def __init__(self):
        self.elements = [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ]

    def set(self, n11, n12, n13, n14, n21, n22, n23, n24,
            n31, n32, n33, n34, n41, n42, n43, n44):
        te = self.elements
        te[0] = n11; te[4] = n12; te[8] = n13; te[12] = n14  # noqa: E702
        te[1] = n21; te[5] = n22; te[9] = n23; te[13] = n24  # noqa: E702
        te[2] = n31; te[6] = n32; te[10] = n33; te[14] = n34  # noqa: E702
        te[3] = n41; te[7] = n42; te[11] = n43; te[15] = n44  # noqa: E702
        return self

    def identity(self):
        return self.set(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)

    def clone(self):
        m = Matrix4()
        m.elements = list(self.elements)
        return m

    def copy(self, m):
        self.elements[:] = m.elements
        return self

    def compose(self, position, quaternion, scale):
        te = self.elements

        x, y, z, w = quaternion._x, quaternion._y, quaternion._z, quaternion._w
        x2, y2, z2 = x + x, y + y, z + z
        xx, xy, xz = x * x2, x * y2, x * z2
        yy, yz, zz = y * y2, y * z2, z * z2
        wx, wy, wz = w * x2, w * y2, w * z2

        sx, sy, sz = scale.x, scale.y, scale.z

        te[0] = (1 - (yy + zz)) * sx
        te[1] = (xy + wz) * sx
        te[2] = (xz - wy) * sx
        te[3] = 0

        te[4] = (xy - wz) * sy
        te[5] = (1 - (xx + zz)) * sy
        te[6] = (yz + wx) * sy
        te[7] = 0

        te[8] = (xz + wy) * sz
        te[9] = (yz - wx) * sz
        te[10] = (1 - (xx + yy)) * sz
        te[11] = 0

        te[12] = position.x
        te[13] = position.y
        te[14] = position.z
        te[15] = 1

        return self

    def look_at(self, eye, target, up):
        te = self.elements

        _z = Vector3().sub_vectors(eye, target)

        if _z.length_sq() == 0:
            # eye and target are in the same position
            _z.z = 1

        _z.normalize()
        _x = Vector3().cross_vectors(up, _z)

        if _x.length_sq() == 0:
            # up and z are parallel
            if abs(up.z) == 1:
                _z.x += 0.0001
            else:
                _z.z += 0.0001

            _z.normalize()
            _x.cross_vectors(up, _z)

        _x.normalize()
        _y = Vector3().cross_vectors(_z, _x)

        te[0] = _x.x; te[4] = _y.x; te[8] = _z.x  # noqa: E702
        te[1] = _x.y; te[5] = _y.y; te[9] = _z.y  # noqa: E702
        te[2] = _x.z; te[6] = _y.z; te[10] = _z.z  # noqa: E702

        return self

    def multiply_matrices(self, a, b):
        ae = a.elements
        be = b.elements
        te = self.elements

        a11, a12, a13, a14 = ae[0], ae[4], ae[8], ae[12]
        a21, a22, a23, a24 = ae[1], ae[5], ae[9], ae[13]
        a31, a32, a33, a34 = ae[2], ae[6], ae[10], ae[14]
        a41, a42, a43, a44 = ae[3], ae[7], ae[11], ae[15]

        b11, b12, b13, b14 = be[0], be[4], be[8], be[12]
        b21, b22, b23, b24 = be[1], be[5], be[9], be[13]
        b31, b32, b33, b34 = be[2], be[6], be[10], be[14]
        b41, b42, b43, b44 = be[3], be[7], be[11], be[15]

        te[0] = a11 * b11 + a12 * b21 + a13 * b31 + a14 * b41
        te[4] = a11 * b12 + a12 * b22 + a13 * b32 + a14 * b42
        te[8] = a11 * b13 + a12 * b23 + a13 * b33 + a14 * b43
        te[12] = a11 * b14 + a12 * b24 + a13 * b34 + a14 * b44

        te[1] = a21 * b11 + a22 * b21 + a23 * b31 + a24 * b41
        te[5] = a21 * b12 + a22 * b22 + a23 * b32 + a24 * b42
        te[9] = a21 * b13 + a22 * b23 + a23 * b33 + a24 * b43
        te[13] = a21 * b14 + a22 * b24 + a23 * b34 + a24 * b44

        te[2] = a31 * b11 + a32 * b21 + a33 * b31 + a34 * b41
        te[6] = a31 * b12 + a32 * b22 + a33 * b32 + a34 * b42
        te[10] = a31 * b13 + a32 * b23 + a33 * b33 + a34 * b43
        te[14] = a31 * b14 + a32 * b24 + a33 * b34 + a34 * b44

        te[3] = a41 * b11 + a42 * b21 + a43 * b31 + a44 * b41
        te[7] = a41 * b12 + a42 * b22 + a43 * b32 + a44 * b42
        te[11] = a41 * b13 + a42 * b23 + a43 * b33 + a44 * b43
        te[15] = a41 * b14 + a42 * b24 + a43 * b34 + a44 * b44

        return self

    def multiply(self, m):
        return self.multiply_matrices(self, m)

    def premultiply(self, m):
        return self.multiply_matrices(m, self)

    def invert(self):
        # based on http://www.euclideanspace.com/maths/algebra/matrix/functions/inverse/fourD/index.htm
        te = self.elements
        n11, n21, n31, n41 = te[0], te[1], te[2], te[3]
        n12, n22, n32, n42 = te[4], te[5], te[6], te[7]
        n13, n23, n33, n43 = te[8], te[9], te[10], te[11]
        n14, n24, n34, n44 = te[12], te[13], te[14], te[15]

        t11 = n23 * n34 * n42 - n24 * n33 * n42 + n24 * n32 * n43 - n22 * n34 * n43 - n23 * n32 * n44 + n22 * n33 * n44
        t12 = n14 * n33 * n42 - n13 * n34 * n42 - n14 * n32 * n43 + n12 * n34 * n43 + n13 * n32 * n44 - n12 * n33 * n44
        t13 = n13 * n24 * n42 - n14 * n23 * n42 + n14 * n22 * n43 - n12 * n24 * n43 - n13 * n22 * n44 + n12 * n23 * n44
        t14 = n14 * n23 * n32 - n13 * n24 * n32 - n14 * n22 * n33 + n12 * n24 * n33 + n13 * n22 * n34 - n12 * n23 * n34

        det = n11 * t11 + n21 * t12 + n31 * t13 + n41 * t14

        if det == 0:
            return self.set(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

        det_inv = 1 / det

        te[0] = t11 * det_inv
        te[1] = (n24 * n33 * n41 - n23 * n34 * n41 - n24 * n31 * n43 + n21 * n34 * n43 + n23 * n31 * n44 - n21 * n33 * n44) * det_inv
        te[2] = (n22 * n34 * n41 - n24 * n32 * n41 + n24 * n31 * n42 - n21 * n34 * n42 - n22 * n31 * n44 + n21 * n32 * n44) * det_inv
        te[3] = (n23 * n32 * n41 - n22 * n33 * n41 - n23 * n31 * n42 + n21 * n33 * n42 + n22 * n31 * n43 - n21 * n32 * n43) * det_inv

        te[4] = t12 * det_inv
        te[5] = (n13 * n34 * n41 - n14 * n33 * n41 + n14 * n31 * n43 - n11 * n34 * n43 - n13 * n31 * n44 + n11 * n33 * n44) * det_inv
        te[6] = (n14 * n32 * n41 - n12 * n34 * n41 - n14 * n31 * n42 + n11 * n34 * n42 + n12 * n31 * n44 - n11 * n32 * n44) * det_inv
        te[7] = (n12 * n33 * n41 - n13 * n32 * n41 + n13 * n31 * n42 - n11 * n33 * n42 - n12 * n31 * n43 + n11 * n32 * n43) * det_inv

        te[8] = t13 * det_inv
        te[9] = (n14 * n23 * n41 - n13 * n24 * n41 - n14 * n21 * n43 + n11 * n24 * n43 + n13 * n21 * n44 - n11 * n23 * n44) * det_inv
        te[10] = (n12 * n24 * n41 - n14 * n22 * n41 + n14 * n21 * n42 - n11 * n24 * n42 - n12 * n21 * n44 + n11 * n22 * n44) * det_inv
        te[11] = (n13 * n22 * n41 - n12 * n23 * n41 - n13 * n21 * n42 + n11 * n23 * n42 + n12 * n21 * n43 - n11 * n22 * n43) * det_inv

        te[12] = t14 * det_inv
        te[13] = (n13 * n24 * n31 - n14 * n23 * n31 + n14 * n21 * n33 - n11 * n24 * n33 - n13 * n21 * n34 + n11 * n23 * n34) * det_inv
        te[14] = (n14 * n22 * n31 - n12 * n24 * n31 - n14 * n21 * n32 + n11 * n24 * n32 + n12 * n21 * n34 - n11 * n22 * n34) * det_inv
        te[15] = (n12 * n23 * n31 - n13 * n22 * n31 + n13 * n21 * n32 - n11 * n23 * n32 - n12 * n21 * n33 + n11 * n22 * n33) * det_inv

        return self

    def make_perspective(self, left, right, top, bottom, near, far):
        # WebGLCoordinateSystem, no reversed depth (the defaults).
        te = self.elements
        x = _div(2 * near, right - left)
        y = _div(2 * near, top - bottom)

        a = _div(right + left, right - left)
        b = _div(top + bottom, top - bottom)

        c = _div(-(far + near), far - near)
        d = _div(-2 * far * near, far - near)

        te[0] = x; te[4] = 0; te[8] = a; te[12] = 0  # noqa: E702
        te[1] = 0; te[5] = y; te[9] = b; te[13] = 0  # noqa: E702
        te[2] = 0; te[6] = 0; te[10] = c; te[14] = d  # noqa: E702
        te[3] = 0; te[7] = 0; te[11] = -1; te[15] = 0  # noqa: E702

        return self


class Object3D:
    """The transform part of three.js's Object3D (no parent, no children)."""

    DEFAULT_UP = (0, 1, 0)

    def __init__(self):
        self.parent = None
        self.up = Vector3(*Object3D.DEFAULT_UP)
        self.position = Vector3()
        self.quaternion = Quaternion()
        self.scale = Vector3(1, 1, 1)
        self.matrix = Matrix4()
        self.matrix_world = Matrix4()
        self.matrix_auto_update = True
        self.matrix_world_auto_update = True
        self.matrix_world_needs_update = False
        self.is_camera = False

    def look_at(self, x, y=None, z=None):
        # This method does not support objects having non-uniformly-scaled parent(s)
        if isinstance(x, Vector3):
            target = Vector3().copy(x)
        else:
            target = Vector3(x, y, z)

        self.update_world_matrix(True, False)

        position = Vector3().set_from_matrix_position(self.matrix_world)

        m1 = Matrix4()
        if self.is_camera:
            m1.look_at(position, target, self.up)
        else:
            m1.look_at(target, position, self.up)

        self.quaternion.set_from_rotation_matrix(m1)

    def update_matrix(self):
        self.matrix.compose(self.position, self.quaternion, self.scale)
        self.matrix_world_needs_update = True

    def update_matrix_world(self, force=False):
        if self.matrix_auto_update:
            self.update_matrix()

        if self.matrix_world_needs_update or force:
            if self.matrix_world_auto_update:
                self.matrix_world.copy(self.matrix)
            self.matrix_world_needs_update = False

    def update_world_matrix(self, update_parents, update_children):
        if self.matrix_auto_update:
            self.update_matrix()
        if self.matrix_world_auto_update:
            self.matrix_world.copy(self.matrix)


class Camera(Object3D):
    def __init__(self):
        super().__init__()
        self.is_camera = True
        self.matrix_world_inverse = Matrix4()
        self.projection_matrix = Matrix4()
        self.projection_matrix_inverse = Matrix4()

    def update_matrix_world(self, force=False):
        super().update_matrix_world(force)
        self.matrix_world_inverse.copy(self.matrix_world).invert()

    def update_world_matrix(self, update_parents, update_children):
        super().update_world_matrix(update_parents, update_children)
        self.matrix_world_inverse.copy(self.matrix_world).invert()


class PerspectiveCamera(Camera):
    def __init__(self, fov=50, aspect=1, near=0.1, far=2000):
        super().__init__()
        self.fov = fov
        self.zoom = 1
        self.near = near
        self.far = far
        self.focus = 10
        self.aspect = aspect
        self.film_gauge = 35  # width of the film (default in millimeters)
        self.film_offset = 0  # horizontal film offset (same unit as gauge)
        self.update_projection_matrix()

    def get_film_width(self):
        # film not completely covered in portrait format (aspect < 1)
        return self.film_gauge * min(self.aspect, 1)

    def update_projection_matrix(self):
        near = self.near
        top = near * math.tan(MathUtils.DEG2RAD * 0.5 * self.fov) / self.zoom
        height = 2 * top
        width = self.aspect * height
        left = -0.5 * width

        skew = self.film_offset
        if skew != 0:
            left += near * skew / self.get_film_width()

        self.projection_matrix.make_perspective(left, left + width, top, top - height, near, self.far)
        self.projection_matrix_inverse.copy(self.projection_matrix).invert()


def _div(a, b):
    """JavaScript division: x / 0 is +-Infinity (or NaN), not an error."""
    try:
        return a / b
    except ZeroDivisionError:
        if a == 0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
