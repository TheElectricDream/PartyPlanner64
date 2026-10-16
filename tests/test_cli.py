"""The command line (partyplanner64/cli.py)."""

import json
import sys
import types

import pytest

from partyplanner64 import cli
from partyplanner64.editor import jsjson
from partyplanner64.editor.boards import _make_default_board
from partyplanner64.lib.romhandler import ROM, romhandler


def _header(game_id):
    data = bytearray(0x1000)
    data[0x3B:0x3F] = game_id.encode("ascii")
    return bytes(data)


def run(args, capsys):
    try:
        code = cli.main(args)
    except SystemExit as e:
        code = e.code
    out = capsys.readouterr()
    return code or 0, out.out, out.err


def test_help(capsys):
    code, out, _ = run(["--help"], capsys)
    assert code == 0
    for command in ("serve", "overwrite", "info", "export-boards", "validate"):
        assert command in out
    code, out, _ = run(["overwrite", "--help"], capsys)
    assert "--target-board-index" in out
    code, out, _ = run(["--version"], capsys)
    assert out.startswith("PartyPlanner64 v")


def test_serve_options_without_command(monkeypatch):
    from partyplanner64.server import app
    seen = {}
    monkeypatch.setattr(app, "serve", lambda args: seen.__setitem__("args", args))
    cli.main(["--port", "9123", "--no-browser"])
    assert seen["args"].port == 9123 and seen["args"].no_browser
    cli.main([])
    assert seen["args"].port == 8064


def test_overwrite_bad_arguments(capsys):
    code, out, err = run(["overwrite", "--rom-file", "x.z64"], capsys)
    assert code == 2 and "Bad arguments" in err and out.startswith("PartyPlanner64 v")


def test_overwrite_not_a_rom(tmp_path, capsys):
    rom = tmp_path / "rom.z64"
    rom.write_bytes(b"\0" * 0x100)
    board = tmp_path / "board.json"
    board.write_text(jsjson.stringify(_make_default_board(1)))
    code, out, err = run(["overwrite", "--rom-file", str(rom), "--target-board-index", "0",
                          "--board-file", str(board), "--output-file",
                          str(tmp_path / "out.z64")], capsys)
    assert code == 1
    assert "File is not recognized as any valid ROM." in err
    assert not (tmp_path / "out.z64").exists()


@pytest.fixture
def fake_rom(monkeypatch):
    log = {}

    def set_rom_buffer(buffer, skip_supported_check=False, on_error=None):
        romhandler._rom = ROM(bytearray(buffer))
        return True

    def save_rom(write_decompressed):
        log["decompressed"] = write_decompressed
        return bytearray(b"NEWROM")

    class Adapter:
        def load_boards(self):
            log["loaded"] = True
            boards = []
            for name in ("Chilly Waters", "Deep: Bloober/Sea"):
                b = _make_default_board(3)
                b["name"] = name
                b["_rom"] = True
                boards.append(b)
            return boards

        def overwrite_board(self, index, board):
            log["overwrite"] = (index, board)

    monkeypatch.setattr(romhandler, "set_rom_buffer", set_rom_buffer)
    monkeypatch.setattr(romhandler, "save_rom", save_rom)
    adapters = types.ModuleType("partyplanner64.lib.adapter.adapters")
    adapters.get_rom_adapter = lambda options: Adapter()
    monkeypatch.setitem(sys.modules, "partyplanner64.lib.adapter.adapters", adapters)
    yield log
    romhandler.clear()


def test_overwrite(tmp_path, capsys, fake_rom):
    rom = tmp_path / "rom.z64"
    rom.write_bytes(_header("NMVE"))
    board = _make_default_board(3)
    board["name"] = "Custom"
    board["links"] = {"0": 0}
    board_file = tmp_path / "board.json"
    board_file.write_text(jsjson.stringify(board))
    out_file = tmp_path / "out.z64"
    code, out, err = run(["overwrite", "--rom-file", str(rom), "--target-board-index", "1",
                          "--board-file", str(board_file), "--output-file", str(out_file)],
                         capsys)
    assert code == 0, err
    assert "Overwriting board 1 in %s with %s" % (rom, board_file) in out
    assert "Wrote %s" % out_file in out
    assert out_file.read_bytes() == b"NEWROM"
    assert fake_rom["loaded"] and fake_rom["decompressed"] is False
    index, written = fake_rom["overwrite"]
    assert index == 1 and written["name"] == "Custom"


def test_info_and_export(tmp_path, capsys, fake_rom):
    rom = tmp_path / "rom.z64"
    rom.write_bytes(_header("NMVE"))
    code, out, _ = run(["info", str(rom)], capsys)
    assert code == 0
    assert "Mario Party 3 (U)" in out and "Chilly Waters" in out and "2 boards" in out
    code, out, _ = run(["export-boards", str(rom), str(tmp_path / "boards")], capsys)
    assert code == 0
    files = sorted(p.name for p in (tmp_path / "boards").iterdir())
    assert files == ["0 - Chilly Waters.json", "1 - Deep_ Bloober_Sea.json"]
    exported = json.loads((tmp_path / "boards" / files[0]).read_text())
    assert exported["name"] == "Chilly Waters" and "_rom" not in exported


def test_validate_without_rom(tmp_path, capsys):
    good = tmp_path / "good.json"
    board = _make_default_board(1)
    board["spaces"].append({"x": 1, "y": 1, "z": 0, "type": 1})
    board["links"] = {"0": 1, "1": 0}
    good.write_text(jsjson.stringify(board))
    code, out, _ = run(["validate", str(good)], capsys)
    assert code == 0 and "No problems found" in out
    board = _make_default_board(1)
    board["spaces"].append({"x": 1, "y": 1, "z": 0, "type": 1})
    board["links"] = {"0": 1}
    bad = tmp_path / "bad.json"
    bad.write_text(jsjson.stringify(board))
    code, out, _ = run(["validate", str(bad)], capsys)
    assert code == 1 and "dead end" in out
    junk = tmp_path / "junk.json"
    junk.write_text("{")
    code, _, err = run(["validate", str(junk)], capsys)
    assert code == 1 and "could not be parsed" in err


def test_validate_with_rom(tmp_path, capsys, fake_rom, monkeypatch):
    validation = types.ModuleType("partyplanner64.lib.validation.validation")
    validation.validate_current_board_for_overwrite = lambda rom_boards, board, skip: [
        {"errors": [], "warnings": ["careful"]},
        {"name": "Chilly Waters", "unavailable": False, "errors": [], "warnings": []},
        {"name": "Deep Bloober Sea", "unavailable": False, "errors": ["too big"],
         "warnings": []}]
    monkeypatch.setitem(sys.modules, "partyplanner64.lib.validation.validation", validation)
    rom = tmp_path / "rom.z64"
    rom.write_bytes(_header("NMVE"))
    board = tmp_path / "board.json"
    board.write_text(jsjson.stringify(_make_default_board(3)))
    code, out, _ = run(["validate", str(board), "--rom", str(rom), "--rom-board", "0"], capsys)
    assert code == 0 and "warning: careful" in out and "Deep" not in out
    code, out, _ = run(["validate", str(board), "--rom", str(rom), "--rom-board", "1"], capsys)
    assert code == 1 and "error: too big" in out
