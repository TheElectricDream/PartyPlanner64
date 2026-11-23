"""Test play (/api/playtest). Without a ROM the error paths run; with the real
Mario Party 3 (U) ROM in `roms/` a test ROM is built and "started"."""

import json
import os
import stat

import pytest

from partyplanner64 import emulator, state

from ..lib.test_playtest import _mp3_rom_path


@pytest.fixture(autouse=True)
def _no_installed_emulator(monkeypatch):
    monkeypatch.setattr(emulator, "detect", lambda: None)
    yield
    emulator.stop()


def test_without_a_rom(client, data_dir):
    info = client.get("/api/playtest")
    assert info["romLoaded"] is False and info["supported"] is False
    assert info["reason"] == "Open a ROM to test boards in it."
    assert info["game"] is None and info["options"] is None
    assert info["emulator"] == {"command": "", "detected": None, "effective": ""}

    assert client.call("POST", "/api/playtest", {"launch": False})[0] == 409
    assert client.call("POST", "/api/playtest/rom", {})[0] == 409
    assert client.post("/api/playtest/stop") == {"stopped": False}
    # No emulator: said before anything is built.
    status, _, body = client.call("POST", "/api/playtest", {})
    assert status == 400 and "No Nintendo 64 emulator was found" in json.loads(body)["error"]

    # The emulator is kept; a game's options need its ROM.
    info = client.post("/api/playtest/options", {"emulator": "  /opt/RMG %f  "})
    assert info["emulator"]["command"] == info["emulator"]["effective"] == "/opt/RMG %f"
    assert json.loads((data_dir / "playtest.json").read_text())["emulator"] == "/opt/RMG %f"
    assert client.get("/api/playtest")["emulator"]["command"] == "/opt/RMG %f"
    assert client.call("POST", "/api/playtest/options", {"options": {"coins": 5}})[0] == 409
    assert client.call("POST", "/api/playtest/options", {"emulator": 5})[0] == 400
    assert client.call("POST", "/api/playtest", {"romBoardIndex": "x"})[0] == 400
    assert client.call("POST", "/api/playtest", {"options": []})[0] == 400


def test_detected_emulator(client, monkeypatch):
    found = {"name": "RMG-K", "command": "/apps/RMG-K.AppImage %f"}
    monkeypatch.setattr(emulator, "detect", lambda: found)
    info = client.get("/api/playtest")["emulator"]
    assert info == {"command": "", "detected": found, "effective": found["command"]}
    info = client.post("/api/playtest/options", {"emulator": "mine"})["emulator"]
    assert info["effective"] == "mine" and info["detected"] == found


@pytest.mark.skipif(os.name != "posix", reason="uses a shell script")
def test_with_the_real_rom(client, data_dir, tmp_path):
    path = _mp3_rom_path()
    if not path:
        pytest.skip("The Mario Party 3 (U) ROM is not in roms/")
    with open(path, "rb") as f:
        status, _, body = client.call("POST", "/api/rom?name=mp3.z64", f.read())
    assert status == 200, body[:300]
    rom_names = [b["name"] for b in client.get("/api/state")["boards"]["romList"]]

    # The board that is open first is for another game.
    info = client.get("/api/playtest")
    assert info["romLoaded"] and not info["supported"]
    assert info["reason"] == "This board is for Mario Party 1; the ROM is Mario Party 3."
    status, _, body = client.call("POST", "/api/playtest", {"launch": False})
    assert status == 400 and json.loads(body)["error"] == info["reason"]

    # One of the ROM's own boards: tested as it is.
    client.post("/api/boards/current", {"index": 2, "rom": True})
    info = client.get("/api/playtest")
    assert info["supported"] and info["reason"] is None
    assert info["options"] == info["game"]["defaults"]
    options = dict(info["options"], coins=200, turn=5)
    assert client.post("/api/playtest/options", {"options": options})["options"]["coins"] == 200
    assert json.loads((data_dir / "playtest.json").read_text())["options"]["3"]["turn"] == 5

    out = tmp_path / "args.txt"
    script = tmp_path / "emu.sh"
    script.write_text('#!/bin/sh\necho "$@" > "%s"\nexec sleep 60\n' % out, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    client.post("/api/playtest/options", {"emulator": "%s %%f" % script})
    result = client.post("/api/playtest", {})
    assert result["launched"] is True
    assert (result["romBoardIndex"], result["romBoardName"]) == (2, "Spiny Desert")
    assert result["options"]["coins"] == 200
    rom_path = data_dir / "playtest" / "PartyPlanner64 Test (MP3).z64"
    assert result["path"] == str(rom_path) and result["command"] == [str(script), str(rom_path)]
    rom = rom_path.read_bytes()
    assert rom[0x3B:0x40] == b"NEDE\x20"
    assert client.post("/api/playtest/stop") == {"stopped": True}

    # A new board of the game: written over the first ROM board it fits, in a copy.
    client.post("/api/boards/new", {"game": 3, "type": "NORMAL", "theme": "default"})
    result = client.post("/api/playtest", {"launch": False, "options": {"stars": 3}})
    assert result["launched"] is False and result["command"] is None
    assert (result["romBoardIndex"], result["romBoardName"]) == (0, "Chilly Waters")
    assert result["options"]["stars"] == 3 and result["options"]["coins"] == 50
    status, headers, body = client.call("POST", "/api/playtest/rom", {"romBoardIndex": 4})
    assert status == 200 and body[0x3B:0x40] == b"NEDE\x20"
    assert "PartyPlanner64%20Test%20%28MP3%29.z64" in headers["Content-Disposition"] \
        or "PartyPlanner64 Test (MP3).z64" in headers["Content-Disposition"]
    assert client.call("POST", "/api/playtest", {"launch": False, "romBoardIndex": 99})[0] == 400
    # A duel board of the ROM cannot be tested yet.
    client.post("/api/boards/current", {"index": 6, "rom": True})
    status, _, body = client.call("POST", "/api/playtest", {"launch": False})
    assert status == 400 and "duel" in json.loads(body)["error"]

    # The open ROM is as it was.
    assert [b["name"] for b in client.get("/api/state")["boards"]["romList"]] == rom_names
    assert state.save_rom()[0][0x3B:0x3F] == b"NMVE"


EVENT_CODE = """; NAME: Test Toll
; GAMES: MP3_USA
; EXECUTION: Direct
; PARAM: +Number|toll
; PARAM: Space|exit

JR RA
NOP
"""


def test_event_without_a_rom(client, data_dir):
    info = client.post("/api/playtest/event/info", {"code": EVENT_CODE, "language": 0})
    assert info["event"] == {"id": "Test Toll", "name": "Test Toll"}
    assert info["supported"] is False
    assert info["reason"] == "Open a Mario Party 3 (U) ROM to test events in it."
    assert info["settings"] == info["test"]["defaults"]
    assert [p["name"] for p in info["test"]["parameters"]] == ["toll", "exit"]
    assert client.call("POST", "/api/playtest/event", {"code": EVENT_CODE, "launch": False})[0] == 409
    # Code without a header is not an event.
    status, _, body = client.call("POST", "/api/playtest/event/info", {"code": "JR RA\nNOP\n"})
    assert status == 400 and "name" in json.loads(body)["error"]
    assert client.call("POST", "/api/playtest/event/info", {"code": "", "language": 0})[0] == 400
    assert client.call("POST", "/api/playtest/event/info",
                       {"code": EVENT_CODE, "language": 4})[0] == 400


def test_event_with_the_real_rom(client, data_dir):
    from partyplanner64.lib.fs.scenes import SIZEOF_SCENE_TABLE_ENTRY, read_overlay_struct
    from partyplanner64.lib.playtest import mp3
    from partyplanner64.lib.utils.dataview import DataView

    path = _mp3_rom_path()
    if not path:
        pytest.skip("The Mario Party 3 (U) ROM is not in roms/")
    with open(path, "rb") as f:
        status, _, body = client.call("POST", "/api/rom?name=mp3.z64", f.read())
    assert status == 200, body[:300]
    rom_names = [b["name"] for b in client.get("/api/state")["boards"]["romList"]]
    current = client.get("/api/state")["boards"]["current"]

    info = client.post("/api/playtest/event/info", {"code": EVENT_CODE, "language": 0})
    assert info["supported"] and info["reason"] is None

    # Not for this game.
    mp2 = EVENT_CODE.replace("MP3_USA", "MP2_USA")
    info = client.post("/api/playtest/event/info", {"code": mp2, "language": 0})
    assert not info["supported"] and "MP3_USA" in info["reason"]
    assert client.call("POST", "/api/playtest/event", {"code": mp2, "launch": False})[0] == 400
    # Bad settings, and code that doesn't assemble.
    status, _, body = client.call("POST", "/api/playtest/event", {
        "code": EVENT_CODE, "launch": False, "settings": {"parameterValues": {"toll": 0}}})
    assert status == 400 and "positive" in json.loads(body)["error"]
    status, _, body = client.call("POST", "/api/playtest/event", {
        "code": EVENT_CODE.replace("JR RA", "JR NOTAREGISTER"), "launch": False})
    assert status == 400 and "Failed a test compile/assembly" in json.loads(body)["error"]

    # The event's test ROM: the test board, written over the first ROM board.
    settings = {"activation": 1, "parameterValues": {"toll": 15, "exit": 0}}
    result = client.post("/api/playtest/event", {"code": EVENT_CODE, "language": 0,
                                                 "settings": settings, "launch": False})
    assert result["launched"] is False and result["event"] == "Test Toll"
    assert (result["romBoardIndex"], result["romBoardName"]) == (0, "Chilly Waters")
    assert result["boardName"] == "Event Test"
    assert result["settings"]["parameterValues"] == {"toll": 15, "exit": 0}
    rom = (data_dir / "playtest" / "PartyPlanner64 Test (MP3).z64").read_bytes()
    assert rom[0x3B:0x40] == b"NEDE\x20"
    # It boots into Chilly Waters' scene, now the test board's.
    from partyplanner64.lib.romhandler import romhandler
    table = romhandler.get_rom().get_scenes()._overlay_table_rom_offset
    boot = read_overlay_struct(DataView(rom), table + mp3.SCENE_BOOT * SIZEOF_SCENE_TABLE_ENTRY)
    code = rom[boot["rom_start"]:boot["rom_start"] + boot["code_end"] - boot["code_start"]]
    assert (0x24040000 | mp3.SCENE_FIRST_BOARD).to_bytes(4, "big") in code

    # The settings are kept for the event's next test.
    saved = json.loads((data_dir / "playtest.json").read_text())["events"]["Test Toll"]
    assert saved == result["settings"]
    info = client.post("/api/playtest/event/info", {"code": EVENT_CODE, "language": 0})
    assert info["settings"] == result["settings"]
    # ...and survive saving the board test's options.
    client.post("/api/playtest/options", {"emulator": "x %f"})
    assert "Test Toll" in json.loads((data_dir / "playtest.json").read_text())["events"]

    # A C event works too.
    c_code = ('// NAME: C Toll\n// GAMES: MP3_USA\n// EXECUTION: Direct\n'
              '// PARAM: Number|delta\n\nvoid main() {\n}\n')
    result = client.post("/api/playtest/event", {"code": c_code, "language": 1, "launch": False,
                                                 "romBoardIndex": 4})
    assert result["romBoardIndex"] == 4 and result["event"] == "C Toll"

    # The open ROM and the open board are as they were.
    state_now = client.get("/api/state")["boards"]
    assert [b["name"] for b in state_now["romList"]] == rom_names
    assert state_now["current"] == current
    assert state.save_rom()[0][0x3B:0x3F] == b"NMVE"
