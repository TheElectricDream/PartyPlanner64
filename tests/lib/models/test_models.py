"""Differential tests of FORM/MTNX parsing and the scene/animation descriptions against
FormToThreeJs/MtnxToThreeJs (reference: tests/fixtures/models/gen_models.ts)."""

import io
import json
import math
from pathlib import Path

import pytest
from PIL import Image

from partyplanner64.lib.models.form import FORM
from partyplanner64.lib.models.form_to_scene import decode_floats, form_to_scene
from partyplanner64.lib.models.mtnx import MTNX
from partyplanner64.lib.models.mtnx_to_animation import mtnx_to_animation
from partyplanner64.lib.utils.canvas import data_url_to_bytes

from ._compare import assert_matches

REF = json.loads((Path(__file__).parents[2] / "fixtures" / "models" / "models_ref.json").read_text())
FORM_NAMES = sorted(REF["forms"])


def _form(name):
    return FORM.unpack(bytearray.fromhex(REF["forms"][name]["input"]))


@pytest.mark.parametrize("name", FORM_NAMES)
def test_unpack_and_pack(name):
    ref = REF["forms"][name]
    form = _form(name)
    assert form["entries"] == ref["unpacked"]["entries"]
    for type_, entries in ref["unpacked"].items():
        if type_ == "entries":
            continue
        assert len(form[type_]) == len(entries)
        for ts_entry, py_entry in zip(entries, form[type_]):
            assert_matches(ts_entry, py_entry, type_)
    assert FORM.pack(form).hex() == ref["repacked"]


def test_replace_bmp():
    form = _form("skeleton")
    FORM.replace_bmp(form, 0, bytes([0x32, 0x10, 0x03, 0x21]),
                     {"colors": [0x11223344, 0x55667788, 0x99AABBCC, 0xDDEEFF00]})
    assert FORM.pack(form).hex() == REF["replaceBMP"]


def _close(a, b, path):
    assert len(a) == len(b), path
    for i, (x, y) in enumerate(zip(a, b)):
        if isinstance(x, str) or isinstance(y, str):
            assert x == y, path
        else:
            assert math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-6), "%s[%d]: %r != %r" % (path, i, x, y)


def _pixels(url):
    return Image.open(io.BytesIO(data_url_to_bytes(url))).convert("RGBA").tobytes()


def _compare_node(ts, py, scene, path):
    if py["type"] == "object":
        assert ts["type"] == "Object3D", path
        assert ts["name"] == py["name"], path
        _close(ts["position"], py["position"], path + ".position")
        _close(ts["rotation"], py["rotation"] + [py["rotation_order"]], path + ".rotation")
        _close(ts["scale"], py["scale"], path + ".scale")
        assert len(ts["children"]) == len(py["children"]), path
        for i, (a, b) in enumerate(zip(ts["children"], py["children"])):
            _compare_node(a, b, scene, "%s/%d" % (path, i))
    elif py["type"] == "mesh":
        assert ts["type"] == "Mesh", path
        geometry = scene["geometries"][py["geometry"]]
        attrs = ts["geometry"]["attributes"]
        _close(attrs["position"], decode_floats(geometry["position"]), path + ".position")
        assert geometry["count"] * 3 == len(attrs["position"])
        for key in ("normal", "color", "uv"):
            values = decode_floats(geometry[key])
            if values:
                _close(attrs[key], values, path + "." + key)
            else:
                assert key not in attrs, path
        groups = [{"start": g["start"], "count": g["count"], "materialIndex": g["material_index"]}
                  for g in geometry["groups"]]
        assert ts["geometry"]["groups"] == groups, path
        assert ts["materials"] == list(range(len(scene["materials"]))), path
    elif py["type"] == "wireframe":
        assert ts["type"] == "LineSegments", path
        assert ts["material"]["color"] == py["color"]
        assert ts["material"]["linewidth"] == py["linewidth"]
    elif py["type"] == "normals":
        assert ts["type"] == "VertexNormalsHelper", path
        assert ts["material"]["color"] == py["color"]
    else:
        raise AssertionError(py["type"])


VARIANTS = {
    "default": {},
    "wire": {"show_wireframe": True, "show_textures": False, "bg_color": 0x336699},
    "normals": {"show_vertex_normals": True, "show_wireframe": True},
    "camera": {"use_form_camera": True},
}


@pytest.mark.parametrize("name", FORM_NAMES)
@pytest.mark.parametrize("variant", sorted(VARIANTS))
@pytest.mark.parametrize("binary", [True, False])
def test_form_to_scene(name, variant, binary):
    ref = REF["forms"][name]["variants"][variant]
    scene = form_to_scene(_form(name), binary=binary, **VARIANTS[variant])
    json.dumps(scene)  # JSON-serializable
    _compare_node(ref["tree"], scene["root"], scene, name)

    consts = REF["consts"]
    assert len(ref["materials"]) in (0, len(scene["materials"]))
    for ts_mat, py_mat in zip(ref["materials"], scene["materials"]):
        assert ts_mat["vertexColors"] == py_mat["vertex_colors"]
        assert ts_mat["alphaTest"] == py_mat.get("alpha_test", 0)
        if ts_mat["map"] is None:
            assert "map" not in py_mat
            continue
        tex = scene["textures"][py_mat["map"]]
        assert ts_mat["map"]["flipY"] == tex["flip_y"]
        assert ts_mat["map"]["wrapS"] == consts[tex["wrap_s"]]
        assert ts_mat["map"]["wrapT"] == consts[tex["wrap_t"]]
        assert ts_mat["map"]["magFilter"] == consts[tex["mag_filter"]]
        assert ts_mat["map"]["minFilter"] == consts[tex["min_filter"]]
        assert ts_mat["map"]["colorSpace"] == tex["color_space"]
        assert _pixels(ts_mat["map"]["url"]) == _pixels(tex["image"])

    camera = scene["camera"]
    assert camera["fov"] == ref["camera"]["fov"] and camera["far"] == ref["camera"]["far"]
    _close(ref["camera"]["position"], camera["position"], "camera")
    if camera["look_at"] is None:
        _close(ref["camera"]["quaternion"], [0, 0, 0, 1], "camera.quaternion")


def test_mtnx():
    ref = REF["mtnx"]
    mtnx = MTNX.unpack(bytearray.fromhex(ref["input"]))
    assert MTNX.is_mtnx(bytearray.fromhex(ref["input"]))
    assert mtnx["total_frames"] == ref["unpacked"]["totalFrames"]
    for ts_track, py_track in zip(ref["unpacked"]["tracks"], mtnx["tracks"]):
        keyframes = {str(k): v for k, v in py_track["keyframes"].items()}
        assert list(keyframes) == list(ts_track["keyframes"])
        assert_matches(ts_track["keyframes"], keyframes)
        ts_track = dict(ts_track)
        del ts_track["keyframes"]
        assert_matches(ts_track, py_track)

    clip = mtnx_to_animation(mtnx, _form("skeleton"))
    json.dumps(clip)
    assert clip["name"] == ref["clip"]["name"]
    assert clip["duration"] == ref["clip"]["duration"]
    assert len(clip["tracks"]) == len(ref["clip"]["tracks"])
    for ts_track, py_track in zip(ref["clip"]["tracks"], clip["tracks"]):
        assert ts_track["name"] == py_track["name"]
        assert ts_track["type"] == py_track["type"]
        _close(ts_track["times"], py_track["times"], ts_track["name"])
        _close(ts_track["values"], py_track["values"], ts_track["name"])
