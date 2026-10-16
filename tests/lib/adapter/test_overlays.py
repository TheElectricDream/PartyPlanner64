"""Differential tests of the board overlays against the TypeScript's output.

The fixtures (tests/fixtures/overlays/*_overlays.json.gz) were made by gen_overlays.ts:
for sample boards of each game, the input board JSON, board index, audio indices, the
board info values used, the asm createBoardOverlay returned, and some intermediate
values (the prepared additional bg / audio selection code, the symbols used).

Two kinds of tests:
- "isolated": the modules the overlays call (boards, symbols, built-in events,
  additionalbg, getaudiochoice, boardinfo) are replaced by small stand-ins fed with the
  TypeScript's intermediate values, so the overlay code itself is checked.
- "integration": the real modules are used (skipped while they are missing).
"""

import copy
import gzip
import importlib
import json
import os
import sys
import types

import pytest

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "overlays")
GAMES = ["mp1", "mp2", "mp3"]


def _load(game):
    with gzip.open(os.path.join(FIXTURES, game + "_overlays.json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


_DATA = {g: _load(g) for g in GAMES}
_CASES = [(g, i) for g in GAMES for i in range(len(_DATA[g]["cases"]))]
_IDS = ["%s-%s" % (g, _DATA[g]["cases"][i]["name"]) for g, i in _CASES]


def _overlay_module(game):
    return importlib.import_module("partyplanner64.lib.adapter.%s_u_boardoverlay" % game)


def _first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            line = a.count("\n", 0, i) + 1
            return "first difference at char %d (line %d): %r vs %r" % (
                i, line, a[max(0, i - 80):i + 80], b[max(0, i - 80):i + 80])
    return "lengths differ: %d vs %d" % (len(a), len(b))


def _assert_same(actual, expected):
    if actual != expected:
        pytest.fail(_first_difference(actual, expected))


# --- Stand-ins for the modules of other areas ---

class _Event:
    def __init__(self, id_):
        self.id = id_


def _for_each_event(board, fn):
    boardevents = board.get("boardevents")
    if boardevents:
        for i in range(len(boardevents) - 1, -1, -1):
            fn(boardevents[i], i)
    for s, space in enumerate(board.get("spaces") or []):
        events = space.get("events")
        if events:
            for i in range(len(events) - 1, -1, -1):
                fn(events[i], i, space, s)


def _get_spaces_of_subtype(subtype, board):
    return [i for i, sp in enumerate(board["spaces"]) if sp and sp.get("subtype") == subtype]


def _get_spaces_with_event(event_name, board):
    found = []

    def visit(event, event_index, space=None, space_index=None):
        if space is not None and event["id"] == event_name:
            found.append(space_index)
    _for_each_event(board, visit)
    return found


def _get_dead_space_index(board):
    if isinstance(board.get("_deadSpace"), int):
        return board["_deadSpace"]
    board["spaces"].append({"x": board["bg"]["width"] + 150, "y": board["bg"]["height"] + 100,
                            "z": 0, "type": 0})
    board["_deadSpace"] = len(board["spaces"]) - 1
    return board["_deadSpace"]


def _install(monkeypatch, modname, attrs):
    """Set attributes on a module, creating a stand-in module if it can't be imported."""
    try:
        mod = importlib.import_module(modname)
    except Exception:
        mod = types.ModuleType(modname)
        monkeypatch.setitem(sys.modules, modname, mod)
        parent_name, _, child = modname.rpartition(".")
        _install(monkeypatch, parent_name, {})
        monkeypatch.setattr(sys.modules[parent_name], child, mod, raising=False)
    for name, value in attrs.items():
        monkeypatch.setattr(mod, name, value, raising=False)
    return mod


def _install_stand_ins(monkeypatch, data, case):
    symbols = data["symbols"]
    lib = "partyplanner64.lib"
    _install(monkeypatch, lib + ".boards", {
        "get_spaces_of_subtype": _get_spaces_of_subtype,
        "get_spaces_of_sub_type": _get_spaces_of_subtype,
        "get_spaces_with_event": _get_spaces_with_event,
        "get_dead_space_index": _get_dead_space_index,
        "for_each_event": _for_each_event,
    })
    _install(monkeypatch, lib + ".events.builtin.events_common", {
        "BankEvent": _Event("BANK"), "BooEvent": _Event("BOO"),
        "ItemShopEvent": _Event("ITEMSHOP"), "Gate": _Event("GATE"),
    })
    _install(monkeypatch, lib + ".symbols.symbols", {
        "get_symbol": lambda game, name: symbols[name],
    })
    prepped = case["prepped"]
    indices = list(range(len(case["board"]["additionalbg"]))) if case["board"].get("additionalbg") else None
    _install(monkeypatch, lib + ".events.additionalbg", {
        "get_board_additional_bg_hvq_indices": lambda board: indices,
        "get_additional_bg_asm_for_overlay": lambda board, bg_dir, idx: prepped["additionalBgCode"],
    })
    _install(monkeypatch, lib + ".events.getaudiochoice", {
        "get_audio_index_asm_for_overlay": lambda board, audio_indices: prepped["audioIndexCode"],
    })
    _install(monkeypatch, lib + ".adapter.boardinfo", {
        "get_arrow_rotation_limit": lambda: 8,
    })


@pytest.mark.parametrize("game,index", _CASES, ids=_IDS)
def test_overlay_isolated(monkeypatch, game, index):
    data = _DATA[game]
    case = data["cases"][index]
    _install_stand_ins(monkeypatch, data, case)
    module = _overlay_module(game)
    board = copy.deepcopy(case["board"])
    asm = module.create_board_overlay(board, dict(case["boardInfo"]), case["boardIndex"],
                                      list(case["audioIndices"]))
    _assert_same(asm, case["asm"])
    assert board.get("_deadSpace") == case["deadSpaceIndex"]


def _real_modules_available():
    try:
        boards = importlib.import_module("partyplanner64.lib.boards")
        importlib.import_module("partyplanner64.lib.events.builtin.events_common")
        importlib.import_module("partyplanner64.lib.symbols.symbols")
        importlib.import_module("partyplanner64.lib.events.additionalbg")
        importlib.import_module("partyplanner64.lib.events.getaudiochoice")
        importlib.import_module("partyplanner64.lib.adapter.boardinfo")
        importlib.import_module("partyplanner64.lib.adapter.adapters")  # get_dead_space_index
        importlib.import_module("partyplanner64.lib.romhandler")  # additionalbg
        return hasattr(boards, "get_dead_space_index")
    except Exception:
        return False


def _ensure_builtin_events():
    try:
        importlib.import_module("partyplanner64.lib.events.builtin.events_include")
    except Exception:
        pass


@pytest.mark.skipif(not _real_modules_available(),
                    reason="the boards/events/symbols/boardinfo modules aren't ported yet")
@pytest.mark.parametrize("game,index", _CASES, ids=_IDS)
def test_overlay_integration(game, index):
    _ensure_builtin_events()
    data = _DATA[game]
    case = data["cases"][index]
    module = _overlay_module(game)
    board = copy.deepcopy(case["board"])
    asm = module.create_board_overlay(board, dict(case["boardInfo"]), case["boardIndex"],
                                      list(case["audioIndices"]))
    _assert_same(asm, case["asm"])


@pytest.mark.skipif(not _real_modules_available(),
                    reason="the boardinfo module isn't ported yet")
@pytest.mark.parametrize("game", GAMES)
def test_board_info_values_match(game):
    """The board info values saved in the fixtures are those of E1's boardinfo port."""
    from partyplanner64.lib.adapter.boardinfo import get_board_info_by_index
    from partyplanner64.lib.types import Game
    game_id = {"mp1": Game.MP1_USA, "mp2": Game.MP2_USA, "mp3": Game.MP3_USA}[game]
    for case in _DATA[game]["cases"]:
        try:
            info = get_board_info_by_index(game_id, case["boardIndex"])
        except ModuleNotFoundError as e:
            pytest.skip("boardinfo isn't fully ported yet: %s" % e)
        for key, value in case["boardInfo"].items():
            actual = info.get(key)
            if isinstance(actual, tuple):
                actual = list(actual)
            assert actual == value, (case["name"], key)


@pytest.mark.parametrize("game", GAMES)
def test_missing_mainfs_event_file_fails(game):
    """Boards without an event file (duel boards) can't get an overlay, as in the TS."""
    data = _DATA[game]
    if data["missingEventFileError"] is None:
        pytest.skip("every board of this game has an event file")
    module = _overlay_module(game)
    board = copy.deepcopy(data["cases"][0]["board"])
    with pytest.raises(TypeError):
        module.create_board_overlay(board, {"bg_dir": 1, "board_def_file": 1}, 0, [1])


def test_templates_are_clean():
    """No unconverted ${...} and only known <<placeholders>> in the templates."""
    import re
    from partyplanner64.lib.adapter.overlayutils import load_overlay_template
    for game in GAMES:
        text = load_overlay_template(game + "_u_boardoverlay.s.tmpl")
        assert "${" not in text and "`" not in text
        stripped = re.sub(r"<<[A-Za-z0-9_]+>>", "", text)
        assert "<<" not in stripped and ">>" not in stripped


def test_shuffle_seed_data():
    from partyplanner64.lib.adapter.overlayutils import get_shuffle_seed_data
    assert get_shuffle_seed_data(8) == {"order": [1, 2, 3, 0, 4, 5, 6, 7],
                                        "bias": [0, 0, 0, 1, 1, 1, 1, 2]}
    assert get_shuffle_seed_data(0) == {"order": [0], "bias": [0]}
    assert len(get_shuffle_seed_data(1)["order"]) == 24
    assert len(get_shuffle_seed_data(9)["bias"]) == 31


def test_js_str():
    from partyplanner64.lib.adapter.overlayutils import js_join, js_str
    assert js_str(None) == "undefined"
    assert js_str(3.0) == "3"
    assert js_str(-0.5) == "-0.5"
    assert js_str(1.5e-6) == "0.0000015"
    assert js_str(1e-7) == "1e-7"
    assert js_join([1, None, 2]) == "1,,2"
    assert js_join([]) == ""
