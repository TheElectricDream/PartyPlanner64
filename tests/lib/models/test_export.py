"""Tests of the glTF and OBJ exporters.

(gen_check_gltf.mjs in tests/fixtures/models loads the exported files with three.js's
GLTFLoader and compares them with model3d.js's objects; this checks the files' structure.)
"""

import io
import json
import math
import struct
import zipfile
from pathlib import Path

import pytest

from partyplanner64.lib.models.form import FORM
from partyplanner64.lib.models.form_to_scene import form_to_scene
from partyplanner64.lib.models.gltf import scene_to_gltf
from partyplanner64.lib.models.obj import scene_to_obj, scene_to_obj_zip
from partyplanner64.lib.models.scene_math import quaternion_from_euler

REF = json.loads((Path(__file__).parents[2] / "fixtures" / "models" / "models_ref.json").read_text())


def _scene(name, **kwargs):
    return form_to_scene(FORM.unpack(bytearray.fromhex(REF["forms"][name]["input"])), **kwargs)


def _simple_scene():
    """One triangle under a node rotated 90 degrees about y and moved by (10, 0, 0)."""
    return {
        "root": {"type": "object", "name": "0x00", "position": [10, 0, 0],
                 "rotation": [0, math.pi / 2, 0], "rotation_order": "ZYX", "scale": [1, 1, 1],
                 "children": [{"type": "mesh", "geometry": 0}]},
        "geometries": [{"count": 3, "position": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                        "normal": [1, 0, 0, 1, 0, 0, 1, 0, 0], "color": [1, 0, 0] * 3,
                        "uv": [0, 0, 1, 0, 0, 1],
                        "groups": [{"start": 0, "count": 3, "material_index": 1}]}],
        "materials": [{"type": "basic", "vertex_colors": True}] * 2,
        "textures": [],
    }


@pytest.mark.parametrize("name", sorted(REF["forms"]))
def test_gltf_and_glb(name):
    scene = _scene(name)
    gltf = json.loads(scene_to_gltf(scene))
    assert gltf["asset"]["version"] == "2.0"
    assert gltf["buffers"][0]["uri"].startswith("data:application/octet-stream;base64,")
    for mesh in gltf["meshes"]:
        for prim in mesh["primitives"]:
            assert set(prim["attributes"]) == {"POSITION", "NORMAL", "COLOR_0", "TEXCOORD_0"}
            assert "min" in gltf["accessors"][prim["attributes"]["POSITION"]]

    glb = scene_to_gltf(scene, glb=True)
    magic, version, length = struct.unpack_from("<4sII", glb)
    assert (magic, version, length) == (b"glTF", 2, len(glb))
    json_len, json_type = struct.unpack_from("<I4s", glb, 12)
    assert json_type == b"JSON" and json_len % 4 == 0
    doc = json.loads(glb[20:20 + json_len])
    bin_len, bin_type = struct.unpack_from("<I4s", glb, 20 + json_len)
    assert bin_type == b"BIN\0" and bin_len == doc["buffers"][0]["byteLength"]
    assert "uri" not in doc["buffers"][0]
    for image in doc.get("images", []):
        view = doc["bufferViews"][image["bufferView"]]
        start = 28 + json_len + view["byteOffset"]
        assert glb[start:start + 8] == b"\x89PNG\r\n\x1a\n"


def test_gltf_nodes():
    gltf = json.loads(scene_to_gltf(_simple_scene()))
    root = gltf["nodes"][gltf["scenes"][0]["nodes"][0]]
    assert root["name"] == "0x00"
    assert root["translation"] == [10, 0, 0]
    q = quaternion_from_euler(0, math.pi / 2, 0, "ZYX")
    assert root["rotation"] == q
    assert math.isclose(q[1], math.sqrt(0.5)) and math.isclose(q[3], math.sqrt(0.5))
    mesh_node = gltf["nodes"][root["children"][0]]
    prim = gltf["meshes"][mesh_node["mesh"]]["primitives"][0]
    assert gltf["accessors"][prim["indices"]]["count"] == 3
    assert gltf["extensionsUsed"] == ["KHR_materials_unlit"]
    assert scene_to_gltf(_simple_scene(), binary=True)[:4] == b"glTF"


def test_obj_world_space():
    result = scene_to_obj(_simple_scene())
    obj, mtl, textures = result["obj"], result["mtl"], result["textures"]
    assert "mtllib material.mtl" in obj
    vs = [list(map(float, line.split()[1:])) for line in obj.splitlines() if line.startswith("v ")]
    # (1,0,0) rotated 90 degrees about y is (0,0,-1); then moved by (10,0,0).
    expected = [[10, 0, -1, 1, 0, 0], [10, 1, 0, 1, 0, 0], [11, 0, 0, 1, 0, 0]]
    for got, want in zip(vs, expected):
        assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(got, want))
    vns = [list(map(float, line.split()[1:])) for line in obj.splitlines() if line.startswith("vn ")]
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(vns[0], [0, 0, -1]))
    vts = [line for line in obj.splitlines() if line.startswith("vt ")]
    assert vts == ["vt 0 1", "vt 1 1", "vt 0 0"]
    assert "usemtl material_1" in obj and "f 1/1/1 2/2/2 3/3/3" in obj
    assert "newmtl material_1" in mtl and not textures


def test_obj_zip():
    data = scene_to_obj_zip(_scene("simple"), name="object")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert names[:2] == ["object.obj", "object.mtl"]
        mtl = zf.read("object.mtl").decode()
        for name in names[2:]:
            assert name in mtl
            assert zf.read(name)[:4] == b"\x89PNG"
        obj = zf.read("object.obj").decode()
    faces = [line for line in obj.splitlines() if line.startswith("f ")]
    # The second mesh draws nothing: its faces have no group (the 0x38 face) or a material
    # index past the materials (atr 2 + 2), as three.js drew nothing for them either.
    assert len(faces) == 5
