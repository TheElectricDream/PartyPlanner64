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


@pytest.fixture
def clean_board_infos():
    """load_boards records event table locations in the (module level) board infos."""
    saved = {}
    for game in ("CLBE", "NMWE", "NMVE"):
        for info in boardinfo.get_board_infos(game):
            saved[id(info)] = (info, copy.deepcopy(info.get("space_event_tables")),
                               "space_event_tables" in info)
    yield
    for info, tables, present in saved.values():
        if present:
            info["space_event_tables"] = tables
        else:
            info.pop("space_event_tables", None)


@pytest.mark.parametrize("name", sorted(CASES))
def test_load_boards(monkeypatch, clean_board_infos, name):
    case = CASES[name]
    rom = fakerom.install(monkeypatch, case["game"])
    rom.hvqfs.bg = dict(case["board"]["bg"])
    writer = get_adapter(case["game"], {})
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
