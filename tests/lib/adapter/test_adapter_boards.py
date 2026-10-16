"""Differential tests of boarddef and the adapters' board transforms against the TypeScript.

Fixtures: tests/fixtures/adapter/perspective.json (gen_perspective.ts) and
boards.json (gen_boards.ts).
"""

import copy

import pytest

from partyplanner64.lib.adapter import boarddef
from partyplanner64.lib.adapter.adapters import get_adapter

from .conftest import as_json, load_fixture

PERSPECTIVE = load_fixture("perspective.json")
BOARDS = load_fixture("boards.json")


@pytest.mark.parametrize("name", sorted(PERSPECTIVE))
def test_reverse_and_apply_perspective(name):
    ref = PERSPECTIVE[name]
    adapter = get_adapter(ref["game"], {})
    bg = dict(ref["bg"], src="")

    board = {"game": ref["game"], "bg": bg, "spaces": copy.deepcopy(ref["spaces"])}
    adapter._reverse_perspective(board)
    for got, exp in zip(board["spaces"], ref["reversed"]):
        assert (got["x"], got["y"], got["z"]) == (exp["x"], exp["y"], exp["z"])

    adapter._apply_perspective(board)
    assert as_json(board["spaces"]) == ref["roundtrip"]

    board2 = {"game": ref["game"], "bg": bg, "spaces": copy.deepcopy(ref["gameSpaces"])}
    adapter._apply_perspective(board2)
    assert as_json(board2["spaces"]) == ref["applied"]
    assert adapter.on_get_game_coords_from_board_coords(10, 20, 0, board2) == ref["coords"]


def _sample_board(name, game):
    board = copy.deepcopy(BOARDS["samples"][name])
    board["links"] = {int(k): v for k, v in board["links"].items()}
    board.update({"game": game, "type": "NORMAL", "events": {}, "bg": {"width": 960, "height": 720}})
    return board


CASES = sorted(BOARDS["results"])


@pytest.mark.parametrize("case", CASES)
def test_boarddef(case, fake_game):
    game, name = case.split(":")
    game = int(game)
    fake_game(game)
    ref = BOARDS["results"][case]
    board = _sample_board(name, game)

    chains = boarddef.determine_chains(board)
    assert chains == ref["chains"]

    boarddef.pad_chains(board, chains)
    assert chains == ref["paddedChains"]
    assert as_json(board) == ref["paddedBoard"]

    buffer = boarddef.create(board, chains)
    assert buffer.hex() == ref["boarddef"]

    parsed = boarddef.parse(bytes(buffer), {})
    assert as_json(parsed) == ref["parsed"]


@pytest.mark.parametrize("case", CASES)
def test_chain_star_gate_events(case, fake_game):
    game, name = case.split(":")
    game = int(game)
    fake_game(game)
    ref = BOARDS["results"][case]
    board = _sample_board(name, game)
    adapter = get_adapter(game, {})

    chains = boarddef.determine_chains(board)
    boarddef.pad_chains(board, chains)

    if "eventError" in ref:
        with pytest.raises(Exception):
            if game == 3:
                adapter._create_gate_events(board, {}, chains)
            adapter.on_create_chain_events(board, chains)
        return

    if game == 3:
        adapter._create_gate_events(board, {}, chains)
    adapter.on_create_chain_events(board, chains)
    adapter._create_star_events(board)
    if adapter.on_write_events:
        adapter.on_write_events(board)
    assert as_json(board) == ref["eventBoard"]


def test_get_chain_index_values_from_absolute_index():
    chains = [[0, 1, 2], [3, 4], [5]]
    assert boarddef.get_chain_index_values_from_absolute_index(chains, 4) == [1, 1]
    assert boarddef.get_chain_index_values_from_absolute_index(chains, 0) == [0, 0]
    assert boarddef.get_chain_index_values_from_absolute_index(chains, 9) == [-1, -1]


def test_parse_mp1_header(fake_game):
    fake_game(1)
    board = {"spaces": [{"x": 1.5, "y": 2.5, "z": 0, "type": 7}, {"x": 3, "y": 4, "z": 0, "type": 1}],
             "links": {0: 1, 1: 0}}
    chains = [[0, 1]]
    buffer = boarddef.create(board, chains)
    # MP1 has a 12 byte header with the chain offset twice.
    assert buffer[0:12].hex() == "000200000001000c002c002c"
    parsed = boarddef.parse(buffer, {})
    assert parsed["spaces"] == [{"type": 7, "x": 1.5, "y": 2.5, "z": 0.0},
                                {"type": 1, "x": 3.0, "y": 4.0, "z": 0.0}]
    assert parsed["links"] == {0: 1}
    assert parsed["_chains"] == [[0, 1]]
