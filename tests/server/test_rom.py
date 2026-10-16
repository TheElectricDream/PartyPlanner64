"""The ROM endpoints. There is no ROM here: the error paths run for real, the rest is mocked."""

import json
import sys
import types

import pytest

from partyplanner64.editor.boards import _make_default_board
from partyplanner64.editor.store import store
from partyplanner64.lib import romhandler as romhandler_module
from partyplanner64.lib.romhandler import ROM, romhandler


def _header(game_id):
    data = bytearray(0x1000)
    data[0:4] = bytes([0x80, 0x37, 0x12, 0x40])
    data[0x3B:0x3F] = game_id.encode("ascii")
    return bytes(data)


def test_not_a_rom(client):
    status, _, body = client.call("POST", "/api/rom?name=x.z64", b"hello" * 100)
    assert status == 400
    assert json.loads(body)["error"] == "File is not recognized as any valid ROM."
    assert client.get("/api/state")["rom"] is None
    status, _, body = client.call("POST", "/api/rom?name=x.z64", b"")
    assert status == 400


def test_unsupported_rom(client):
    status, _, body = client.call("POST", "/api/rom?name=x.z64", _header("NMVJ"))
    assert status == 400
    assert json.loads(body)["error"] == "This ROM is not supported right now."
    # Allowed, it is read, which fails for this fake.
    client.post("/api/settings", {"ui.allowallroms": True})
    status, _, body = client.call("POST", "/api/rom?name=x.z64", _header("NMVJ"))
    assert status == 400
    assert json.loads(body)["error"].startswith("Error loading the ROM file.")
    assert client.get("/api/state")["rom"] is None


def test_no_rom(client):
    assert client.call("POST", "/api/rom/save", {})[0] == 409
    assert client.call("POST", "/api/rom/overwrite", {"romBoardIndex": 0})[0] == 409
    client.post("/api/rom/close")


class FakeAdapter:
    def __init__(self, log):
        self.log = log

    def load_boards(self):
        boards = []
        for name in ("Chilly Waters", "Deep Bloober Sea"):
            board = _make_default_board(3)
            board["name"] = name + (" (written)" if self.log.get("written") else "")
            boards.append(board)
        return boards

    def overwrite_board(self, index, board):
        self.log["written"] = (index, board["name"])


@pytest.fixture
def fake_rom(monkeypatch):
    """romhandler loads a fake MP3 ROM; the adapter and validation are fakes."""
    log = {"validation": [{"errors": [], "warnings": ["general warning"]},
                          {"name": "Chilly Waters", "unavailable": False,
                           "forced_disabled": False, "errors": [], "warnings": []},
                          {"name": "Deep Bloober Sea", "unavailable": True,
                           "forced_disabled": False, "errors": ["board error"],
                           "warnings": []}]}

    def set_rom_buffer(buffer, skip_supported_check=False, on_error=None):
        romhandler._rom = ROM(bytearray(buffer))
        log["skip"] = skip_supported_check
        return True

    def save_rom(write_decompressed):
        log["decompressed"] = write_decompressed
        return bytearray(b"ROM!")

    monkeypatch.setattr(romhandler, "set_rom_buffer", set_rom_buffer)
    monkeypatch.setattr(romhandler, "save_rom", save_rom)
    adapters = types.ModuleType("partyplanner64.lib.adapter.adapters")

    def get_rom_adapter(options):
        log.setdefault("options", []).append(options)
        return FakeAdapter(log)
    adapters.get_rom_adapter = get_rom_adapter
    adapters.get_adapter = lambda game, options: None
    monkeypatch.setitem(sys.modules, "partyplanner64.lib.adapter.adapters", adapters)
    validation = types.ModuleType("partyplanner64.lib.validation.validation")

    def validate(rom_boards, board, skip_validation=False):
        log["validated"] = (len(rom_boards), board["name"], skip_validation)
        return log["validation"]
    validation.validate_current_board_for_overwrite = validate
    monkeypatch.setitem(sys.modules, "partyplanner64.lib.validation.validation", validation)
    yield log
    romhandler.clear()


def test_rom_flow(client, fake_rom):
    status, _, body = client.call("POST", "/api/rom?name=mp3.z64", _header("NMVE"))
    assert status == 200, body
    res = json.loads(body)
    assert res["rom"] == {"game": "NMVE", "gameName": "MP3_USA", "gameVersion": 3,
                          "supported": True, "fileName": "mp3.z64",
                          "title": "Mario Party 3 (U)", "shortName": "MP3"}
    assert [b["name"] for b in res["boards"]["romList"]] == ["Chilly Waters", "Deep Bloober Sea"]
    assert all(b["rom"] for b in res["boards"]["romList"])
    assert fake_rom["skip"] is False
    assert client.get("/api/state")["rom"]["game"] == "NMVE"
    assert client.get("/api/boards/1?rom=1")["board"]["name"] == "Deep Bloober Sea"
    status, _, body = client.call("GET", "/api/boards/1/export?rom=1")
    assert "_rom" not in json.loads(body)
    assert store.state.rom_boards[1]["_rom"] is True

    # Validation, as the overwrite menu showed it.
    v = client.get("/api/board/validate?romBoard=1")
    assert v["results"] == [{"level": 2, "message": "general warning"},
                            {"level": 1, "message": "board error"}]
    assert v["boards"][1] == {"index": 1, "name": "Deep Bloober Sea", "unavailable": True,
                              "forcedDisabled": False, "errors": ["board error"], "warnings": []}
    assert fake_rom["validated"] == (2, "Untitled", False)

    # Overwrite: refused for an unavailable board, done for another.
    client.op("setBoardName", {"name": "Mine"})
    status, _, body = client.call("POST", "/api/rom/overwrite", {"romBoardIndex": 1})
    assert status == 400 and "written" not in fake_rom
    fake_rom["validation"][0]["errors"] = ["general error"]
    assert client.call("POST", "/api/rom/overwrite", {"romBoardIndex": 0})[0] == 400
    fake_rom["validation"][0]["errors"] = []
    res = client.post("/api/rom/overwrite", {"romBoardIndex": 0})
    assert fake_rom["written"] == (0, "Mine")
    assert {"write_branding": True} in fake_rom["options"]
    assert [b["name"] for b in res["boards"]["romList"]] == [
        "Chilly Waters (written)", "Deep Bloober Sea (written)"]
    assert res["boards"]["current"] == {"index": 0, "rom": False}
    assert client.get("/api/board")["board"]["name"] == "Mine"

    # A ROM board as the current board, and copies of it.
    r = client.post("/api/boards/current", {"index": 1, "rom": True})
    assert r["boards"]["current"] == {"index": 1, "rom": True}
    r = client.post("/api/boards/copy", {"index": 1, "rom": True, "makeCurrent": True})
    assert r["boards"]["current"] == {"index": 1, "rom": False}
    assert r["boards"]["list"][1]["name"] == "Copy of Deep Bloober Sea (written)"
    assert "_rom" not in store.state.boards[1]

    # Save.
    client.post("/api/settings", {"write.decompressed": True})
    status, headers, body = client.call("POST", "/api/rom/save", {})
    assert status == 200 and body == b"ROM!"
    assert "MyMarioParty3.z64" in headers["Content-Disposition"]
    assert fake_rom["decompressed"] is True

    # Close: the ROM boards go and board 0 is current.
    client.post("/api/boards/current", {"index": 0, "rom": True})
    res = client.post("/api/rom/close")
    assert res["boards"]["romList"] == [] and res["boards"]["current"] == {"index": 0,
                                                                          "rom": False}
    assert client.get("/api/state")["rom"] is None


def test_open_rom_twice(client, fake_rom):
    client.call("POST", "/api/rom?name=a.z64", _header("NMVE"))
    client.post("/api/boards/current", {"index": 1, "rom": True})
    status, _, body = client.call("POST", "/api/rom?name=b.z64", _header("NMVE"))
    res = json.loads(body)
    assert len(res["boards"]["romList"]) == 2
    assert res["boards"]["current"] == {"index": 0, "rom": False}
    assert res["rom"]["fileName"] == "b.z64"


def test_skip_validation(client, fake_rom):
    client.call("POST", "/api/rom?name=a.z64", _header("NMVE"))
    client.post("/api/settings", {"ui.skipvalidation": True})
    fake_rom["validation"] = [{"errors": [], "warnings": []},
                              {"name": "A", "unavailable": False, "errors": [], "warnings": []},
                              {"name": "B", "unavailable": True, "errors": [], "warnings": []}]
    client.get("/api/board/validate")
    assert fake_rom["validated"][2] is True
    assert client.call("POST", "/api/rom/overwrite", {"romBoardIndex": 1})[0] == 400
    assert client.call("POST", "/api/rom/overwrite", {"romBoardIndex": 7})[0] == 400
    client.post("/api/rom/overwrite", {"romBoardIndex": 0})
    assert fake_rom["written"][0] == 0


def test_romhandler_module_name():
    assert romhandler_module.romhandler is romhandler


def test_real_validation(client):
    """The library's validation, with a ROM that has only a header (MP3)."""
    from partyplanner64.editor import boards
    romhandler._rom = ROM(bytearray(_header("NMVE")))
    try:
        for n in range(2):
            board = _make_default_board(3)
            board["name"] = "ROM %d" % n
            boards.add_board(board, rom=True)
        v = client.get("/api/board/validate?romBoard=1")
        assert v["romLoaded"] and len(v["boards"]) == 2
        assert {"level": 1, "message": "Board is for MP1, but ROM is MP3"} in v["results"]
        assert v["boards"][1]["forcedDisabled"] is True
        status, _, body = client.call("POST", "/api/rom/overwrite", {"romBoardIndex": 1})
        assert status == 400 and b"Board is for MP1, but ROM is MP3" in body
    finally:
        romhandler.clear()
