"""Synthetic soundbanks and MIDI files for the player tests (and the speed measurement)."""

import random
import time
from types import SimpleNamespace as NS

from partyplanner64.lib.audio.midiplayer import render_midi

def make_bank(n_inst=6, seconds=1.0, rate=22050, seed=1):
    rnd = random.Random(seed)
    tbl = bytearray()
    insts = []
    for i in range(n_inst):
        sounds = []
        for s in range(2):
            frames = int(seconds * rate / 16)
            base = len(tbl)
            for f in range(frames):
                tbl.append(((3 + (f % 5)) << 4) | 0)  # scale index, predictor 0
                tbl.extend(rnd.randrange(256) for _ in range(8))
            book = NS(order=2, npredictors=1, predictors=[rnd.randrange(-2048, 2048) for _ in range(16)])
            wave = NS(wave_base=base, wave_len=frames * 9, type=0, flags=0,
                      adpcm_wave=NS(loop=None, book=book), raw_wave=None)
            keymap = NS(key_min=s * 64, key_max=s * 64 + 63, key_base=48 + s * 24, detune=0)
            sounds.append(NS(wave=wave, keymap=keymap, sample_volume=100))
        insts.append(NS(volume=110, sounds=sounds))
    return NS(sample_rate=rate, instruments=insts), tbl

def vl(v):
    out = [v & 0x7f]
    v >>= 7
    while v:
        out.insert(0, (v & 0x7f) | 0x80); v >>= 7
    return bytes(out)

def make_midi(seconds=180, tracks=4, seed=2):
    rnd = random.Random(seed)
    div = 96
    chunks = []
    for t in range(tracks):
        ev = bytearray()
        ev += vl(0) + bytes([0xff, 0x51, 3, 0x07, 0xa1, 0x20])
        ev += vl(0) + bytes([0xc0 | t, t])
        ev += vl(0) + bytes([0xb0 | t, 7, 100])
        ticks = seconds * 2 * div
        tick = 0
        while tick < ticks:
            note = rnd.randrange(36, 90)
            dur = rnd.choice([24, 48, 96])
            ev += vl(0) + bytes([0x90 | t, note, rnd.randrange(60, 127)])
            ev += vl(dur) + bytes([0x90 | t, note, 0])
            tick += dur
        ev += vl(0) + bytes([0xff, 0x2f, 0])
        chunks.append(b"MTrk" + len(ev).to_bytes(4, "big") + ev)
    return b"MThd" + (6).to_bytes(4, "big") + (1).to_bytes(2, "big") + tracks.to_bytes(2, "big") + div.to_bytes(2, "big") + b"".join(chunks)

def measure(seconds=180, tracks=4):
    bank, tbl = make_bank()
    midi = make_midi(seconds, tracks)
    t = time.time()
    wav = render_midi(midi, bank, tbl, 22050)
    return time.time() - t, wav


if __name__ == "__main__":
    elapsed, wav = measure()
    print("render %.2fs, wav %d bytes = %.1f s audio" % (elapsed, len(wav), (len(wav) - 44) / 2 / 22050))
