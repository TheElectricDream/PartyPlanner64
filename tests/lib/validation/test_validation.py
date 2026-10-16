"""Validation rules on synthetic boards, against the TypeScript (fixtures/validation)."""

import copy
import importlib
import json
import os

import pytest

from partyplanner64.lib.events.builtin import events_include  # noqa: F401
from partyplanner64.lib.events.builtin.events_common import BankEvent, ItemShopEvent
from partyplanner64.lib.types import Game
from partyplanner64.lib.validation import validation
from partyplanner64.lib.validation.validationrules import get_rule

from ..events import romstub

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "validation")
with open(os.path.join(FIXTURES, "boards.json"), encoding="utf-8") as _f:
    BOARDS = json.load(_f)
with open(os.path.join(FIXTURES, "results.json"), encoding="utf-8") as _f:
    REF = json.load(_f)

GAMES = {1: Game.MP1_USA, 2: Game.MP2_USA, 3: Game.MP3_USA}
EVENTS = {"BANK": BankEvent, "ITEMSHOP": ItemShopEvent}

# Rules that test-assemble code need agent A's assembler.
ASSEMBLING_RULES = {"CUSTOMEVENTFAIL", "ADDITIONALBGCODEISSUE", "GETAUDIOINDEXCODEISSUE"}


def _have(module):
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


HAVE_ASSEMBLER = _have("partyplanner64.lib.mips") and _have("partyplanner64.lib.symbols.symbols")
HAVE_ADAPTERS = _have("partyplanner64.lib.adapter.boardinfo") and \
    _have("partyplanner64.lib.adapter.boardinfobase")


def _rule_args(args):
    if isinstance(args, dict) and "event" in args:
        args = dict(args)
        args["event"] = EVENTS[args["event"]]
    if isinstance(args, dict) and "disallowed" in args:
        args = dict(args)
        args["disallowed"] = {int(k): v for k, v in args["disallowed"].items()}
    return args


def _board_info():
    if HAVE_ADAPTERS:
        from partyplanner64.lib.adapter.boardinfobase import dummy_board_info
        return dummy_board_info
    return {"name": "Test Info", "board_def_file": 1, "bg_dir": 1, "str": {}, "img": {}}


@pytest.mark.parametrize("name", sorted(BOARDS))
def test_rules(name, monkeypatch):
    board_game = 3 if name == "mp2_on_other" else BOARDS[name]["game"]
    romstub.install(monkeypatch, GAMES[board_game])
    for (rule_id, args), expected in zip(REF["ruleList"], REF["rules"][name]):
        if rule_id in ASSEMBLING_RULES and not HAVE_ASSEMBLER:
            continue
        board = copy.deepcopy(BOARDS[name])
        try:
            got = get_rule(rule_id, _rule_args(args)).fails({"board": board, "board_info": _board_info()})
        except Exception as e:
            got = {"error": "Error: %s" % e}
        assert got == expected, (rule_id, args)


def _ts_shape(results):
    out = []
    for r in results:
        r = dict(r)
        if "forced_disabled" in r:
            r["forcedDisabled"] = r.pop("forced_disabled")
        r.pop("rom_board_index", None)
        out.append(r)
    return out


@pytest.mark.parametrize("name", sorted(BOARDS))
def test_validate_current_board_for_overwrite(name, monkeypatch):
    if not (HAVE_ASSEMBLER and HAVE_ADAPTERS):
        pytest.skip("needs the assembler (agent A) and adapters' board infos (agent E1)")
    for g in ("1", "2", "3"):
        romstub.install(monkeypatch, GAMES[int(g)])
        board = copy.deepcopy(BOARDS[name])
        rom_boards = [
            dict(copy.deepcopy(BOARDS["mp%s_valid" % g]), name="ROM A"),
            dict(copy.deepcopy(BOARDS["mp%s_many_subtypes" % g]), name="ROM B", type="DUEL"),
            dict(copy.deepcopy(BOARDS["mp%s_nine_stars" % g]), name="ROM C"),
        ]
        got = validation.validate_current_board_for_overwrite(rom_boards, board, False)
        assert _ts_shape(got) == REF["overwrite"][name][g], g


def test_no_rom(monkeypatch):
    romstub.install(monkeypatch, None)
    assert validation.validate_current_board_for_overwrite([], BOARDS["mp1_valid"]) is None
    assert validation.validate_board([], BOARDS["mp1_valid"]) == [
        {"level": 1, "message": "No ROM is loaded."}]


def test_validate_board_flattened(monkeypatch):
    if not (HAVE_ASSEMBLER and HAVE_ADAPTERS):
        pytest.skip("needs the assembler (agent A) and adapters' board infos (agent E1)")
    romstub.install(monkeypatch, Game.MP2_USA)
    rom_boards = [dict(copy.deepcopy(BOARDS["mp2_valid"]), name="ROM A"),
                  dict(copy.deepcopy(BOARDS["mp2_valid"]), name="ROM B")]
    got = validation.validate_board(rom_boards, copy.deepcopy(BOARDS["mp2_dead_end"]), 0)
    assert got == [{"level": 2, "message": "There is a dead end on the board."},
                   {"level": 1, "message": "There are 2 stars, but the count must be 7 for this board."}]
    got = validation.validate_board(rom_boards, copy.deepcopy(BOARDS["mp2_valid"]), 1)
    assert got == [{"level": 1, "message": "This board cannot be overwritten."}]
    assert validation.validate_board(rom_boards, BOARDS["mp2_valid"], 0, skip_validation=True) == []
