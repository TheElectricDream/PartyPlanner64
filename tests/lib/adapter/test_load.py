"""load_boards against the TypeScript, reading back boards written to a fake ROM.

Fixture: load.json (gen_load.ts). Each board of overwrite_input.json is
written with overwrite_board, then all the game's boards are loaded: once with
the stashed board JSON, once without it (so the board def and the event lists
PP64 wrote are parsed). Image parsing is skipped on both sides.
"""

import copy

import pytest

from partyplanner64.lib.adapter import boardinfo
from partyplanner64.lib.adapter.adapters import get_adapter

from . import fakerom
from .conftest import as_json, load_fixture

INPUT = load_fixture("overwrite_input.json")
REF = load_fixture("load.json")
CASES = {case["name"]: case for case in INPUT["cases"]}
STASH_FILES = [(10, 423), (10, 429), (10, 683), (19, 619), (19, 621)]


def _save_board_infos():
    saved = []
    for game in ("CLBE", "NMWE", "NMVE"):
        for info in boardinfo.get_board_infos(game):
            saved.append((info, copy.deepcopy(info.get("space_event_tables")),
                          "space_event_tables" in info))
    return saved


def _restore_board_infos(saved):
    for info, tables, present in saved:
        if present:
            info["space_event_tables"] = copy.deepcopy(tables)
        else:
            info.pop("space_event_tables", None)


@pytest.fixture
def clean_board_infos():
    """load_boards records event table locations in the (module level) board infos."""
    saved = _save_board_infos()
    yield saved
    _restore_board_infos(saved)


def _tables_json(tables):
    if tables is None:
        return None
    return [{("tableOffset" if k == "table_offset" else k): v for k, v in t.items()} for t in tables]


@pytest.mark.parametrize("name", sorted(CASES))
def test_load_boards(monkeypatch, clean_board_infos, name):
    case = CASES[name]
    rom = fakerom.install(monkeypatch, case["game"])
    rom.hvqfs.bg = dict(case["board"]["bg"])
    writer = get_adapter(case["game"], {})
    fakerom.prefill(case["game"], writer, rom)
    writer.on_overwrite_promises = lambda *args: None
    writer.overwrite_board(case["boardIndex"], copy.deepcopy(case["board"]))

    for stashed in (True, False):
        if not stashed:
            for d, f in STASH_FILES:
                rom.mainfs.files.pop("%d/%d" % (d, f), None)
        loader = get_adapter(case["game"], {})
        loader.on_parse_board_select_img = lambda *args: None
        loader.on_parse_board_logo_img = lambda *args: None
        loader._parse_board_select_icon = lambda *args: None
        loader._read_animation_backgrounds = lambda *args: None
        boards = loader.load_boards()
        ref = REF[name + (":stashed" if stashed else ":parsed")]
        assert "error" not in ref
        got = as_json(boards)
        assert len(got) == len(ref["boards"])
        for i, (g, e) in enumerate(zip(got, ref["boards"])):
            assert g == e, "board %d (%s)" % (i, "stashed" if stashed else "parsed")
        infos = boardinfo.get_board_infos(fakerom.GAME_IDS[case["game"]])
        assert [_tables_json(info.get("space_event_tables")) for info in infos] == ref["spaceEventTables"]
        _restore_board_infos(clean_board_infos)


def test_boards_with_hvq_backgrounds_are_flagged(monkeypatch, clean_board_infos):
    """The game's own (HVQ) backgrounds read as black; such boards say so."""
    case = CASES["mp1_dk"]
    rom = fakerom.install(monkeypatch, case["game"])
    rom.hvqfs.bg = dict(case["board"]["bg"])
    loader = get_adapter(case["game"], {})
    for hook in ("on_parse_board_select_img", "on_parse_board_logo_img",
                 "_parse_board_select_icon", "_read_animation_backgrounds"):
        setattr(loader, hook, lambda *args: None)
    fakerom.prefill(case["game"], loader, rom)
    loader.on_overwrite_promises = lambda *args: None
    loader.overwrite_board(case["boardIndex"], copy.deepcopy(case["board"]))
    from partyplanner64.lib.adapter.boardinfo import get_board_infos
    infos = get_board_infos(rom.get_game())
    rom.hvqfs.hvq_dirs = {infos[0]["bg_dir"]}
    boards = loader.load_boards()
    assert boards[0].get("_bgHvq") is True
    assert all("_bgHvq" not in b for b in boards[1:])


def test_hvqfs_tells_hvq_tiles_apart():
    from partyplanner64.lib.fs.hvqfs import HVQFS

    class Rom:
        def __init__(self, version):
            self.version = version

        def get_game_version(self):
            return self.version

    fs = HVQFS.__new__(HVQFS)
    fs._rom = Rom(2)
    fs._hvq_cache = [
        [b"meta", b"HVQ-MPS1.1", b"HVQS....", b"HVQS...."],     # the game's own
        [b"meta", b"HVQ-MPS1.1", b"\x00\x00\x00\x03....", b"\x00\x00\x00\x03...."],  # PP64's
        None,
    ]
    assert fs.is_hvq_compressed(0)
    assert not fs.is_hvq_compressed(1)
    assert not fs.is_hvq_compressed(2)
    assert not fs.is_hvq_compressed(9)
