"""Test play of one event (lib/playtest/eventtest): its settings and its test board."""

import pytest

from partyplanner64.editor.boards import _make_default_board
from partyplanner64.lib import boards as lib_boards
from partyplanner64.lib.events.customevents import create_custom_event
from partyplanner64.lib.playtest import PlaytestError, eventtest
from partyplanner64.lib.types import Game, Space

CODE = """; NAME: Toll Booth
; GAMES: MP3_USA
; EXECUTION: Direct
; PARAM: +Number|toll
; PARAM: Boolean|loud
; PARAM: Number|offset
; PARAM: Space|exit
; PARAM: Space[]|tunnels

JR RA
NOP
"""


@pytest.fixture
def event():
    return create_custom_event(0, CODE)


def test_defaults(event):
    settings = eventtest.normalize_settings(event)
    assert settings == eventtest.default_settings(event)
    assert settings == {
        "activation": 3, "spaceType": int(Space.HAPPENING),
        "parameterValues": {"toll": 1, "loud": False, "offset": 0, "exit": 2, "tunnels": []},
    }


def test_settings_are_checked(event):
    settings = eventtest.normalize_settings(event, {
        "activation": 1, "spaceType": int(Space.RED),
        "parameterValues": {"toll": 20, "loud": True, "offset": -5, "exit": 0,
                            "tunnels": [1, 11], "gone": 3}})
    assert settings["activation"] == 1 and settings["spaceType"] == int(Space.RED)
    assert settings["parameterValues"] == {"toll": 20, "loud": True, "offset": -5, "exit": 0,
                                           "tunnels": [1, 11]}


@pytest.mark.parametrize("settings, message", [
    ({"activation": 7}, r"Land On \(3\) or Walk Over \(1\)"),
    ({"spaceType": int(Space.STAR)}, "Happening, Blue or Red"),
    ({"parameterValues": {"toll": 0}}, "toll must be a positive number"),
    ({"parameterValues": {"offset": 1.5}}, "offset must be a whole number"),
    ({"parameterValues": {"loud": 1}}, "loud is true or false"),
    ({"parameterValues": {"exit": 12}}, "exit must be one of the test board's spaces"),
    ({"parameterValues": {"tunnels": [2, 40]}}, "tunnels must be a list"),
    ([], "an object"),
])
def test_bad_settings(event, settings, message):
    with pytest.raises(PlaytestError, match=message):
        eventtest.normalize_settings(event, settings)


def test_lenient_settings_keep_what_fits(event):
    # Saved before the code changed: what no longer fits is the default again.
    settings = eventtest.normalize_settings(
        event, {"activation": 99, "parameterValues": {"toll": -1, "offset": 4}}, lenient=True)
    assert settings["activation"] == 3
    assert settings["parameterValues"]["toll"] == 1 and settings["parameterValues"]["offset"] == 4
    assert eventtest.normalize_settings(event, "junk", lenient=True) == \
        eventtest.default_settings(event)


def test_land_on_board(event):
    settings = eventtest.normalize_settings(event, {"spaceType": int(Space.BLUE),
                                                    "parameterValues": {"toll": 7}})
    new_board = _make_default_board(3)
    board = eventtest.build_board(new_board, event, settings)
    assert new_board["spaces"] != board["spaces"]           # a copy
    spaces = board["spaces"]
    assert len(spaces) == 2 + eventtest.LOOP_SPACES
    assert lib_boards.get_start_space_index(board) == 0
    assert spaces[1]["type"] == Space.OTHER and not spaces[1].get("events")
    loop = spaces[2:]
    assert all(s["type"] == Space.BLUE for s in loop)
    for s in loop:
        assert s["events"] == [{"id": "Toll Booth", "activationType": 3, "executionType": 1,
                                "parameterValues": settings["parameterValues"], "custom": True}]
    assert loop[0]["events"][0]["parameterValues"] is not loop[1]["events"][0]["parameterValues"]
    # The loop closes on the invisible space; nothing is a dead end.
    assert board["links"] == {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10,
                              10: 11, 11: 1}
    assert lib_boards.get_dead_ends(board) == []
    assert board["events"] == {"Toll Booth": {"language": 0, "code": CODE}}
    assert lib_boards.get_board_event(board, "Toll Booth")["code"] == CODE
    # Every space is on the background.
    for s in spaces:
        assert 0 < s["x"] < board["bg"]["width"] and 0 < s["y"] < board["bg"]["height"]
    assert board["bg"] == new_board["bg"] and board["game"] == 3


def test_walk_over_board(event):
    settings = eventtest.normalize_settings(event, {"activation": 1, "spaceType": int(Space.RED)})
    board = eventtest.build_board(_make_default_board(3), event, settings)
    events = [(i, s.get("events")) for i, s in enumerate(board["spaces"]) if s.get("events")]
    assert [i for i, _ in events] == [1]
    assert events[0][1][0]["activationType"] == 1
    # The loop is plain blue spaces, whatever spaceType says.
    assert all(s["type"] == Space.BLUE for s in board["spaces"][2:])


def test_space_names_match_the_board(event):
    board = eventtest.build_board(_make_default_board(3), event, eventtest.normalize_settings(event))
    names = {s["index"]: s["name"] for s in eventtest.spaces()}
    assert set(names) == set(range(len(board["spaces"])))
    assert board["spaces"][0]["type"] == Space.START and names[0] == "Start space"
    assert board["spaces"][1]["type"] == Space.OTHER and names[1].startswith("Invisible")


def test_unsupported(event):
    assert eventtest.unsupported_reason(event) is None
    assert eventtest.supports_game(event, Game.MP3_USA) and eventtest.supports_game(event, "NMVE")
    mp2 = create_custom_event(0, CODE.replace("MP3_USA", "MP2_USA"))
    assert "MP3_USA" in eventtest.unsupported_reason(mp2)
    builtin = mp2.copy()
    builtin.custom = False
    assert eventtest.unsupported_reason(builtin) == "Only custom events can be test-played."
    with pytest.raises(PlaytestError):
        eventtest.build_board(_make_default_board(3), builtin, eventtest.default_settings(event))


def test_describe(event):
    info = eventtest.describe(event)
    assert [a["name"] for a in info["activations"]] == ["Land On", "Walk Over"]
    assert [s["name"] for s in info["spaceTypes"]] == ["Happening", "Blue", "Red"]
    assert info["parameters"][0] == {"name": "toll", "type": "+Number"}
    assert info["defaults"] == eventtest.default_settings(event)
    assert len(info["spaces"]) == 12 and info["loopSpaces"] == 10
