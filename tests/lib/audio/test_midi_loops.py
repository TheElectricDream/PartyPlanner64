"""Counted loops in game MIDIs end (the TypeScript jumped back forever)."""

import struct

from partyplanner64.lib.audio.midi import parse_game_midi
from partyplanner64.lib.utils.dataview import DataView


def _game_midi(count):
    trk = bytearray()
    trk += b"\x00\xFF\x2E\x00\xFF"          # start loop 0
    trk += b"\x00\x90\x3C\x64\x10"          # note on, with its duration
    trk += b"\x10\xFF\x51\x07\xA1\x20"      # tempo
    trk += b"\x00\xFF\x2D" + bytes([count, 0])
    trk += struct.pack(">I", len(trk) + 4 - 5)   # back to just after the loop start
    trk += b"\x00\xFF\x2F\x00"              # end of track
    hdr = bytearray(0x44)
    struct.pack_into(">I", hdr, 0, 0x44)    # the one track
    struct.pack_into(">I", hdr, 0x40, 0x30)  # division
    return hdr + trk


def test_counted_loop_repeats_then_ends():
    for count in (1, 2, 5):
        data = _game_midi(count)
        out = bytes(parse_game_midi(DataView(bytearray(data)), len(data)))
        assert out[:4] == b"MThd"
        assert out.count(b"\x90\x3c\x64") == count + 1
