"""Sprites: the MainFS image packs (routes/sprites.py)."""

import io
import zipfile

from PIL import Image


def _png(client, path):
    status, headers, body = client.call("GET", path)
    assert status == 200, body[:300]
    assert headers["Content-Type"] == "image/png"
    return Image.open(io.BytesIO(body)), headers


def test_no_rom(client):
    client.get("/api/sprites", expect=409)


def test_list_and_frames(client, fake_rom):
    fake_rom(1)
    sprites = client.get("/api/sprites")["sprites"]
    assert sprites == [{"dir": 1, "file": 0, "frames": 1, "width": 8, "height": 4},
                       {"dir": 2, "file": 1, "frames": 1, "width": 4, "height": 4}]
    res = client.get("/api/sprites/1/0")
    assert res["frames"] == [{"index": 0, "width": 8, "height": 4, "url": "/api/sprites/1/0/0.png"}]
    img, headers = _png(client, "/api/sprites/1/0/0.png")
    assert img.size == (8, 4) and img.mode == "RGBA"
    assert "Content-Disposition" not in headers
    _, headers = _png(client, "/api/sprites/1/0/0.png?download=1")
    assert "sprite-1-0-0.png" in headers["Content-Disposition"]
    sheet, _ = _png(client, "/api/sprites/2/1/sheet.png")
    assert sheet.size == (4, 4)


def test_zip(client, fake_rom):
    fake_rom(1)
    status, headers, body = client.call("GET", "/api/sprites/1/0/zip")
    assert status == 200 and "sprite-1-0.zip" in headers["Content-Disposition"]
    assert zipfile.ZipFile(io.BytesIO(body)).namelist() == ["1.0.0.png"]


def test_not_sprites(client, fake_rom):
    fake_rom(1)
    assert "not a sprite" in client.get("/api/sprites/1/1", expect=404)["error"]
    client.get("/api/sprites/9/0", expect=404)
    client.get("/api/sprites/1/0/3.png", expect=404)


def test_new_rom_new_list(client, fake_rom):
    fake_rom(1)
    assert len(client.get("/api/sprites")["sprites"]) == 2
    rh = fake_rom(1)
    del rh.rom.mainfs.files[(2, 1)]
    assert len(client.get("/api/sprites")["sprites"]) == 1
