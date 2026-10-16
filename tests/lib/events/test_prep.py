"""Event code text transforms and custom event headers, against the TypeScript (prep.json)."""

import hashlib
import json
import os

import pytest

from partyplanner64.lib.events.additionalbg import (
    default_additional_bg_asm, default_additional_bg_c, make_additional_bg_defines,
    make_bg_symbol_labels, prep_additional_bg_asm, prep_additional_bg_c)
from partyplanner64.lib.events.customevents import CustomAsmHelper, create_custom_event
from partyplanner64.lib.events.getaudiochoice import (
    default_get_audio_asm, default_get_audio_c, make_audio_defines, make_audio_symbol_labels,
    make_fake_get_audio_indices, prep_get_audio_asm, prep_get_audio_c)
from partyplanner64.lib.events.prep_asm import (
    create_event_instance_label, make_game_symbol_labels, make_generic_symbols_for_addresses,
    make_parameter_symbol_labels, prep_asm, prep_generic_asm, prep_single_event_asm,
    scope_labels_static_by_default)
from partyplanner64.lib.events.prep_c import make_parameter_symbol_defines, prep_c
from partyplanner64.lib.types import Game

from . import romstub

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "events")


def _load_json(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


REF = _load_json("prep.json")
WRITES = _load_json("write.json")


def _read(name):
    with open(os.path.join(FIXTURES, "corpus", name), encoding="utf-8", newline="") as f:
        return f.read()


CORPUS = {name: _read(name) for name in sorted(os.listdir(os.path.join(FIXTURES, "corpus")))}
ASMS = dict(CORPUS)
for i, r in enumerate(WRITES["results"]):
    if isinstance(r, str):
        ASMS["write_%d" % i] = r
ASMS["defaultAdditionalBgAsm"] = default_additional_bg_asm
ASMS["defaultGetAudioAsm"] = default_get_audio_asm
ASMS["defaultAdditionalBgC"] = default_additional_bg_c
ASMS["defaultGetAudioC"] = default_get_audio_c


def attempt(fn):
    try:
        return fn()
    except Exception as e:  # The TypeScript printed String(error).
        return {"error": "Error: %s" % e}


def plain(value):
    return json.loads(json.dumps(value))


def digest(s):
    lines = s.split("\n")
    return {"md5": hashlib.md5(s.encode("utf-8")).hexdigest(), "lines": len(lines),
            "head": lines[:3], "tail": lines[-3:]}


def test_corpus_is_complete():
    assert set(ASMS) == set(REF["scope"])


@pytest.mark.parametrize("name", sorted(ASMS))
def test_scope_labels_static_by_default(name):
    asm = ASMS[name]
    got = [attempt(lambda: scope_labels_static_by_default(asm, True)),
           attempt(lambda: scope_labels_static_by_default(asm, False))]
    assert got == REF["scope"][name]


@pytest.mark.parametrize("name", sorted(ASMS))
def test_make_generic_symbols_for_addresses(name):
    assert make_generic_symbols_for_addresses(ASMS[name]) == REF["generic"][name]


@pytest.mark.parametrize("name", sorted(ASMS))
def test_create_custom_event_headers(name):
    asm = ASMS[name]
    lang = 1 if name.endswith(".c") else 0
    expected = REF["custom"][name]
    got = attempt(lambda: create_custom_event(lang, asm).to_json())
    assert got == expected
    games = CustomAsmHelper.read_supported_games(asm)
    assert (None if games is None else [g.value for g in games]) == REF["custom"][name + ":games"]
    assert CustomAsmHelper.read_discrete_property_set(asm, "PARAM") == REF["custom"][name + ":params"]
    assert CustomAsmHelper.clear_discrete_properties(
        asm, ["NAME", "GAMES", "EXECUTION", "PARAM"]) == REF["custom"][name + ":cleared"]


def test_write_discrete_properties():
    got = CustomAsmHelper.write_discrete_property_array(
        CustomAsmHelper.write_discrete_property("nop", "NAME", "x", ";"),
        "PARAM", ["Number|a", "Boolean|b"], "//")
    assert got == REF["custom"]["written"]


VALUE_SETS = [
    None,
    {},
    {"coins": 5, "flag": True, "target": 3, "amount": 7, "targets": [1, 3, 9], "numbers": [1, 2]},
    {"coins": "x", "flag": 0, "target": 9, "amount": -2, "targets": []},
    {"coins": 2.5, "flag": False, "target": 1, "targets": [4]},
]
INFOS = [
    {"chains": [[0, 1, 2], [3, 4], [5, 9]], "cur_space_index": 3},
    {"cur_space_index": -2, "test_compile": True},
    {"chains": [], "cur_space_index": 0},
]


def _space_event(event, v):
    space_event = {"id": event.id, "activationType": 3, "executionType": 1}
    if VALUE_SETS[v] is not None:
        space_event["parameterValues"] = VALUE_SETS[v]
    return space_event


@pytest.mark.parametrize("index", range(len(VALUE_SETS) * len(INFOS)))
def test_parameter_symbols(index):
    entry = REF["params"][index]
    event = create_custom_event(0, CORPUS["edge1.s"])
    space_event = _space_event(event, entry["v"])
    info = INFOS[entry["i"]]
    assert attempt(lambda: make_parameter_symbol_labels(event, space_event, info)) == entry["labels"]
    assert attempt(lambda: make_parameter_symbol_defines(event, space_event, info)) == entry["defines"]
    single = [[attempt(lambda: prep_single_event_asm(CORPUS[f], event, space_event, info, bool(n), n + 1))
               for f in ("edge1.s", "main_entry.s", "crlf.s")] for n in (0, 1)]
    assert single == entry["single"]


def test_misc():
    misc = REF["misc"]
    assert [create_event_instance_label(0, 0), create_event_instance_label(12, 3),
            create_event_instance_label(-4, 1)] == misc["labels"]
    assert prep_additional_bg_asm(default_additional_bg_asm, 7, [8, 9]) == misc["bgAsm"]
    assert prep_additional_bg_asm(CORPUS["edge1.s"], 0, None) == misc["bgAsmNull"]
    assert prep_additional_bg_c(default_additional_bg_c, 7, [8, 9]) == misc["bgC"]
    assert make_bg_symbol_labels(3, [4, 5, 6]) == misc["bgSyms"]
    assert make_additional_bg_defines(3, []) == misc["bgDefines"]
    assert prep_get_audio_asm(default_get_audio_asm, [12, 40]) == misc["audioAsm"]
    assert prep_get_audio_c(default_get_audio_c, [12]) == misc["audioC"]
    assert make_audio_symbol_labels([1, 2, 3]) == misc["audioSyms"]
    assert [make_audio_defines(None), make_audio_defines([5, 6])] == misc["audioDefines"]
    assert [make_fake_get_audio_indices({}),
            make_fake_get_audio_indices({"audioData": [{}, {}, {}]})] == misc["fakeAudio"]


@pytest.mark.parametrize("game", [g.value for g in Game])
def test_game_symbol_labels_and_prep_asm(game, monkeypatch):
    pytest.importorskip("partyplanner64.lib.symbols.symbols")
    romstub.install(monkeypatch, None)  # No ROM loaded: test-compile background indices.
    got = [attempt(lambda: digest("\n".join(make_game_symbol_labels(game, stubs))))
           for stubs in (True, False)]
    assert got == REF["games"][game]

    event = create_custom_event(0, CORPUS["edge1.s"])
    from partyplanner64.lib.adapter.boardinfobase import dummy_board_info

    def run():
        space_event = {"id": event.id, "activationType": 3, "executionType": 1,
                       "parameterValues": VALUE_SETS[2]}
        info = {"addr": 0x80123450, "game": game, "audio_indices": [3, 4],
                "board_info": dummy_board_info, "board": {"additionalbg": ["a", "b"]},
                "chains": INFOS[0]["chains"]}
        return [digest(prep_asm(CORPUS["edge1.s"], event, space_event, info)),
                digest(prep_generic_asm(CORPUS["crlf.s"], 0x80000000, game)),
                prep_c(CORPUS["event.c"], create_custom_event(1, CORPUS["event.c"]), space_event, info)]
    assert plain(attempt(run)) == REF["prepAsm"][game]
