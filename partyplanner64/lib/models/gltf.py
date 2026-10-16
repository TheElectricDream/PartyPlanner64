"""glTF 2.0 export of a scene description (replaces three's GLTFExporter use on the Models page).

scene_to_gltf(scene, glb=False) writes what GLTFExporter wrote for the
model FormToThreeJs built: the node hierarchy (names, translation, ZYX
rotation as a quaternion, scale), each mesh as one primitive per material
group (indices into shared POSITION/NORMAL/COLOR_0/TEXCOORD_0 accessors),
unlit materials (KHR_materials_unlit) with vertex colors, textures as PNG
images with their samplers, and alpha test as alphaMode MASK.
Wireframe and vertex normal helper nodes are left out.
"""

import base64
import json
import struct

from ..utils.canvas import data_url_to_bytes
from .form_to_scene import decode_floats
from .scene_math import quaternion_from_euler

_WRAPPING = {"MirroredRepeatWrapping": 33648, "RepeatWrapping": 10497, "ClampToEdgeWrapping": 33071}
_FILTERS = {"NearestFilter": 9728, "LinearFilter": 9729, "NearestMipmapNearestFilter": 9984,
            "LinearMipmapNearestFilter": 9985, "NearestMipmapLinearFilter": 9986,
            "LinearMipmapLinearFilter": 9987}
_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963
_FLOAT = 5126
_UNSIGNED_SHORT = 5123
_UNSIGNED_INT = 5125


class _Writer:
    def __init__(self, scene, glb):
        self.scene = scene
        self.glb = glb
        self.bin = bytearray()
        self.json = {
            "asset": {"version": "2.0", "generator": "PartyPlanner64"},
            "scene": 0,
            "scenes": [{"nodes": []}],
            "nodes": [],
        }
        self.material_map = {}
        self.texture_map = {}
        self.geometry_cache = {}

    def _list(self, key):
        return self.json.setdefault(key, [])

    def _buffer_view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        self.bin += data
        views = self._list("bufferViews")
        views.append(view)
        return len(views) - 1

    def _accessor(self, values, type_, components, minmax=False):
        data = struct.pack("<%df" % len(values), *values)
        accessor = {"bufferView": self._buffer_view(data, _ARRAY_BUFFER), "componentType": _FLOAT,
                    "count": len(values) // components, "type": type_}
        if minmax and values:
            accessor["min"] = [min(values[i::components]) for i in range(components)]
            accessor["max"] = [max(values[i::components]) for i in range(components)]
        accessors = self._list("accessors")
        accessors.append(accessor)
        return len(accessors) - 1

    def _indices(self, start, count):
        indices = list(range(start, start + count))
        if start + count <= 0xFFFF:
            data, component = struct.pack("<%dH" % count, *indices), _UNSIGNED_SHORT
        else:
            data, component = struct.pack("<%dI" % count, *indices), _UNSIGNED_INT
        accessors = self._list("accessors")
        accessors.append({"bufferView": self._buffer_view(data, _ELEMENT_ARRAY_BUFFER),
                          "componentType": component, "count": count, "type": "SCALAR",
                          "min": [start], "max": [start + count - 1]})
        return len(accessors) - 1

    def _texture(self, index):
        if index in self.texture_map:
            return self.texture_map[index]
        desc = self.scene["textures"][index]
        png = data_url_to_bytes(desc["image"])
        if self.glb:
            image = {"mimeType": "image/png", "bufferView": self._buffer_view(png)}
        else:
            image = {"mimeType": "image/png",
                     "uri": "data:image/png;base64," + base64.b64encode(png).decode("ascii")}
        images = self._list("images")
        images.append(image)
        samplers = self._list("samplers")
        samplers.append({
            "magFilter": _FILTERS.get(desc.get("mag_filter"), 9729),
            "minFilter": _FILTERS.get(desc.get("min_filter"), 9987),
            "wrapS": _WRAPPING.get(desc.get("wrap_s"), 33071),
            "wrapT": _WRAPPING.get(desc.get("wrap_t"), 33071),
        })
        textures = self._list("textures")
        textures.append({"sampler": len(samplers) - 1, "source": len(images) - 1})
        self.texture_map[index] = len(textures) - 1
        return self.texture_map[index]

    def _material(self, index):
        if index in self.material_map:
            return self.material_map[index]
        desc = self.scene["materials"][index]
        material = {
            "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.9},
            "extensions": {"KHR_materials_unlit": {}},
        }
        if desc.get("map") is not None:
            material["pbrMetallicRoughness"]["baseColorTexture"] = {
                "index": self._texture(desc["map"]), "texCoord": 0}
        if desc.get("alpha_test", 0) > 0:
            material["alphaMode"] = "MASK"
            material["alphaCutoff"] = desc["alpha_test"]
        used = self.json.setdefault("extensionsUsed", [])
        if "KHR_materials_unlit" not in used:
            used.append("KHR_materials_unlit")
        materials = self._list("materials")
        materials.append(material)
        self.material_map[index] = len(materials) - 1
        return self.material_map[index]

    def _mesh(self, geometry_index):
        if geometry_index in self.geometry_cache:
            return self.geometry_cache[geometry_index]
        geometry = self.scene["geometries"][geometry_index]
        mesh_index = None
        if geometry["count"] > 0:
            attributes = {"POSITION": self._accessor(decode_floats(geometry["position"]), "VEC3", 3,
                                                     True)}
            normals = decode_floats(geometry["normal"])
            if normals:
                attributes["NORMAL"] = self._accessor(normals, "VEC3", 3)
            colors = decode_floats(geometry["color"])
            if colors:
                attributes["COLOR_0"] = self._accessor(colors, "VEC3", 3)
            uvs = decode_floats(geometry["uv"])
            if uvs:
                attributes["TEXCOORD_0"] = self._accessor(uvs, "VEC2", 2)
            primitives = []
            for group in geometry["groups"]:
                material_index = group.get("material_index")
                # (GLTFExporter failed on groups without a material; they're skipped.)
                if material_index is None or not 0 <= material_index < len(self.scene["materials"]):
                    continue
                count = min(group["count"], geometry["count"] - group["start"])
                if count <= 0:
                    continue
                primitives.append({"mode": 4, "attributes": attributes,
                                   "indices": self._indices(group["start"], count),
                                   "material": self._material(material_index)})
            if primitives:
                meshes = self._list("meshes")
                meshes.append({"primitives": primitives})
                mesh_index = len(meshes) - 1
        self.geometry_cache[geometry_index] = mesh_index
        return mesh_index

    def node(self, desc):
        """Add a node (and its children); return its index or None."""
        node = {}
        if desc["type"] == "mesh":
            mesh = self._mesh(desc["geometry"])
            if mesh is None:
                return None
            node["mesh"] = mesh
        elif desc["type"] != "object":
            return None  # Wireframes and helpers aren't exported.
        else:
            if desc.get("name"):
                node["name"] = desc["name"]
            rotation = desc.get("rotation", [0, 0, 0])
            if any(rotation):
                node["rotation"] = quaternion_from_euler(
                    rotation[0], rotation[1], rotation[2], desc.get("rotation_order", "XYZ"))
            if any(desc.get("position", [0, 0, 0])):
                node["translation"] = list(desc["position"])
            if list(desc.get("scale", [1, 1, 1])) != [1, 1, 1]:
                node["scale"] = list(desc["scale"])
        nodes = self.json["nodes"]
        nodes.append(node)
        index = len(nodes) - 1
        children = [self.node(child) for child in desc.get("children", [])]
        children = [c for c in children if c is not None]
        if children:
            node["children"] = children
        return index

    def write(self):
        root = self.scene.get("root")
        if root is not None:
            index = self.node(root)
            if index is not None:
                self.json["scenes"][0]["nodes"].append(index)
        if self.bin:
            while len(self.bin) % 4:
                self.bin.append(0)
            buffer = {"byteLength": len(self.bin)}
            if not self.glb:
                buffer["uri"] = ("data:application/octet-stream;base64,"
                                 + base64.b64encode(bytes(self.bin)).decode("ascii"))
            self.json["buffers"] = [buffer]
        text = json.dumps(self.json, separators=(",", ":")).encode("utf-8")
        if not self.glb:
            return text
        while len(text) % 4:
            text += b" "
        chunks = struct.pack("<I4s", len(text), b"JSON") + text
        if self.bin:
            chunks += struct.pack("<I4s", len(self.bin), b"BIN\0") + bytes(self.bin)
        return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def scene_to_gltf(scene, glb=False):
    """Return a .gltf (JSON, buffers and images embedded as data URIs) or, with glb, a .glb file."""
    return _Writer(scene, glb).write()
