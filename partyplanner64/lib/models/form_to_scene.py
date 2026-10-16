"""Converts an unpacked FORM into a scene description for three.js.

This replaces FormToThreeJs.ts and three-support/Geometry.ts: the browser
used to build the THREE objects itself; now Python builds everything the
browser needs (static/js/lib/model3d.js turns it into the same THREE objects).

form_to_scene returns a JSON-serializable dict:

    {
      "root": node or None,
      "geometries": [geometry, ...],
      "materials": [material, ...],
      "textures": [texture, ...],
      "camera": {"fov", "near", "far", "position": [x, y, z], "look_at": [x, y, z] or None},
      "background": 0xRRGGBB,
      "options": {"show_textures", "show_wireframe", "show_vertex_normals", "use_form_camera"},
    }

A node is {"type": "object", "name", "position", "rotation" (radians),
"rotation_order": "ZYX", "scale", "children": [...]}, or a leaf:
{"type": "mesh", "geometry": i} (drawn with all the materials, as a
multi-material THREE.Mesh), {"type": "wireframe", "geometry": i, "color",
"linewidth"} (LineSegments of an EdgesGeometry), or {"type": "normals",
"geometry": i, "size": 8, "color": 0x00FF00} (a VertexNormalsHelper).

A geometry is non-indexed, as Geometry.toBufferGeometry made it: "position",
"normal", "color" (linear RGB, as THREE.Color stores colors), "uv" (float32
arrays, base64 of little-endian float32 when binary, else lists), "count"
(vertices) and "groups" ([{"start", "count", "material_index"}], the index
into "materials", None when FormToThreeJs gave none).

A material is {"type": "basic", "vertex_colors": True} and, for textured
ones, "map": texture index and "alpha_test": 0.5. A texture is {"image": PNG
data URL, "width", "height", "flip_y": False, "wrap_s", "wrap_t" (three.js
constant names), "mag_filter", "min_filter", "color_space": "srgb"}.
"""

import base64
import logging
import math
import struct

from ..utils.debug import hexstr
from ..utils.number import degrees_to_radians
from .form import FORM

logger = logging.getLogger("partyplanner64")

DEFAULT_CAMERA_Z = 500


def _srgb_to_linear(c):
    return c * 0.0773993808 if c < 0.04045 else math.pow(c * 0.9478672986 + 0.0521327014, 2.4)


def color_hex_to_linear(hex_):
    """new THREE.Color(hex): sRGB hex to linear [r, g, b] (three.js color management)."""
    hex_ = int(hex_)
    return [_srgb_to_linear(((hex_ >> 16) & 0xFF) / 255),
            _srgb_to_linear(((hex_ >> 8) & 0xFF) / 255),
            _srgb_to_linear((hex_ & 0xFF) / 255)]


def linear_to_srgb(c):
    if c < 0.0031308:
        return c * 12.92
    return 1.055 * math.pow(c, 0.41666) - 0.055


def invert_color(hex_):
    r = 255 - ((hex_ >> 16) & 0xFF)
    g = 255 - ((hex_ >> 8) & 0xFF)
    b = 255 - (hex_ & 0xFF)
    return (r << 16) | (g << 8) | b


def encode_floats(values):
    """Base64 of little-endian float32 values."""
    return base64.b64encode(struct.pack("<%df" % len(values), *values)).decode("ascii")


def decode_floats(value):
    """The floats of a geometry attribute (base64 string or list)."""
    if isinstance(value, str):
        raw = base64.b64decode(value)
        return list(struct.unpack("<%df" % (len(raw) // 4), raw))
    return list(value)


def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


class _Geometry:
    """The legacy THREE.Geometry, as much as FormToThreeJs used of it."""

    def __init__(self):
        self.vertices = []
        self.faces = []  # dicts: a, b, c, vertex_normals, material_index, color, vertex_colors
        self.face_vertex_uvs = []

    def to_buffer_geometry(self, binary):
        """Geometry.toBufferGeometry (via DirectGeometry.fromGeometry)."""
        positions, normals, colors, uvs = [], [], [], []
        for i, face in enumerate(self.faces):
            for idx in (face["a"], face["b"], face["c"]):
                positions.extend(self.vertices[idx])
            vertex_normals = face["vertex_normals"]
            if len(vertex_normals) == 3:
                for n in vertex_normals:
                    normals.extend(n)
            else:
                normals.extend([0, 0, 0] * 3)
            vertex_colors = face["vertex_colors"]
            if len(vertex_colors) == 3:
                for c in vertex_colors:
                    # (A null color threw in the TypeScript; it's white here.)
                    colors.extend(c if c is not None else [1.0, 1.0, 1.0])
            else:
                colors.extend(face["color"] * 3)
            vertex_uvs = self.face_vertex_uvs[i] if i < len(self.face_vertex_uvs) else None
            if vertex_uvs is not None:
                for uv in vertex_uvs:
                    uvs.extend(uv)
            else:
                uvs.extend([0, 0] * 3)

        # computeGroups
        groups = []
        group = None
        material_index = None  # (undefined: faces without a material index start no group)
        for i, face in enumerate(self.faces):
            if face["material_index"] != material_index:
                material_index = face["material_index"]
                if group is not None:
                    group["count"] = i * 3 - group["start"]
                    groups.append(group)
                group = {"start": i * 3, "count": -1, "material_index": material_index}
        if group is not None:
            group["count"] = len(self.faces) * 3 - group["start"]
            groups.append(group)

        positions = [_f32(v) for v in positions]
        normals = [_f32(v) for v in normals]
        colors = [_f32(v) for v in colors]
        uvs = [_f32(v) for v in uvs]
        enc = encode_floats if binary else (lambda v: v)
        return {
            "count": len(positions) // 3,
            "position": enc(positions),
            "normal": enc(normals),
            "color": enc(colors),
            "uv": enc(uvs),
            "groups": groups,
        }


class FormToScene:
    """Converts extracted FORM data into a scene description (FormToThreeJs)."""

    def __init__(self, bg_color=0x000000, show_textures=True, show_wireframe=False,
                 show_vertex_normals=False, use_form_camera=False, binary=True):
        self.bg_color = bg_color
        self.show_textures = show_textures
        self.show_wireframe = show_wireframe
        self.show_vertex_normals = show_vertex_normals
        self.use_form_camera = use_form_camera
        self.binary = binary
        self._geometries = []
        self._textures = []

    def create_model(self, form):
        self._geometries = []
        self._textures = []
        materials = self._parse_materials(form)
        root = self._parse_form(form)
        return {
            "root": root,
            "geometries": self._geometries,
            "materials": materials,
            "textures": self._textures,
            "camera": self.create_camera(form),
            "background": self.bg_color,
            "options": {
                "show_textures": self.show_textures,
                "show_wireframe": self.show_wireframe,
                "show_vertex_normals": self.show_vertex_normals,
                "use_form_camera": self.use_form_camera,
            },
        }

    def _parse_form(self, form):
        child_objs = self._parse_form_obj(form, 0)
        if len(child_objs) != 1:
            logger.warning("Expected 1 return object from _parseForm, got %d", len(child_objs))
        return child_objs[0] if child_objs else None

    def _parse_form_obj(self, form, obj_index):
        objs = FORM.get_by_global_index(form, "OBJ1", obj_index)
        if objs is None:
            if obj_index == 0:
                # mp2 62/2 doesn't have 0 obj?
                objs = form["OBJ1"][0]["parsed"]["objects"][0]
                logger.warning("Using first object rather than global index 0 object")

            if not objs:
                raise ValueError("Attempted to get unavailable OBJ %s" % obj_index)

        if not isinstance(objs, list):
            objs = [objs]

        new_objs = []
        for obj in objs:
            obj_type = obj["obj_type"]
            if obj_type == 0x3D:
                # Just references other objects, can transform them.
                new_obj = self._create_object3d_from_obj1_entry(obj)
                for child in obj["children"]:
                    new_obj["children"].extend(self._parse_form_obj(form, child))
                new_objs.append(new_obj)
            elif obj_type == 0x10:
                # References a SKL1, which will point back to other objects.
                new_obj = self._create_object3d_from_obj1_entry(obj)
                new_obj["children"].append(self._parse_form_skl(form, obj["skeleton_global_index"]))
                new_objs.append(new_obj)
            elif obj_type == 0x3A:
                new_obj = self._create_object3d_from_obj1_entry(obj)

                geometry = _Geometry()
                faces = form["FAC1"][0]["parsed"]["faces"]
                for f in range(obj["face_index"], obj["face_index"] + obj["face_count"]):
                    self._populate_geometry_with_face(form, geometry, faces[f])

                self._geometries.append(geometry.to_buffer_geometry(self.binary))
                geometry_index = len(self._geometries) - 1

                if self.show_textures:
                    new_obj["children"].append({"type": "mesh", "geometry": geometry_index})

                if self.show_wireframe:
                    new_obj["children"].append({
                        "type": "wireframe",
                        "geometry": geometry_index,
                        "color": invert_color(self.bg_color),
                        "linewidth": 2 if self.show_textures else 1,
                    })

                if self.show_vertex_normals:
                    new_obj["children"].append({
                        "type": "normals", "geometry": geometry_index, "size": 8, "color": 0x00FF00,
                    })

                new_objs.append(new_obj)

        return new_objs

    def _create_object3d_from_obj1_entry(self, obj):
        # Name the nodes for animation - see mtnx_to_animation
        name = self._get_obj_name_from_id(obj["global_index"]) if "global_index" in obj else ""
        return {
            "type": "object",
            "name": name,
            "position": [obj["pos_x"], obj["pos_y"], obj["pos_z"]],
            "rotation": [degrees_to_radians(obj["rot_x"]), degrees_to_radians(obj["rot_y"]),
                         degrees_to_radians(obj["rot_z"])],
            "rotation_order": "ZYX",
            "scale": [obj["scale_x"], obj["scale_y"], obj["scale_z"]],
            "children": [],
        }

    @staticmethod
    def _get_obj_name_from_id(id_):
        return hexstr(id_)

    def _parse_form_skl(self, form, skl1_global_index):
        skl_match = FORM.get_by_global_index(form, "SKL1", skl1_global_index)
        if skl_match is None or isinstance(skl_match, list):
            raise ValueError("Unexpected SKL1 search result")
        return self._parse_form_skl_node(form, skl_match["skls"], 0)

    def _parse_form_skl_node(self, form, skls, index):
        skl = skls[index]
        skl_obj = self._create_object3d_from_obj1_entry(skl)

        skl_obj["children"].extend(self._parse_form_obj(form, skl["obj_global_index"]))

        if skl["is_parent_node"]:
            current_child_index = index + 1
            while current_child_index:
                child_skl = skls[current_child_index]
                skl_obj["children"].append(self._parse_form_skl_node(form, skls, current_child_index))
                if child_skl["next_sibling_relative_index"]:
                    current_child_index += child_skl["next_sibling_relative_index"]
                else:
                    break

        return skl_obj

    def _populate_geometry_with_face(self, form, geometry, face):
        vtx_entries = face["vtx_entries"]
        if not vtx_entries:
            return

        vtx1 = form["VTX1"][0]["parsed"]
        scale = vtx1["scale"]
        vertices = vtx1["vertices"]

        vtx_indices = []
        for i in range(3):
            vtx_indices.append(len(geometry.vertices))
            geometry.vertices.append(self._make_vertex(vertices[vtx_entries[i]["vertex_index"]], scale))
        if len(vtx_entries) == 4:
            for i in (0, 2, 3):
                vtx_indices.append(len(geometry.vertices))
                geometry.vertices.append(
                    self._make_vertex(vertices[vtx_entries[i]["vertex_index"]], scale))

        if len(vtx_entries) == 3:
            self._add_face(geometry, form, face, vtx_indices[0:3], vtx_entries[0:3])
        elif len(vtx_entries) == 4:
            self._add_face(geometry, form, face, vtx_indices[0:3], vtx_entries[0:3])
            self._add_face(geometry, form, face, vtx_indices[3:6],
                           [vtx_entries[0], vtx_entries[2], vtx_entries[3]])

    def _add_face(self, geometry, form, face, indices, vtx_entries):
        color = self._get_color_bytes(form, face)
        geometry.faces.append({
            "a": indices[0], "b": indices[1], "c": indices[2],
            "vertex_normals": [self._make_vertex_normal(form, e["vertex_index"]) for e in vtx_entries],
            "material_index": self._get_material_index(face),
            # new THREE.Color(undefined) is white.
            "color": color_hex_to_linear(color) if color is not None else [1.0, 1.0, 1.0],
            "vertex_colors": self._make_vertex_colors(form, face, vtx_entries),
        })
        geometry.face_vertex_uvs.append([[e["u"], e["v"]] for e in vtx_entries])

    def _parse_materials(self, form):
        materials = [
            {"type": "basic", "vertex_colors": True},
            {"type": "basic", "vertex_colors": True},
        ]

        if form.get("BMP1"):
            if form.get("ATR1") and form["ATR1"][0]:
                for atr in form["ATR1"][0]["parsed"]["atrs"]:
                    bmp = FORM.get_by_global_index(form, "BMP1", atr["bmp_global_index"])
                    if bmp is None or isinstance(bmp, list):
                        logger.warning("Unexpected bitmap result from global index lookup")
                        continue
                    materials.append(self._create_texture_material(atr, bmp))
            else:
                logger.warning("BMPs, but no ATRs")

        return materials

    def _create_texture_material(self, atr, bmp):
        from ..utils.canvas import rgba_to_data_url

        width = bmp["width"]
        height = bmp["height"]
        size = width * height * 4
        src = bytes(bmp.get("src") or b"")[:size]
        src += bytes(size - len(src))
        if width and height:
            data_url = rgba_to_data_url(src, width, height)
        else:
            data_url = rgba_to_data_url(bytes(4), 1, 1)
        self._textures.append({
            "image": data_url,
            "width": width,
            "height": height,
            "flip_y": False,
            "wrap_s": self._get_wrapping_behavior(atr["x_behavior"]),
            "wrap_t": self._get_wrapping_behavior(atr["y_behavior"]),
            "mag_filter": "LinearFilter",
            "min_filter": "LinearMipmapLinearFilter",
            "color_space": "srgb",
        })
        return {
            "type": "basic",
            "alpha_test": 0.5,
            "map": len(self._textures) - 1,
            # transparent: True,
            "vertex_colors": True,
        }

    @staticmethod
    def _get_wrapping_behavior(behavior):
        if behavior == 0x2C:
            return "MirroredRepeatWrapping"
        if behavior == 0x2D:
            return "RepeatWrapping"
        if behavior == 0x2E:
            return "ClampToEdgeWrapping"  # default
        logger.warning("Unknown behavior %s", hexstr(behavior))
        return "ClampToEdgeWrapping"  # default

    @staticmethod
    def _make_vertex(vtx, scale):
        return [vtx["x"] * scale, vtx["y"] * scale, vtx["z"] * scale]

    @staticmethod
    def _make_vertex_normal(form, vtx_index):
        vtx = form["VTX1"][0]["parsed"]["vertices"][vtx_index]
        x = vtx["normal_x"] / (127 + (1 if vtx["normal_x"] < 0 else 0))
        y = vtx["normal_y"] / (127 + (1 if vtx["normal_y"] < 0 else 0))
        z = vtx["normal_z"] / (127 + (1 if vtx["normal_z"] < 0 else 0))
        length = math.sqrt(x * x + y * y + z * z) or 1
        return [x / length, y / length, z / length]

    @staticmethod
    def _get_material_index(face):
        if face["atr_index"] >= 0 or face["mystery3"] == 0x36:
            # Face colors, or maybe bitmap
            # If it is 0xFFFF (-1) -> THREE.FaceColors material
            # If greater, it'll be a bitmap material
            return face["atr_index"] + 2
        elif face["mystery3"] == 0x37:
            # Vertex colors?
            return 0  # Vertex colors
        return None

    def _get_color_bytes(self, form, face):
        if face["mystery3"] == 0x36:
            return self._get_color_from_material(form, face["material_index"])
        elif face["mystery3"] == 0x37:
            # Vertex colors?
            return 0xFFFC00  # Puke green, shouldn't see this

        logger.debug("Could not determine color for face")
        return None

    @staticmethod
    def _get_color_from_material(form, material_index):
        color_index = None
        mat1 = form.get("MAT1")
        if mat1 and mat1[0] and mat1[0].get("parsed"):
            materials = mat1[0]["parsed"]["materials"]
            # (A missing material threw in the TypeScript.)
            if 0 <= material_index < len(materials):
                color_index = materials[material_index]["color_index"]
                col1 = form.get("COL1")
                if col1 and col1[0] and col1[0].get("parsed") is not None:
                    colors = col1[0]["parsed"]
                    if 0 <= color_index < len(colors):
                        return colors[color_index] >> 8

        logger.debug("Could not find color %s specified by material %s", color_index, material_index)
        return 0xFFFC00  # Puke green

    def _make_vertex_colors(self, form, face, vtx_entries):
        if face["mystery3"] != 0x37:
            return []
        return [self._make_vertex_color(form, e) for e in vtx_entries]

    def _make_vertex_color(self, form, vtx_entry):
        if vtx_entry["material_index"] < 0:
            return None
        return color_hex_to_linear(self._get_color_from_material(form, vtx_entry["material_index"]))

    def create_camera(self, form):
        """The PerspectiveCamera FormToThreeJs.createCamera made (the aspect is the viewer's)."""
        camera = {"fov": 75, "near": 1, "far": 999999, "position": [0, 0, DEFAULT_CAMERA_Z],
                  "look_at": None}
        if self.use_form_camera:
            camera_objs = FORM.get_objects_by_type(form, 0x61)
            if len(camera_objs) == 3:
                eye, interest = camera_objs[0], camera_objs[1]
                camera["position"] = [eye["pos_x"], eye["pos_y"], eye["pos_z"]]
                camera["look_at"] = [interest["pos_x"], interest["pos_y"], interest["pos_z"]]
            else:
                logger.warning("Unexpected camera object count: %d", len(camera_objs))
        return camera


def form_to_scene(form, bg_color=0x000000, show_textures=True, show_wireframe=False,
                  show_vertex_normals=False, use_form_camera=False, binary=True):
    """Return the scene description (see the module docstring) of an unpacked FORM.

    Args:
        form: FORM.unpack's result (or the FORM file's bytes).
        bg_color: The viewer's background (the wireframe is drawn in its inverse).
        show_textures: Include the meshes.
        show_wireframe: Include wireframes.
        show_vertex_normals: Include vertex normal helpers.
        use_form_camera: Place the camera as the FORM's camera objects say.
        binary: Geometry attributes as base64 float32 (else lists of numbers).
    """
    if not isinstance(form, dict):
        form = FORM.unpack(form)
        if form is None:
            raise ValueError("Not a FORM file")
    converter = FormToScene(bg_color, show_textures, show_wireframe, show_vertex_normals,
                            use_form_camera, binary)
    return converter.create_model(form)
