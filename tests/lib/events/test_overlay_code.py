"""Board code for the overlays and custom event writing, against the TypeScript (overlay.json)."""

import importlib
import json
import os

import pytest

from partyplanner64.lib.events.additionalbg import (
    default_additional_bg_c, get_additional_bg_asm_for_overlay)
from partyplanner64.lib.events.customevents import write_custom_event
from partyplanner64.lib.events.getaudiochoice import (
    default_get_audio_c, get_audio_index_asm_for_overlay)
from partyplanner64.lib.types import Game

from . import romstub

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "events")
with open(os.path.join(FIXTURES, "overlay.json"), encoding="utf-8") as _f:
    REF = json.load(_f)


def _read(name):
    with open(os.path.join(FIXTURES, "corpus", name), encoding="utf-8", newline="") as f:
        return f.read()


def _need_compiler():
    for module in ("wasmtime", "partyplanner64.lib.utils.c_compiler"):
        try:
            importlib.import_module(module)
        except ImportError as e:
            pytest.skip("C compiler unavailable: %s" % e)


@pytest.fixture(autouse=True)
def _mp3(monkeypatch):
    romstub.install(monkeypatch, Game.MP3_USA)


def test_additional_bg_asm_for_overlay():
    assert get_additional_bg_asm_for_overlay({}, 5, [6, 7]) == REF["bg"][0]
    assert get_additional_bg_asm_for_overlay(
        {"additionalbgcode": "LI V0 ADDITIONAL_BG_2\nJR RA\nNOP"}, 5, None) == REF["bg"][1]
    _need_compiler()
    assert get_additional_bg_asm_for_overlay(
        {"additionalbgcode": {"language": 1, "code": default_additional_bg_c}}, 5, [6]) == REF["bg"][2]


def test_audio_index_asm_for_overlay():
    assert get_audio_index_asm_for_overlay({}, [3]) == REF["audio"][0]
    assert get_audio_index_asm_for_overlay(
        {"audioSelectCode": {"language": 0, "code": "LI V0 MUSIC_TRACK_INDEX_2\nJR RA\nNOP"}},
        [3, 9]) == REF["audio"][1]
    _need_compiler()
    assert get_audio_index_asm_for_overlay(
        {"audioSelectCode": {"language": 1, "code": default_get_audio_c}}, [3, 9]) == REF["audio"][2]


def test_write_custom_event():
    from partyplanner64.lib.adapter.boardinfobase import dummy_board_info
    info = {"game": Game.MP3_USA, "audio_indices": [2], "board_info": dummy_board_info,
            "board": {"additionalbg": ["a"]}, "chains": [[0, 1], [2, 3, 4]], "cur_space_index": 1}
    assert write_custom_event(None, {"id": "CRLF Event"}, info, 0, _read("crlf.s"), {}) == REF["write"][1]
    _need_compiler()
    got = write_custom_event(None, {"id": "Good C", "parameterValues": {"coins": 3, "target": 4, "flag": True}},
                             info, 1, _read("good.c"), {})
    assert got == REF["write"][0]
