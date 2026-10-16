"""S2: an ALSeqFile (port of audio/S2.ts).

https://github.com/derselbst/N64SoundTools/blob/master/N64SoundListTool/N64SoundLibrary/N64AIFCAudio.cpp

Two-part midi table.
  First table: 8 byte entries, [midi offset, midi length]
  Second table: 16 byte entries, [SS7FFFFF (SS = soundbank index), B1 offset, B1 length, TBL offset]
B1
TBL
Midis

Each entry of `midis` is a dict: {"buffer": bytearray, "soundbank_index": int}.

Extended table notes

Mario Party

Midi Listing at 015396A0 (4 byte header S2)
Midi Lookup Soundbank # at 0153992C
SS7FFFFF 000007A0 00029D28 0002A4C8
SS = Soundbank #

(Note that I believe actually the soundbank association, though in table, may actually be hardcoded)
Midi Listing at 01778BC0 (4 byte header S2)
Midi Lookup Soundbank # at 01778BFC
SS7FFFFF 000007A0 00029D28 0002A4C8
SS = Soundbank #

Mario Party 2

01750490 Midi Lookup (ROM)
00SS0000 07000000 OOOOOOOO LLLLLLLL
SS = Soundbank #
OOOOOOOO=Location of Midi (offset from 01750450)
LLLLLLLL=Length of Midi

Mario Party 3

01881C80 Midi Lookup (ROM)
00??SS00 07000000 OOOOOOOO LLLLLLLL
?? = ?
SS = Soundbank #
OOOOOOOO=Location of Midi (offset from 01881C40)
LLLLLLLL=Length of Midi
"""

from ..debug import is_debug
from ..utils.dataview import DataView
from ..utils.debug import assert_
from ..utils.number import make_divisible_by
from .b1 import B1

S2_MAGIC = 0x5332


def _slice(view, start, end):
    return bytearray(view.buffer[view.byte_offset + start:view.byte_offset + end])


class S2:
    def __init__(self, data_view):
        self.midis = []
        self.tbl = None
        self.soundbanks = None
        self._raw_b1 = None
        self._extract(data_view)

    def _extract(self, view):
        if view.get_uint16(0) != S2_MAGIC:  # "S2"
            raise ValueError("S2 constructor encountered non-S2 structure")

        midi_count = view.get_uint16(2)
        extended_s2_table_offset = 4 + midi_count * 8

        # Extract midi buffers
        for i in range(midi_count):
            midi_offset = view.get_uint32(4 + i * 4 * 2)
            midi_size = view.get_uint32(8 + i * 4 * 2)
            self.midis.append({
                "buffer": _slice(view, midi_offset, midi_offset + midi_size),
                "soundbank_index": view.get_uint8(extended_s2_table_offset + i * 16),
            })

        # Extract tbl buffer
        # Assumption: we know where it begins, and will assume it ends at the first midi offset.
        tbl_offset_start = view.get_uint32(extended_s2_table_offset + 12)
        tbl_offset_end = view.get_uint32(4)  # First midi offset
        self.tbl = _slice(view, tbl_offset_start, tbl_offset_end)

        # Extract B1 structure
        # Assumption: extra S2 table entries all point to same B1
        b1offset_start = view.get_uint32(extended_s2_table_offset + 4)
        b1length = view.get_uint32(extended_s2_table_offset + 8)
        b1view = DataView(view.buffer, view.byte_offset + b1offset_start)
        self.soundbanks = B1(b1view)
        self._raw_b1 = _slice(view, b1offset_start, b1offset_start + b1length)

    def pack(self, buffer, start_offset=0):
        data_view = DataView(buffer, start_offset)
        current_offset = 0

        data_view.set_uint16(0, S2_MAGIC)
        data_view.set_uint16(2, len(self.midis))
        current_offset += 4

        # First table
        first_table_len = len(self.midis) * 8
        second_table_len = len(self.midis) * 16 + 4
        b1_offset = make_divisible_by(4 + first_table_len + second_table_len, 16)
        midis_offset = b1_offset + len(self._raw_b1) + len(self.tbl)
        midis_offset = make_divisible_by(midis_offset, 8)
        for midi_info in self.midis:
            data_view.set_uint32(current_offset, midis_offset)
            midi_size = make_divisible_by(len(midi_info["buffer"]), 8)
            data_view.set_uint32(current_offset + 4, midi_size)

            current_offset += 8
            midis_offset += midi_size

        # Second table
        for midi_info in self.midis:
            data_view.set_int8(current_offset, midi_info["soundbank_index"])
            data_view.set_int8(current_offset + 1, 0x7F)
            data_view.set_uint8(current_offset + 2, 0xFF)
            data_view.set_uint8(current_offset + 3, 0xFF)

            data_view.set_uint32(current_offset + 4, b1_offset)
            data_view.set_uint32(current_offset + 8, len(self._raw_b1))
            data_view.set_uint32(current_offset + 12, b1_offset + len(self._raw_b1))  # TBL offset

            current_offset += 16
        data_view.set_uint32(current_offset, 0xFFFFFFFF)
        current_offset += 4
        current_offset = make_divisible_by(current_offset, 16)

        # B1
        _copy(data_view, self._raw_b1, current_offset)
        current_offset += make_divisible_by(len(self._raw_b1), 8)

        # TBL
        _copy(data_view, self.tbl, current_offset)
        current_offset += make_divisible_by(len(self.tbl), 8)

        # Midis
        for midi_info in self.midis:
            _copy(data_view, midi_info["buffer"], current_offset)
            current_offset += make_divisible_by(len(midi_info["buffer"]), 8)

        current_offset = make_divisible_by(current_offset, 16)

        if is_debug():
            assert_(self.get_byte_length() == current_offset)
        return current_offset

    def get_byte_length(self):
        byte_length = 0

        byte_length += 2  # Magic
        byte_length += 2  # Midi count
        byte_length += len(self.midis) * 8  # First table
        byte_length += len(self.midis) * 16 + 4  # Second table
        byte_length = make_divisible_by(byte_length, 16)

        byte_length += make_divisible_by(len(self._raw_b1), 8)  # B1
        byte_length += make_divisible_by(len(self.tbl), 8)  # TBL

        # Midis
        for midi_info in self.midis:
            byte_length += make_divisible_by(len(midi_info["buffer"]), 8)

        byte_length = make_divisible_by(byte_length, 16)

        return byte_length


def _copy(data_view, src, out_offset):
    """copyRange(dataView, src, outOffset, 0, src.byteLength)."""
    start = data_view.byte_offset + out_offset
    if out_offset < 0 or out_offset + len(src) > data_view.byte_length:
        raise IndexError("Offset is outside the bounds of the DataView")
    data_view.buffer[start:start + len(src)] = src
