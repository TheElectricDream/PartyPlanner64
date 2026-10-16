"""Models: FORM and MTNX files (routes/models.py), with the model tests' synthetic files."""

import json

import pytest


def test_no_rom(client):
    client.get("/api/models", expect=409)


def test_lists(client, fake_rom):
    fake_rom(1)
    res = client.get("/api/models")
    assert res["models"] == [{"dir": 1, "file": 1}, {"dir": 2, "file": 0}]
    assert res["first"] == {"dir": 2, "file": 0}       # from directory 2, as the original
    assert client.get("/api/models/animations")["animations"] == [{"dir": 1, "file": 2}]
    assert client.get("/api/models/animations?dir=2")["animations"] == []
    assert client.get("/api/models/animations?dir=1")["animations"] == [{"dir": 1, "file": 2}]


def test_scene_and_animation(client, fake_rom):
    fake_rom(1)
    scene = client.get("/api/models/1/1?wireframe=1&bg=FFFFFF")
    assert scene["root"]["type"] == "object" and scene["geometries"]
    assert scene["options"]["show_wireframe"] is True
    assert scene["background"] == 0xFFFFFF
    anim = client.get("/api/models/1/1/animation/1/2")
    assert anim["duration"] > 0 and anim["tracks"]
    assert "not a model" in client.get("/api/models/1/2", expect=404)["error"]
    assert "not an animation" in client.get("/api/models/1/1/animation/1/1", expect=404)["error"]
    client.get("/api/models/1/1?bg=zz", expect=400)


def test_export(client, fake_rom):
    fake_rom(1)
    status, headers, body = client.call("GET", "/api/models/1/1/export?format=gltf")
    if status == 501:
        pytest.skip("glTF export isn't in partyplanner64.lib.models yet")
    assert status == 200 and "model-1-1.gltf" in headers["Content-Disposition"]
    assert json.loads(body)["asset"]
    status, headers, body = client.call("GET", "/api/models/1/1/export?format=glb")
    assert status == 200 and body[:4] == b"glTF"
    client.get("/api/models/1/1/export?format=fbx", expect=400)


def test_export_follows_setting(client, fake_rom):
    fake_rom(1)
    client.post("/api/settings", {"models.useGLB": True})
    status, headers, body = client.call("GET", "/api/models/1/1/export")
    if status == 501:
        pytest.skip("glTF export isn't in partyplanner64.lib.models yet")
    assert ".glb" in headers["Content-Disposition"]


def test_export_obj(client, fake_rom):
    import io
    import zipfile
    fake_rom(1)
    status, headers, body = client.call("GET", "/api/models/1/1/export?format=obj")
    assert status == 200 and "model-1-1.zip" in headers["Content-Disposition"]
    z = zipfile.ZipFile(io.BytesIO(body))
    assert {"model-1-1.obj", "model-1-1.mtl"} <= set(z.namelist())
    assert "mtllib model-1-1.mtl" in z.read("model-1-1.obj").decode()
