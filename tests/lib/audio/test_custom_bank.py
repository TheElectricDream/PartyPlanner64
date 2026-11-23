"""Custom soundbanks (lib/audio/custom_bank.py): synthesis, ADPCM encoding, bank building,
adding banks to a bank file, recordings, budgets and previews.

What the game does with them was measured in an emulator (Mario Party 3 USA, high-level
audio): every note of a Game Boy bank played in tune (within 2 cents) with the harmonics
tested below, and a bank file bigger than the audio heap hangs the game at boot.
"""

import cmath
import io
import math
import os
import struct
import wave

import pytest

from partyplanner64.lib.audio import custom_bank as cb
from partyplanner64.lib.audio.b1 import B1
from partyplanner64.lib.audio.midiplayer import render_with_soundbank
from partyplanner64.lib.audio.vadpcm import decode_vadpcm_samples
from partyplanner64.lib.audio.wav import extract_wav_sound, read_wav_samples
from partyplanner64.lib.utils.dataview import DataView

ROM_DIRS = [os.environ.get("PP64_ROMS", ""),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "roms")]


class _Book:
    def __init__(self, predictors):
        self.order = 2
        self.npredictors = len(predictors) // 16
        self.predictors = predictors


def _harmonics(pcm, cycles, count=5):
    n = len(pcm)
    mags = [abs(sum(pcm[i] * cmath.exp(-2j * math.pi * cycles * h * i / n) for i in range(n)))
            for h in range(1, count + 1)]
    return [m / mags[0] for m in mags]


def _snr(original, decoded):
    err = math.sqrt(sum((a - b) ** 2 for a, b in zip(original, decoded)) / len(original))
    rms = math.sqrt(sum(v * v for v in original) / len(original))
    return 20 * math.log10(rms / max(err, 1e-9))


def _wav(samples, rate, loop=None):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))
    data = bytearray(out.getvalue())
    if loop:
        smpl = struct.pack("<9I", 0, 0, 0, 60, 0, 0, 0, 1, 0) + struct.pack("<6I", 0, 0, loop[0], loop[1] - 1, 0, 0)
        data += b"smpl" + struct.pack("<I", len(smpl)) + smpl
        struct.pack_into("<I", data, 4, len(data) - 8)
    return bytes(data)


# --- Checking -----------------------------------------------------------------------

def test_game_boy_bank_is_valid():
    bank = cb.game_boy_bank()
    assert cb.check_soundbank(bank) is None
    assert [i["name"] for i in bank["instruments"]][:3] == ["Pulse 12.5%", "Pulse 25%", "Pulse 50%"]


@pytest.mark.parametrize("bank, words", [
    ({"name": "x", "instruments": []}, "no instruments"),
    ({"name": "x", "instruments": [cb.default_instrument("p", {"type": "pulse", "duty": 0.3})]}, "duty"),
    ({"name": "x", "instruments": [cb.default_instrument("w", {"type": "wave", "pattern": "12"})]}, "32 hex"),
    ({"name": "x", "instruments": [cb.default_instrument("v", {"type": "pulse", "duty": 0.5}, volume=300)]}, "volume"),
    ({"name": "x", "instruments": [cb.default_instrument("s", {"type": "sample", "data": "nope"})]}, "could not be read"),
])
def test_check_soundbank_finds_problems(bank, words):
    assert words in cb.check_soundbank(bank)


# --- Synthesis -------------------------------------------------------------------

@pytest.mark.parametrize("duty", [0.5, 0.25, 0.125])
def test_pulse_harmonics(duty):
    # A pulse of duty d has harmonics |sin(pi k d)| / k.
    expect = [abs(math.sin(math.pi * k * duty)) / k / math.sin(math.pi * duty) for k in range(1, 6)]
    pcm, key, detune = cb._synth_band({"type": "pulse", "duty": duty}, 71)
    cycles = round(len(pcm) * cb._midi_hz(71) / cb.SAMPLE_RATE)
    assert [round(h, 2) for h in _harmonics(pcm, cycles)] == [round(e, 2) for e in expect]


def test_synth_bands_are_in_tune():
    for lo, hi, key in cb._BANDS:
        pcm, base, detune = cb._synth_band({"type": "wave", "pattern": "0123456789ABCDEFFEDCBA9876543210"}, key)
        assert base == key and -127 <= detune <= 127
        n = len(pcm)
        cycles = round(n * cb._midi_hz(key) / cb.SAMPLE_RATE)
        played = cycles * cb.SAMPLE_RATE / n * 2 ** (detune / 1200)
        assert abs(1200 * math.log2(played / cb._midi_hz(key))) < 1   # cents


def test_noise_is_noisy():
    pcm, _, _ = cb._noise_band({"type": "noise", "short": False}, 60)
    assert len(set(pcm)) == 2 and 0.3 < sum(v > 0 for v in pcm) / len(pcm) < 0.7


# --- ADPCM -------------------------------------------------------------------------

@pytest.mark.parametrize("src, min_snr", [
    ({"type": "pulse", "duty": 0.5}, 24),
    ({"type": "pulse", "duty": 0.125}, 18),
    ({"type": "wave", "pattern": "0123456789ABCDEFFEDCBA9876543210"}, 30),
])
def test_adpcm_round_trip(src, min_snr):
    pcm, _, _ = cb._synth_band(src, 71)
    book = cb.make_book()
    data, state = cb.encode_adpcm(pcm, (0, len(pcm)), book)
    assert len(data) == len(pcm) // 16 * 9
    decoded = decode_vadpcm_samples(DataView(bytearray(data)), len(data), _Book(book), False)
    assert _snr(pcm, decoded) > min_snr
    # The loop's state is the decoded frame holding the loop start, so passes match.
    assert state == decoded[:16]


def test_adpcm_loop_state_for_a_later_start():
    pcm = [int(8000 * math.sin(i / 7)) for i in range(800)]
    data, state = cb.encode_adpcm(pcm, (100, 800))
    decoded = decode_vadpcm_samples(DataView(bytearray(data)), len(data), _Book(cb.make_book([pcm])), False)
    assert state == decoded[96:112]


# --- Banks -------------------------------------------------------------------------

def _b1_with(banks):
    """A bank file holding these soundbanks (built by append_banks onto an empty file)."""
    empty = struct.pack(">hh", 0x4231, 0) + bytes(12)
    b1, tbl, first = cb.append_banks(empty, b"", banks)
    return b1, tbl


def _dump(bank):
    out = [bank.sample_rate]
    for inst in bank.instruments:
        out.append((inst.volume, inst.pan, inst.bend_range))
        for s in inst.sounds:
            w = s.wave
            lp = w.adpcm_wave.loop
            out.append((s.keymap.key_min, s.keymap.key_max, s.keymap.key_base, s.keymap.detune,
                        w.wave_base, w.wave_len, w.type, (lp.start, lp.end, lp.count, tuple(lp.state)),
                        tuple(w.adpcm_wave.book.predictors)))
    return out


def test_built_bank_parses_and_decodes():
    bank = cb.game_boy_bank()
    b1, tbl = _b1_with([bank])
    parsed = B1(DataView(bytearray(b1))).banks[0]
    assert parsed.sample_rate == 32000 and len(parsed.instruments) == len(bank["instruments"])
    pulse = parsed.instruments[2]
    assert [(s.keymap.key_min, s.keymap.key_max) for s in pulse.sounds] == [(lo, hi) for lo, hi, _ in cb._BANDS]
    for s in pulse.sounds:
        loop = s.wave.adpcm_wave.loop
        assert s.wave.type == 0 and loop.count == 0xFFFFFFFF and loop.start == 0
        assert loop.end * 9 // 16 == s.wave.wave_len
    rate, pcm = read_wav_samples(extract_wav_sound(tbl, parsed, 2, 3))
    expect = cb.instrument_sounds(bank["instruments"][2])[3][2]
    assert rate == 32000 and _snr(expect, pcm) > 20


def test_append_banks_moves_the_old_ones_intact():
    first_bank = {"name": "A", "instruments": [cb.default_instrument("p", {"type": "pulse", "duty": 0.5})]}
    b1, tbl = _b1_with([first_bank])
    before = [_dump(b) for b in B1(DataView(bytearray(b1))).banks]
    assert cb.append_banks(b1, tbl, [])[0] == b1
    gb = cb.game_boy_bank()
    b1b, tbl2, index = cb.append_banks(b1, tbl, [gb])
    assert index == 1 and tbl2[:len(tbl)] == tbl
    banks = B1(DataView(bytearray(b1b))).banks
    assert [_dump(b) for b in banks[:1]] == before
    assert len(banks[1].instruments) == len(gb["instruments"])
    assert len(cb.pointer_fields(b1b)) > len(cb.pointer_fields(b1))


def test_game_boy_bank_fits_the_budget():
    assert cb.bank_bytes(cb.game_boy_bank()) < cb.BANK_BUDGET["MP3_USA"]
    assert cb.budget_problem("NMVE", [cb.game_boy_bank()]) is None
    assert "fewer" in cb.budget_problem("MP3_USA", [cb.game_boy_bank()] * 2)
    assert "Mario Party 3" in cb.budget_problem("MP1_USA", [cb.game_boy_bank()])


class _SeqTable:
    def __init__(self, b1, tbl):
        self._soundback_buffer = bytearray(b1)
        self.tbl = bytearray(tbl)
        self.soundbanks = None


def test_add_soundbank_reuses_and_limits():
    b1, tbl = _b1_with([{"name": "A", "instruments": [cb.default_instrument("p", {"type": "pulse", "duty": 0.5})]}])
    table = _SeqTable(b1, tbl)
    gb = cb.game_boy_bank()
    assert cb.add_soundbank(table, gb, "NMVE") == 1
    renamed = dict(gb, name="Same sounds")
    assert cb.add_soundbank(table, renamed, "NMVE") == 1      # not added twice
    assert len(table.soundbanks.banks) == 2
    other = cb.game_boy_bank()
    other["instruments"][0]["volume"] = 90
    with pytest.raises(cb.SoundbankError, match="audio memory"):
        cb.add_soundbank(table, other, "NMVE")


# --- Recordings --------------------------------------------------------------------

def test_import_wav_resamples_and_keeps_the_loop():
    samples = [int(12000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(8000)]
    inst = cb.import_wav(_wav(samples, 16000, loop=(2000, 6000)), "Flute", 69)
    src = inst["source"]
    assert inst["name"] == "Flute" and src["type"] == "sample" and src["key"] == 69
    assert (src["loopStart"], src["loopEnd"]) == (4000, 12000)
    pcm = cb.sample_pcm(src)
    assert len(pcm) == 16000
    assert cb.check_soundbank({"name": "R", "instruments": [inst]}) is None
    # One sound per octave up from its key, each half as long as the one before.
    bands = cb.instrument_sounds(inst)
    assert bands[0][:2] == (0, 80) and bands[1][:2] == (81, 92) and bands[-1][1] == 127
    assert len(bands[1][2]) == len(pcm) // 2


def test_read_wav_formats():
    rate, chans, loop = cb.read_wav(_wav([0, 16384, -16384], 22050))
    assert rate == 22050 and chans == [[0.0, 0.5, -0.5]] and loop is None
    with pytest.raises(cb.SoundbankError):
        cb.read_wav(b"not a wav file at all")


# --- Previews ----------------------------------------------------------------------

def _midi(notes, program=2):
    """A standard MIDI file: program, then (key, beats) notes one after another (96 ppq)."""
    def vl(v):
        out = [v & 0x7F]
        v >>= 7
        while v:
            out.insert(0, (v & 0x7F) | 0x80)
            v >>= 7
        return bytes(out)
    ev = b"\x00\xc0" + bytes([program])
    for key, beats in notes:
        ev += b"\x00\x90" + bytes([key, 110]) + vl(int(beats * 96)) + b"\x80" + bytes([key, 0])
    ev += b"\x00\xff\x2f\x00"
    return (b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) + b"MTrk" + struct.pack(">I", len(ev)) + ev)


def test_preview_plays_in_tune_and_sustains():
    wav = render_with_soundbank(_midi([(69, 2), (57, 2)]), cb.game_boy_bank())
    with wave.open(io.BytesIO(wav)) as w:
        rate = w.getframerate()
        x = struct.unpack("<%dh" % w.getnframes(), w.readframes(w.getnframes()))
    for start, hz in ((0.2, 440.0), (1.2, 220.0)):   # 120 bpm: a note lasts 1 s
        seg = x[int(start * rate):int((start + 0.6) * rate)]
        # zero crossings upward
        ups = sum(1 for a, b in zip(seg, seg[1:]) if a < 0 <= b)
        assert abs(ups / 0.6 - hz) / hz < 0.02
        assert math.sqrt(sum(v * v for v in seg) / len(seg)) > 2000   # still sounding (looped)


# --- The real Mario Party 3 bank file -------------------------------------------------

def _find_rom():
    for d in ROM_DIRS:
        if d and os.path.isdir(d):
            for name in os.listdir(d):
                if name.lower().startswith("mario party 3") and name.lower().endswith((".z64", ".n64", ".v64")):
                    return os.path.join(d, name)
    return None


def test_real_mp3_bank_file():
    rom_file = _find_rom()
    if not rom_file:
        pytest.skip("no Mario Party 3 ROM in roms/ or $PP64_ROMS")
    from partyplanner64.cli import _load_rom, _setup_library
    from partyplanner64.lib.romhandler import romhandler
    _setup_library()
    assert _load_rom(rom_file)
    try:
        table = romhandler.get_rom().get_audio().get_sequence_table(0)
        before = [len(b.instruments) for b in table.soundbanks.banks]
        raw = bytes(table._soundback_buffer)
        b1, tbl, index = cb.append_banks(raw, table.tbl, [cb.game_boy_bank()])
        banks = B1(DataView(bytearray(b1))).banks
        assert index == len(before) and [len(b.instruments) for b in banks[:index]] == before
        # The game's own samples still decode the same from the new sound data.
        assert (read_wav_samples(extract_wav_sound(table.tbl, table.soundbanks.banks[20], 5, 0))
                == read_wav_samples(extract_wav_sound(tbl, banks[20], 5, 0)))
        assert len(b1) - len(raw) <= cb.BANK_BUDGET["MP3_USA"]
    finally:
        romhandler.clear()


def test_preview_volume_is_squared_and_bends_two_semitones():
    """As the game plays them (Mario Party 3, measured): controller 7 at 64 is a quarter of
    the amplitude; a full pitch bend is the instrument's 200 cents."""
    def amp_and_hz(vol, bend):
        ev = (b"\x00\xc0\x02\x00\xb0\x07" + bytes([vol]) + b"\x00\xe0" + bytes([bend & 0x7F, bend >> 7])
              + b"\x00\x90\x45\x6e\x81\x40\x80\x45\x00\x00\xff\x2f\x00")
        midi = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) + b"MTrk" + struct.pack(">I", len(ev)) + ev
        with wave.open(io.BytesIO(render_with_soundbank(midi, cb.game_boy_bank()))) as w:
            rate = w.getframerate()
            x = struct.unpack("<%dh" % w.getnframes(), w.readframes(w.getnframes()))
        seg = x[int(0.1 * rate):int(0.6 * rate)]
        ups = sum(1 for a, b in zip(seg, seg[1:]) if a < 0 <= b)
        return math.sqrt(sum(v * v for v in seg) / len(seg)), ups / 0.5
    full, hz = amp_and_hz(127, 8192)
    half, _ = amp_and_hz(64, 8192)
    _, up = amp_and_hz(127, 16383)
    assert abs(half / full - (64 / 127) ** 2) < 0.02
    assert abs(hz - 440) < 9 and abs(up - 493.9) < 10


# --- Game Boy music (scripts/gbs_to_midi.py) ------------------------------------------

def _gbs_module():
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "gbs_to_midi.py")
    spec = importlib.util.spec_from_file_location("gbs_to_midi", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _iodump(writes):
    """iodumper lines for (seconds, addr, value) writes."""
    out, last = [], 0
    for t, addr, val in writes:
        cyc = int(round(t * 4194304))
        out.append("%08x %04x=%02x" % (cyc - last, addr, val))
        last = cyc
    return out


def _pulse_note(t, freq, vol=15, period=0):
    return [(t, 0xFF11, 0x80), (t, 0xFF12, (vol << 4) | period), (t, 0xFF13, freq & 0xFF),
            (t, 0xFF14, 0x80 | (freq >> 8))]


def test_gbs_converter_notes_volume_and_wave():
    g = _gbs_module()
    a4 = 2048 - round(131072 / 440)            # pulse frequency register for 440 Hz
    writes = [(0, 0xFF26, 0x80), (0, 0xFF24, 0x77), (0, 0xFF25, 0xFF)]
    writes += _pulse_note(0.1, a4, vol=15, period=1)       # fades 1/64 s a step
    writes += [(0.2, 0xFF1A, 0x00)] + [(0.2, 0xFF30 + i, 0x01 * i * 17 & 0xFF) for i in range(16)]
    writes += [(0.2, 0xFF1A, 0x80), (0.2, 0xFF1C, 0x40), (0.2, 0xFF1D, a4 & 0xFF), (0.2, 0xFF1E, 0x80 | (a4 >> 8))]
    writes += [(0.6, 0xFF26, 0x00)]
    conv = g.Converter()
    conv.run(_iodump(writes))
    ons = [e for e in conv.events if e[3] == "on"]
    assert [(e[2], e[4]) for e in ons] == [(0, 69), (2, 57)]    # wave: 65536/(2048-x), an octave down
    vols = [e[5] for e in conv.events if e[3] == "cc" and e[2] == 0 and e[4] == 7]
    assert vols[0] == 127 and vols == sorted(vols, reverse=True)  # the envelope fades
    wave_level = [e[5] for e in conv.events if e[3] == "cc" and e[2] == 2 and e[4] == 7][0]
    assert wave_level == round(127 * math.sqrt(0.5))             # 50% level, squared by the game
    kinds = [i[0] for i in conv.instruments]
    assert kinds == ["pulse", "wave"] and conv.instruments[0][1] == 0.5
    bank = g.soundbank("Test", conv.instruments)
    assert cb.check_soundbank(bank) is None


def test_gbs_converter_finds_the_loop():
    g = _gbs_module()
    keys = [2048 - round(131072 / 440 / 2 ** (k / 12)) for k in (0, 3, 7, 5, 2)]
    writes = [(0, 0xFF26, 0x80), (0, 0xFF24, 0x77), (0, 0xFF25, 0xFF)]
    t = 0.05
    for f in [keys[0]] + keys[1:] * 3:      # an intro note, then a 4-note phrase three times
        writes += _pulse_note(t, f)
        t += 0.4
    conv = g.Converter()
    conv.run(_iodump(writes))
    start, length = g.find_loop(conv.events)
    assert abs(start - 0.45) < 0.01 and abs(length - 1.6) < 0.01
    midi = g.write_midi(conv.events, start, length)
    assert midi[:4] == b"MThd" and b"MTrk" in midi


def test_loop_start_marker():
    """A "loopStart" marker sets where a looping song loops back to (the port's own)."""
    from partyplanner64.lib.audio.midi import create_game_midi, parse_game_midi
    from partyplanner64.lib.audio.midiplayer import read_midi

    def song(marker):
        conductor = b"\x00\xff\x51\x03\x07\xa1\x20"
        conductor += (b"\x83\x00\xff\x06\x09loopStart\x83\x00" if marker else b"\x86\x00") + b"\xff\x2f\x00"
        notes = b"\x00\xc0\x02" + b"".join(b"\x00\x90" + bytes([k, 100]) + b"\x83\x00\x80" + bytes([k, 0])
                                           for k in (60, 64)) + b"\x00\xff\x2f\x00"
        return (b"MThd" + struct.pack(">IHHH", 6, 1, 2, 96)
                + b"MTrk" + struct.pack(">I", len(conductor)) + conductor
                + b"MTrk" + struct.pack(">I", len(notes)) + notes)

    def loop_ticks(midi):
        game = create_game_midi(midi, {"loop": True})
        _, tracks = read_midi(bytes(parse_game_midi(DataView(bytes(game)), len(game))))
        return [(e["tick"], e["number"]) for e in tracks[1]
                if e["type"] == "controller" and e["number"] in (102, 103)]

    assert loop_ticks(song(False)) == [(0, 102), (768, 103)]
    assert loop_ticks(song(True)) == [(384, 102), (768, 103)]


def test_gbs_converter_writes_the_intro_and_marks_the_loop():
    g = _gbs_module()
    keys = [2048 - round(131072 / 440 / 2 ** (k / 12)) for k in (0, 3, 7, 5, 2)]
    writes = [(0, 0xFF26, 0x80), (0, 0xFF24, 0x77), (0, 0xFF25, 0xFF)]
    t = 0.05
    for f in [keys[0]] + keys[1:] * 3:
        writes += _pulse_note(t, f)
        t += 0.4
    conv = g.Converter()
    conv.run(_iodump(writes))
    start, length = g.find_loop(conv.events)
    first = min(e[0] for e in conv.events if e[3] == "on")
    midi = g.write_midi(conv.events, start, length, intro=start - first)
    assert b"\xff\x06\x09loopStart" in midi
    from partyplanner64.lib.audio.midiplayer import read_midi
    _, tracks = read_midi(midi)
    ons = [e["note"] for e in tracks[1] if e["type"] == "note" and e["velocity"]]
    assert ons == [69, 72, 76, 74, 71]          # the intro note, then one pass of the loop
