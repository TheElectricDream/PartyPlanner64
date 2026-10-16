"""AUDIODETAILSISSUE with custom audio, which reads the ROM's soundbanks (stubbed here)."""

import base64
import types

from partyplanner64.lib.types import Game
from partyplanner64.lib.validation import validation_common  # noqa: F401
from partyplanner64.lib.validation.validationrules import get_rule

from ..events import romstub


def _rom(bank_count):
    seq_table = types.SimpleNamespace(soundbanks=types.SimpleNamespace(banks=[object()] * bank_count))
    audio = types.SimpleNamespace(get_sequence_table=lambda i: seq_table)
    return types.SimpleNamespace(get_audio=lambda: audio)


def _fails(board):
    return get_rule("AUDIODETAILSISSUE").fails({"board": board, "board_info": {}})


def test_custom_audio_entries(monkeypatch):
    romstub.install(monkeypatch, Game.MP3_USA, rom=_rom(3))
    board = {"audioType": 1, "audioData": [{"name": "a", "soundbankIndex": 3, "data": "x"}]}
    assert _fails(board) == "Soundbank index for custom audio is out of range (0 - 2)"
    board["audioData"][0]["soundbankIndex"] = -1
    assert _fails(board) == "Soundbank index for custom audio is out of range (0 - 2)"
    board["audioData"][0]["soundbankIndex"] = 1
    board["audioData"][0]["data"] = ""
    assert _fails(board) == "Custom audio was chosen, but a midi file was not uploaded."
    board["audioData"][0]["data"] = "no comma"
    assert _fails(board) == "Custom audio midi data could not be parsed into an ArrayBuffer."
    board["audioData"][0]["data"] = "data:audio/midi;base64," + base64.b64encode(b"nope").decode()
    assert _fails(board) == "Custom audio midi data could not be converted into game audio."


def test_in_game_audio(monkeypatch):
    romstub.install(monkeypatch, Game.MP3_USA, rom=_rom(3))
    assert _fails({"audioType": 0, "audioIndex": 4}) is False
    assert _fails({"audioType": 0}) == "Expected an audio track index to be defined."
    assert _fails({}) == "Expected audioType to be defined."
