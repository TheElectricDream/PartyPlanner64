"""boards.py helpers, against the TypeScript (fixtures/boards/helpers.json)."""

import copy
import json
import os

import pytest

from partyplanner64.lib import boards as B
from partyplanner64.lib.events.builtin import events_include  # noqa: F401
from partyplanner64.lib.events.customevents import create_custom_event
from partyplanner64.lib.events.event_library import get_events_in_library
from partyplanner64.lib.events.events import create_event_instance, get_available_events, get_event

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load(*parts):
    with open(os.path.join(FIXTURES, *parts), encoding="utf-8") as f:
        return json.load(f)


BOARDS = _load("validation", "boards.json")
OLD = _load("boards", "old_boards.json")
REF = _load("boards", "helpers.json")


def plain(value):
    """JSON round trip (int link keys become strings, as in the TypeScript's JSON)."""
    return json.loads(json.dumps(value))


@pytest.mark.parametrize("name", sorted(BOARDS))
@pytest.mark.parametrize("normalized", [False, True])
def test_helpers(name, normalized):
    ref = REF["boards"][name]
    b = copy.deepcopy(BOARDS[name])
    if normalized:
        B._normalize_links(b)
        assert all(isinstance(k, int) for k in b["links"])
    n = len(b["spaces"])
    assert B.get_dead_ends(b) == ref["deadEnds"]
    assert B.get_start_space_index(b) == ref["start"]
    assert [B.get_spaces_of_type(t, b) for t in range(21)] == ref["types"]
    assert [B.get_spaces_of_sub_type(t, b) for t in range(9)] == ref["subtypes"]
    assert B.get_spaces_with_event("BANK", b) == ref["withBank"]
    connections = []
    has = []
    for i in range(-1, min(n, 12) + 1):
        connections.append(B.get_connections(i, b))
        row = [B.has_connection(i, "*", b), B.has_connection(i, None, b)]
        row += [B.has_connection(i, j, b) for j in range(min(n, 12) + 1)]
        has.append(row)
    assert connections == ref["connections"]
    assert has == ref["has"]

    visits = []
    B.for_each_event(b, lambda ev, ei, space=None, si=None: visits.append([ev["id"], ei, si]))
    assert visits == ref["visits"]

    params = []
    try:
        B.for_each_event_parameter(
            b, get_events_in_library(),
            lambda p, ev, ei, space=None, si=None: params.append([p["name"], p["type"], ev["id"], ei, si]))
        got_params = params
    except Exception as e:
        got_params = {"error": "Error: %s" % e}
    if isinstance(ref["params"], dict):
        assert isinstance(got_params, dict)  # (A TypeError in the TypeScript.)
    else:
        assert got_params == ref["params"]

    assert [B.get_board_event(b, id) for id in list(b["events"]) + ["missing"]] == ref["boardEvents"]
    assert B.get_additional_background_code(b) == ref["bgCode"]
    assert B.get_audio_select_code(b) == ref["audioCode"]
    assert [B.supports_animation_backgrounds(b), B.supports_additional_backgrounds(b),
            B.get_space_index(b["spaces"][2], b), B.get_space_index({}, b)] == ref["supports"]

    c = copy.deepcopy(b)
    for s, e in [[0, 0], [0, 1], [0, 2], [0, 3], [0, 2], [7, 1], [7, -1], [-1, 3], [8, 2], [8, 3],
                 [8, 4], [99, 1]]:
        B.add_connection_internal(s, e, c)
    assert plain(c["links"]) == ref["afterAdds"]
    if normalized:
        assert all(isinstance(k, int) for k in c["links"])
    else:
        assert all(isinstance(k, str) for k in c["links"])


@pytest.mark.parametrize("name", sorted(OLD))
def test_fix_potentially_old_board(name):
    board = copy.deepcopy(OLD[name])
    fixed = B.fix_potentially_old_board(board)
    assert fixed is board
    assert all(isinstance(k, int) for k in board["links"])
    assert plain(board) == REF["old"][name]


def test_add_event_to_space_internal():
    b = copy.deepcopy(BOARDS["mp3_custom_events"])
    lib = get_events_in_library()
    custom = create_custom_event(0, b["events"]["Main Entry"]["code"])
    inst = create_event_instance(custom, {"parameterValues": {"enabled": True}})
    ce = get_event("CRLF Event", b, lib)
    b["events"] = {}
    B.add_event_to_space_internal(b, b["spaces"][0], inst, True, dict(lib, **{custom.id: custom}))
    B.add_event_to_space_internal(b, b["spaces"][0], create_event_instance(lib["BANK"]), False, lib)
    B.add_event_to_space_internal(b, b["spaces"][3],
                                  create_event_instance(lib["BOO"], {"activationType": 3}), False, lib)
    added = REF["added"]
    assert plain(b["events"]) == added["events"]
    assert plain([b["spaces"][0], b["spaces"][3]]) == added["spaces"]
    assert ce.to_json() == added["crlf"]


def test_available_events():
    for g in ("1", "2", "3"):
        assert [e.id for e in get_available_events({"game": int(g)})] == REF["available"][g]


def test_dead_space():
    pytest.importorskip("partyplanner64.lib.adapter.adapters")
    b = copy.deepcopy(BOARDS["mp1_valid"])
    n = len(b["spaces"])
    assert B.get_dead_space_index(b) == n
    assert B.get_dead_space_index(b) == n
    space = B.get_dead_space(b)
    assert (space["x"], space["y"], space["type"]) == (960 + 150, 720 + 100, 0)
    assert b["_deadSpace"] == n


def test_get_dead_ends_deep_board():
    # A long path doesn't hit Python's recursion limit.
    count = 5000
    b = {"spaces": [{"x": 0, "y": 0, "z": 0, "type": 7}] +
         [{"x": i, "y": 0, "z": 0, "type": 1} for i in range(1, count)],
         "links": {i: i + 1 for i in range(count - 1)}}
    assert B.get_dead_ends(b) == [count - 1]
    b["links"][count - 1] = 0
    assert B.get_dead_ends(b) == []
