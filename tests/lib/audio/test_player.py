"""Tests of the offline song renderer (midiplayer) and the mixer."""

import random
import struct
import sys
import types
from array import array

import pytest

from partyplanner64.lib.audio import midiplayer, soundplayer
from partyplanner64.lib.audio.midi import create_game_midi
from partyplanner64.lib.audio.playershared import Mixer, PackedVoice, resample_linear

from ._synth import NS, make_bank, make_midi, measure, vl


def _pcm(wav):
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    rate = struct.unpack_from("<I", wav, 24)[0]
    size = struct.unpack_from("<I", wav, 40)[0]
    return rate, array("h", wav[44:44 + size])


def test_mixer_matches_naive_sum():
    rnd = random.Random(5)
    mixer = Mixer()
    expected = [0.0] * 90000
    for _ in range(40):
        samples = [rnd.randrange(-32768, 32768) for _ in range(rnd.randrange(1, 9000))]
        start = rnd.randrange(0, 80000)
        gain = rnd.choice([0.1, 0.5, 1.0, 1.7, 3.0])
        length = rnd.choice([None, rnd.randrange(1, 9000)])
        mixer.add(start, PackedVoice(samples), gain, length)
        n = len(samples) if length is None else min(length, len(samples))
        g = round(gain * 65536) / 65536
        for i in range(n):
            if start + i < len(expected):
                expected[start + i] += samples[i] * g
    out = mixer.render()
    assert len(out) == mixer.length
    for i, v in enumerate(out):
        want = max(-32768, min(32767, int(expected[i] // 1)))
        assert abs(v - want) <= 1, (i, v, want)


def test_resample_linear():
    assert resample_linear([0, 10, 20], 0.5, 5) == [0, 5, 10, 15, 20]
    assert resample_linear([0, 10, 20, 30], 2.0, 3) == [0, 20, 30]
    assert resample_linear([1, 2], 1.0, 3) == [1, 2, 2]


def _midi_one_note(note=60, velocity=100, off_tick=48, program=0, division=96):
    ev = bytearray()
    ev += vl(0) + bytes([0xFF, 0x51, 3, 0x07, 0xA1, 0x20])  # 120 bpm
    ev += vl(0) + bytes([0xC0, program])
    ev += vl(0) + bytes([0x90, note, velocity])
    ev += vl(off_tick) + bytes([note, 0])  # running status note off
    ev += vl(0) + bytes([0xFF, 0x2F, 0])
    return (b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big")
            + division.to_bytes(2, "big") + b"MTrk" + len(ev).to_bytes(4, "big") + ev)


def test_render_one_note_is_cut_by_note_off():
    bank, tbl = make_bank(n_inst=1, seconds=1.0)
    # Half a beat at 120 bpm: 0.25 s.
    rate, pcm = _pcm(midiplayer.render_midi(_midi_one_note(note=48, off_tick=48), bank, tbl, 22050))
    assert rate == 22050
    assert len(pcm) == int(0.25 * 22050)
    assert max(map(abs, pcm)) > 0


def test_render_note_pitch_changes_length():
    bank, tbl = make_bank(n_inst=1, seconds=0.5)
    # No note off: the sample plays to its end; an octave up plays twice as fast.
    _, base = _pcm(midiplayer.render_midi(_midi_one_note(note=48, off_tick=100000), bank, tbl, 22050))
    _, octave = _pcm(midiplayer.render_midi(_midi_one_note(note=60, off_tick=100000), bank, tbl, 22050))
    assert abs(len(base) - 2 * len(octave)) <= 2


def test_render_unknown_program_is_silent():
    bank, tbl = make_bank(n_inst=1, seconds=0.5)
    _, pcm = _pcm(midiplayer.render_midi(_midi_one_note(program=5), bank, tbl, 22050))
    assert len(pcm) == 0


def test_render_speed():
    # A 60 s, 4 track song (3 minute songs take about three times as long).
    elapsed, wav = measure(seconds=60, tracks=4)
    assert len(wav) > 60 * 22050 * 2
    assert elapsed < 10


class _FakeAudio:
    def __init__(self, seq_table, sound_table):
        self.seq_table = seq_table
        self.sound_table = sound_table

    def get_sequence_table(self, index):
        return self.seq_table if index == 0 else None

    def get_sound_table(self, index):
        return self.sound_table if index == 0 else None


@pytest.fixture
def fake_rom(monkeypatch):
    bank, tbl = make_bank(n_inst=2, seconds=0.3)
    game_midi = create_game_midi(make_midi(seconds=2, tracks=2), {"loop": True})
    seq_table = NS(midis=[{"buffer": game_midi, "soundbank_index": 0}],
                   soundbanks=NS(banks=[bank]), tbl=tbl)
    sound = bank.instruments[0].sounds[0]
    sound_table = NS(sounds=[NS(wave=sound.wave, keymap=None, sample_rate=16000)], tbl=tbl)
    rom = NS(get_audio=lambda: _FakeAudio(seq_table, sound_table))
    module = types.ModuleType("partyplanner64.lib.romhandler")
    module.romhandler = NS(get_rom=lambda: rom)
    monkeypatch.setitem(sys.modules, "partyplanner64.lib.romhandler", module)
    return seq_table


def test_rom_actions(fake_rom):
    wav = midiplayer.render_sequence_wav(0, 0)
    rate, pcm = _pcm(wav)
    assert rate == 22050 and len(pcm) > 22050

    mid = midiplayer.export_midi(0, 0)
    assert mid[:4] == b"MThd"

    rate, pcm = _pcm(soundplayer.sound_wav(0, 0))
    assert rate == 16000 and len(pcm) > 0

    midiplayer.replace_midi(0, 0, _midi_one_note())
    assert fake_rom.midis[0]["buffer"] == create_game_midi(_midi_one_note(), {"loop": True})
    with pytest.raises(ValueError, match="Could not process midi"):
        midiplayer.replace_midi(0, 0, b"not a midi file at all")

    assert midiplayer.get_soundbank_count(0) == 1
    midiplayer.change_soundbank_index(0, 0, 0)
    with pytest.raises(ValueError, match="Invalid soundbank index"):
        midiplayer.change_soundbank_index(0, 0, 1)
