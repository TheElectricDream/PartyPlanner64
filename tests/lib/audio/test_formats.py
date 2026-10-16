"""Differential tests of the audio structures, VADPCM, WAV and MIDI against the TypeScript.

The reference outputs come from tests/fixtures/audio/gen_audio.ts.
"""

import json
from pathlib import Path

import pytest

from partyplanner64.lib.audio.fxd0 import FXD0
from partyplanner64.lib.audio.mbf0 import MBF0
from partyplanner64.lib.audio.midi import create_game_midi, parse_game_midi
from partyplanner64.lib.audio.s2 import S2
from partyplanner64.lib.audio.sbf0 import SBF0
from partyplanner64.lib.audio.t3 import T3
from partyplanner64.lib.audio.vadpcm import decode_vadpcm
from partyplanner64.lib.audio.wav import extract_wav_from_sound, extract_wav_sound
from partyplanner64.lib.utils.dataview import DataView

from ._compare import assert_matches

REF = json.loads((Path(__file__).parents[2] / "fixtures" / "audio" / "audio_ref.json").read_text())


class _Book:
    def __init__(self, d):
        self.order = d["order"]
        self.npredictors = d["npredictors"]
        self.predictors = d["predictors"]


@pytest.mark.parametrize("case", REF["vadpcm"])
def test_vadpcm(case):
    tbl = bytearray.fromhex(case["tbl"])
    out = bytearray(case["len"] * 8)
    n = decode_vadpcm(DataView(tbl), out, case["len"], _Book(case["book"]), case["half"])
    assert n == case["samples"]
    assert out[:n * 2].hex() == case["out"]


def test_s2():
    ref = REF["s2"]
    s2 = S2(DataView(bytearray.fromhex(ref["input"])))
    assert_matches(ref["parsed"], s2)
    assert s2.get_byte_length() == ref["byteLength"]
    packed = bytearray(s2.get_byte_length())
    assert s2.pack(packed) == ref["packedLen"]
    assert packed.hex() == ref["packed"]
    bank = s2.soundbanks.banks[0]
    wavs = []
    for i, inst in enumerate(bank.instruments):
        for s in range(len(inst.sounds)):
            wavs.append(extract_wav_sound(s2.tbl, bank, i, s).hex())
    assert wavs == ref["wavs"]
    buf = s2.midis[0]["buffer"]
    assert parse_game_midi(DataView(buf), len(buf)).hex() == ref["midi"]


def test_mbf0():
    ref = REF["mbf0"]
    mbf0 = MBF0(DataView(bytearray.fromhex(ref["input"])))
    assert_matches(ref["parsed"], mbf0)
    assert mbf0.midis[0]["buffer"] is mbf0.midis[2]["buffer"]
    assert mbf0.get_byte_length() == ref["byteLength"]
    packed = bytearray(mbf0.get_byte_length())
    assert mbf0.pack(packed) == ref["packedLen"]
    assert packed.hex() == ref["packed"]


def test_sbf0():
    ref = REF["sbf0"]
    sbf0 = SBF0(DataView(bytearray.fromhex(ref["input"])))
    assert_matches(ref["parsed"], sbf0)
    wavs = [extract_wav_from_sound(sbf0.tbl, s, s.sample_rate).hex() for s in sbf0.sounds]
    assert wavs == ref["wavs"]


def test_t3_and_fxd0():
    t3 = T3(DataView(bytearray.fromhex(REF["t3"]["input"])))
    assert_matches(REF["t3"]["parsed"], t3)
    fxd0 = FXD0(DataView(bytearray.fromhex(REF["fxd0"]["input"])))
    assert_matches(REF["fxd0"]["parsed"], fxd0)


@pytest.mark.parametrize("case", REF["midi"])
def test_create_and_parse_game_midi(case):
    std = bytes.fromhex(case["std"])
    for key, loop in (("noloop", False), ("loop", True)):
        game = create_game_midi(std, {"loop": loop})
        assert game.hex() == case[key]
        assert parse_game_midi(DataView(game), len(game)).hex() == case[key + "_parsed"]


def test_parse_game_midi_repeats():
    ref = REF["gameMidiRepeat"]
    buf = bytearray.fromhex(ref["input"])
    assert parse_game_midi(DataView(buf), len(buf)).hex() == ref["parsed"]


def test_create_game_midi_rejects_non_midi():
    assert create_game_midi(b"RIFF" + bytes(20)) is None
