"""Differential tests of the editor store against the TypeScript (boardState.ts + redux-undo).

The scenarios (tests/fixtures/editor/board_state_scenarios.json, written by
gen_scenarios.py) were run through the original Redux store by
gen_board_state.ts; board_state_expected.json holds the state after each step.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from partyplanner64.editor import board_state as bs
from partyplanner64.editor import ops
from partyplanner64.editor.boards import _make_default_board
from partyplanner64.editor.jsjson import to_js_value
from partyplanner64.editor.store import EditorStore, normalize_action_type

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "editor"
SCENARIOS = json.loads((FIXTURES / "board_state_scenarios.json").read_text())
EXPECTED = {s["name"]: s for s in json.loads((FIXTURES / "board_state_expected.json").read_text())}


def _builtin_events():
    from partyplanner64 import state
    from partyplanner64.lib.events.event_library import get_events_in_library
    state._load_builtin_events()
    return {k: v for k, v in get_events_in_library().items() if not v.custom}


def _hash_images(value):
    if isinstance(value, dict):
        return {k: _hash_images(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_hash_images(v) for v in value]
    if isinstance(value, str) and value.startswith("data:image/"):
        return "img:" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return value


def _make_board(spec):
    from partyplanner64.lib.boards import fix_potentially_old_board
    if "default" in spec:
        return _make_default_board(spec["default"][0], spec["default"][1])
    return fix_potentially_old_board(copy.deepcopy(spec["board"]))


def _snapshot(store):
    p = store.state
    return _hash_images(to_js_value({
        "boards": p.boards,
        "romBoards": p.rom_boards,
        "currentBoardIndex": p.current_board_index,
        "currentBoardIsROM": p.current_board_is_rom,
        "selectedSpaceIndices": sorted(int(i) for i in p.selected_space_indices),
        "highlightedSpaceIndices": p.highlighted_space_indices,
        "temporaryConnections": p.temporary_connections,
        "customEvents": {k: v.asm for k, v in store.event_library.items() if v.custom},
        "past": len(store.history.past),
        "future": len(store.history.future),
    }))


def _run_step(store, step):
    if step.get("undo"):
        return store.undo()
    if step.get("redo"):
        return store.redo()
    if step.get("clear"):
        return store.clear_history()
    action_type = normalize_action_type(step["op"])
    if action_type == "addBoardAction":
        args = dict(step["args"], board=_make_board(step["args"]["board"]))
        return store.dispatch(action_type, args)
    action_type, payload = ops.prepare(step["op"], copy.deepcopy(step["args"]))
    return store.dispatch(action_type, payload)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_scenario(scenario):
    store = EditorStore()
    store.event_library.update(_builtin_events())
    store.dispatch("setBoardsAction", {"boards": [_make_board(b) for b in scenario["boards"]]})
    for spec in scenario.get("romBoards") or []:
        board = _make_board(spec)
        board["_rom"] = True
        store.dispatch("addBoardAction", {"board": board, "rom": True})
    store.clear_history()

    expected = EXPECTED[scenario["name"]]["steps"]
    for i, step in enumerate(scenario["steps"]):
        error = False
        try:
            _run_step(store, step)
        except Exception:  # noqa: BLE001
            error = True
        assert error == expected[i]["error"], "step %d %s" % (i, step)
        got = _snapshot(store)
        want = expected[i]["state"]
        for key in want:
            if key in ("past", "future") and step.get("op") == "removeEventFromLibrary":
                # Deviation: the library is not part of the undo history here
                # (in the TypeScript, undoing could bring a deleted event back).
                continue
            assert got[key] == want[key], "step %d %s: %s differs" % (i, step, key)


def test_default_boards_match_typescript():
    """_makeDefaultBoard for each game and type, theme images included."""
    want = EXPECTED["board list"]["steps"][0]["state"]
    got = _hash_images(to_js_value([_make_default_board(1), _make_default_board(2),
                                    _make_default_board(3, "DUEL")]))
    assert got == want["boards"]
    rom_board = _make_default_board(3, "NORMAL")
    rom_board["_rom"] = True
    assert _hash_images(to_js_value(rom_board)) == want["romBoards"][0]


def test_reducer_names_complete():
    """Every reducer of boardState.ts has a handler."""
    import re
    names = {
        "setBoardsAction", "addBoardAction", "deleteBoardAction", "setCurrentBoardAction",
        "clearBoardsFromROMAction", "copyCurrentBoardAction", "setBoardNameAction",
        "setBoardDescriptionAction", "setBoardDifficultyAction",
        "setBoardCostumeTypeIndexAction", "setBackgroundAction", "setBoardOtherBgAction",
        "addAnimationBackgroundAction", "removeAnimationBackgroundAction",
        "addAdditionalBackgroundAction", "removeAdditionalBackgroundAction",
        "setAdditionalBackgroundCodeAction", "setAudioSelectCodeAction", "setBoardAudioAction",
        "addConnectionAction", "eraseConnectionsAction", "setTemporaryUIConnections",
        "addSpaceAction", "removeSpaceAction", "removeSpacesAction", "setSpacePositionsAction",
        "setSpaceTypeAction", "setSpaceSubtypeAction", "setSpaceHostsStarAction",
        "setSpaceRotationAction", "addSelectedSpaceAction", "setSelectedSpaceAction",
        "setSelectedSpacesAction", "clearSelectedSpacesAction", "setHighlightedSpacesAction",
        "setSelectionBoxCoordsAction", "changeCurrentEventAction", "addEventToLibraryAction",
        "removeEventFromLibraryAction", "addEventToBoardAction", "removeEventFromBoardAction",
        "includeEventInBoardAction", "excludeEventFromBoardAction",
        "setHoveredBoardEventIndexAction", "setBoardEventActivationTypeAction",
        "setBoardEventEventParameterAction", "addEventToSpaceAction", "addEventToSpacesAction",
        "removeEventFromSpaceAction", "removeEventsFromSpacesAction",
        "setSpaceEventActivationTypeAction", "setSpaceEventsActivationTypeAction",
        "setSpaceEventEventParameterAction", "setSpaceEventsEventParameterAction",
    }
    assert names == set(bs.REDUCERS) | bs.LIBRARY_ACTIONS
    assert all(re.match(r"^[a-z]", n) for n in names)
