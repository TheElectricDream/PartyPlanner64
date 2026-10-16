"""Wavefront OBJ export of a scene description (stands in for the bundled ThreeJS-export-OBJ).

scene_to_obj flattens every mesh into world space (the node transforms
applied) and returns the .obj text (vertices with their vertex colors, as
"v x y z r g b" in sRGB, texture coordinates flipped to OBJ's bottom-up v,
normals, one usemtl per material group) and the .mtl text. scene_to_obj_zip
packs object.obj, material.mtl and the textures (PNG) into a .zip, as the
original packed its output with JSZip.
"""

import io
import zipfile

from ..utils.canvas import data_url_to_bytes
from .form_to_scene import decode_floats, linear_to_srgb
from .scene_math import IDENTITY, multiply, node_matrix, normal_matrix, transform_normal, \
    transform_point


def _fmt(x):
    text = "%.6f" % x
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _material_name(index):
    return "material_%d" % index


def _texture_name(index):
    return "texture_%d.png" % index


def scene_to_obj(scene):
    """Return (obj_text, mtl_text, textures) of a scene; textures maps file names to PNG bytes."""
    lines = ["# PartyPlanner64", "mtllib material.mtl"]
    used_materials = []
    counter = {"v": 0, "vt": 0, "vn": 0, "o": 0}

    def visit(node, parent_matrix):
        if node["type"] == "object":
            matrix = multiply(parent_matrix, node_matrix(node))
            for child in node.get("children", []):
                visit(child, matrix)
        elif node["type"] == "mesh":
            write_mesh(scene["geometries"][node["geometry"]], parent_matrix)

    def write_mesh(geometry, matrix):
        count = geometry["count"]
        if count <= 0:
            return
        positions = decode_floats(geometry["position"])
        normals = decode_floats(geometry["normal"])
        colors = decode_floats(geometry["color"])
        uvs = decode_floats(geometry["uv"])
        nm = normal_matrix(matrix)
        counter["o"] += 1
        lines.append("o mesh_%d" % counter["o"])
        base_v, base_vt, base_vn = counter["v"], counter["vt"], counter["vn"]
        for i in range(count):
            p = transform_point(matrix, positions[i * 3:i * 3 + 3])
            line = "v %s %s %s" % tuple(_fmt(c) for c in p)
            if colors:
                line += " %s %s %s" % tuple(_fmt(linear_to_srgb(c)) for c in colors[i * 3:i * 3 + 3])
            lines.append(line)
        if uvs:
            for i in range(count):
                lines.append("vt %s %s" % (_fmt(uvs[i * 2]), _fmt(1 - uvs[i * 2 + 1])))
        if normals:
            for i in range(count):
                lines.append("vn %s %s %s" % tuple(
                    _fmt(c) for c in transform_normal(nm, normals[i * 3:i * 3 + 3])))
        counter["v"] += count
        if uvs:
            counter["vt"] += count
        if normals:
            counter["vn"] += count

        for group in geometry["groups"]:
            material_index = group.get("material_index")
            if material_index is None or not 0 <= material_index < len(scene["materials"]):
                continue  # three.js drew nothing for these.
            if material_index not in used_materials:
                used_materials.append(material_index)
            lines.append("usemtl %s" % _material_name(material_index))
            end = min(group["start"] + group["count"], count)
            for first in range(group["start"], end - 2, 3):
                corners = []
                for k in range(first, first + 3):
                    v = str(base_v + k + 1)
                    vt = str(base_vt + k + 1) if uvs else ""
                    vn = str(base_vn + k + 1) if normals else ""
                    corners.append("%s/%s/%s" % (v, vt, vn) if (vt or vn) else v)
                lines.append("f " + " ".join(corners))

    if scene.get("root") is not None:
        visit(scene["root"], IDENTITY)

    textures = {}
    mtl = ["# PartyPlanner64"]
    for index in sorted(used_materials):
        desc = scene["materials"][index]
        mtl += ["newmtl %s" % _material_name(index), "Ka 1 1 1", "Kd 1 1 1", "Ks 0 0 0", "d 1",
                "illum 1"]
        if desc.get("map") is not None:
            name = _texture_name(desc["map"])
            textures[name] = data_url_to_bytes(scene["textures"][desc["map"]]["image"])
            mtl.append("map_Kd %s" % name)
            if desc.get("alpha_test"):
                mtl.append("map_d %s" % name)
        mtl.append("")
    return "\n".join(lines) + "\n", "\n".join(mtl) + "\n", textures


def scene_to_obj_zip(scene):
    """Return a .zip (bytes) of object.obj, material.mtl and the textures."""
    obj_text, mtl_text, textures = scene_to_obj(scene)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("object.obj", obj_text)
        zf.writestr("material.mtl", mtl_text)
        for name, data in textures.items():
            zf.writestr(name, data)
    return out.getvalue()
