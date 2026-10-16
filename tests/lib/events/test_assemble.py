"""Custom event test assembly/compilation and board code tests, against the TypeScript.

Needs agent A's assembler (partyplanner64.lib.mips) and, for C, the C compiler
(partyplanner64.lib.utils.c_compiler, which needs wasmtime).
"""

import hashlib
import importlib
import json
import os

import pytest

from partyplanner64.lib.events import additionalbg, getaudiochoice
from partyplanner64.lib.events.customevents import (
    CustomAsmHelper, create_custom_event, validate_custom_event)
from partyplanner64.lib.types import Game

from . import romstub

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "events")
with open(os.path.join(FIXTURES, "assemble.json"), encoding="utf-8") as _f:
    REF = json.load(_f)


def _read(name):
    with open(os.path.join(FIXTURES, "corpus", name), encoding="utf-8", newline="") as f:
        return f.read()


def _need(module, reason):
    try:
        importlib.import_module(module)
    except ImportError as e:
        pytest.skip("%s (%s)" % (reason, e))


def _need_assembler():
    _need("partyplanner64.lib.mips", "the MIPS assembler (agent A) is missing")
    _need("partyplanner64.lib.symbols.symbols", "the symbols module (agent B) is missing")
    _need("partyplanner64.lib.adapter.boardinfobase", "the adapters' board info (agent E1) is missing")


def _need_compiler():
    _need("wasmtime", "wasmtime is not installed")
    _need("partyplanner64.lib.utils.c_compiler", "the C compiler (agent A) is missing")


@pytest.fixture(autouse=True)
def _no_rom(monkeypatch):
    romstub.install(monkeypatch, None)


@pytest.mark.parametrize("name", sorted(REF["events"]))
def test_custom_event_assembly(name):
    _need_assembler()
    if name.endswith(".c"):
        _need_compiler()
    code = _read(name)
    lang = 1 if name.endswith(".c") else 0
    expected = REF["events"][name]
    event = create_custom_event(lang, code)
    try:
        got = validate_custom_event(event)
    except Exception as e:
        got = "Error: %s" % e
    assert got == expected["validate"]

    for game, exp in expected["games"].items():
        try:
            r = CustomAsmHelper.test_custom_event(lang, code, event.parameters, {"game": Game(game)})
            if not isinstance(r, str):
                r = "%s:%d" % (hashlib.md5(bytes(r)).hexdigest(), len(r))
        except Exception as e:
            r = {"error": "Error: %s" % e}
        assert r == exp, (name, game)


@pytest.mark.parametrize("game", ["1", "2", "3"])
def test_board_code_tests(game):
    _need_assembler()
    board = {"game": int(game), "additionalbg": ["x", "y"], "audioData": [{}, {}]}
    bad = "  j missing_label\n  nop"
    exp_bg = REF["bg"][game]
    exp_audio = REF["audio"][game]
    assert additionalbg.test_additional_bg_code_all_games(additionalbg.default_additional_bg_asm, 0, board) == exp_bg[0]
    assert additionalbg.test_additional_bg_code_all_games(bad, 0, board) == exp_bg[1]
    assert getaudiochoice.test_get_audio_code_all_games(getaudiochoice.default_get_audio_asm, 0, board) == exp_audio[0]
    assert getaudiochoice.test_get_audio_code_all_games(bad, 0, board) == exp_audio[1]
    _need_compiler()
    assert additionalbg.test_additional_bg_code_all_games(additionalbg.default_additional_bg_c, 1, board) == exp_bg[2]
    assert getaudiochoice.test_get_audio_code_all_games(getaudiochoice.default_get_audio_c, 1, board) == exp_audio[2]
