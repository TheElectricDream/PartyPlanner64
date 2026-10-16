"""The Debug page's tools (routes/debug.py)."""

import io
import zipfile


def test_no_rom(client):
    client.get("/api/debug/scenes", expect=409)
    client.call("GET", "/api/debug/dump")


def test_scene_table(client, fake_rom):
    fake_rom(1)
    res = client.get("/api/debug/scenes")
    assert res["count"] == 2 and res["scenes"][1]["rom_start"] == 0x201000
    lines = res["text"].splitlines()
    assert lines[0].split()[:3] == ["i", "rom_start", "rom_end"]
    assert lines[1].split()[:3] == ["0x00", "0x200000", "0x200020"]
    split = client.get("/api/debug/scenes?format=n64split")["text"].splitlines()
    assert split[0] == '   - [0x200000, 0x200010, "asm", "overlay0_main", 0x80100000]'
    assert split[2] == "   # overlay0 bss: 0x80100020 - 0x80100028"
    splat = client.get("/api/debug/scenes?format=n64splat")["text"].splitlines()
    assert splat[:4] == ["  - name: overlay0", "    type: code", "    overlay: True", "    start: 0x200000"]
    client.get("/api/debug/scenes?format=x", expect=400)


def test_scene(client, fake_rom):
    rh = fake_rom(1)
    assert client.get("/api/debug/scenes/1")["info"]["ram_start"] == "80100000"
    client.get("/api/debug/scenes/7", expect=404)
    asm = client.get("/api/debug/scenes/0/asm")["text"].splitlines()
    assert asm[0] == "0x80100000: ADDIU SP SP 0xFFE8"
    assert asm[2] == "0x80100008: JR RA"
    assert "D_80100010: 00000001" in asm and "D_80100020: .word 0" in asm
    status, headers, body = client.call("GET", "/api/debug/scenes/0/download")
    assert status == 200 and "overlay-0.bin" in headers["Content-Disposition"] and len(body) == 32
    status, _, body = client.call("POST", "/api/debug/scenes/1/replace?code_end=80100004&bss_end=", b"\x00" * 8)
    assert status == 200
    assert rh.rom.scenes.replaced == (1, {"code_end": 0x80100004})


def test_offsets(client, fake_rom):
    fake_rom(1)
    res = client.get("/api/debug/rom-to-ram?offset=200004")["result"]
    assert res == "RAM: 80100004\nOverlay 0 (0x00) offset +4 (+0x04)"
    res = client.get("/api/debug/rom-to-ram?offset=10104")["result"]
    assert res == "RAM: N/A\nMainFS 1/0 (0x01/0x00) offset +4 (+0x04)"
    assert client.get("/api/debug/rom-to-ram?offset=2000")["result"] == "RAM: 0x80001400"
    assert client.get("/api/debug/rom-to-ram?offset=10")["result"] == "Unknown"
    client.get("/api/debug/rom-to-ram?offset=xyz", expect=400)
    # MainFS: 0x10000 + 4 + 4*3, then dir 0: 4 + 4*1, file header 12.
    assert client.get("/api/debug/mainfs-to-rom?dir=0&file=0")["result"] == "ROM: 0x10024"
    assert client.get("/api/debug/mainfs-to-rom?dir=9&file=0")["result"] == "Unknown"


def test_asm(client, fake_rom):
    fake_rom(1)
    text = client.get("/api/debug/asm?start=0&end=4")["text"].splitlines()
    assert text == ["0x00: ADDIU SP SP 0xFFE8", "0x04: SW RA 0x10(SP)"]
    client.get("/api/debug/asm?start=8&end=0", expect=400)


def test_strings(client, fake_rom):
    fake_rom(1)
    assert client.get("/api/debug/string?index=1")["text"] == "Get a Star!"
    assert client.get("/api/debug/string?index=2&raw=1")["text"] == "43 6F 69 6E 73 00"
    found = client.get("/api/debug/find-string?q=Star")
    assert found["count"] == 1 and found["text"] == "1 (0x01):\nGet a Star!"
    fake_rom(3)
    assert client.get("/api/debug/string?dir=1&index=0")["text"] == "Coins"
    assert client.get("/api/debug/string?dir=1&index=0")["where"] == "0x01/0x00"


def test_dump_round_trip(client, fake_rom):
    rh = fake_rom(1)
    status, headers, body = client.call("GET", "/api/debug/dump")
    assert status == 200 and "mp1-files.zip" in headers["Content-Disposition"]
    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    assert "mainfs/1/1.form" in names and "mainfs/1/2.mtnx" in names and "mainfs/1/0" in names
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("mainfs/2/1", b"new")
        z.writestr("readme.txt", b"ignored")
    res = client.post("/api/debug/dump", out.getvalue())
    assert res == {"written": 1, "files": ["2/1"]}
    assert rh.rom.mainfs.files[(2, 1)] == b"new"
    assert "zip" in client.post("/api/debug/dump", b"not a zip", expect=400)["error"]


def test_images(client, fake_rom):
    fake_rom(1)
    status, headers, body = client.call("GET", "/api/debug/images")
    assert status == 200
    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    assert "mainfs/1/0.0.png" in names and "mainfs/2/1.0.png" in names
