"""MBF0 - Custom MIDI Bank Format (port of audio/MBF0.ts).

struct MBF0Header {
  u32 magic; "MBF0"
  u32 midi_count;
  u32 zeroes;
  u32 zeroes;
  u16 mystery;
  u16 mystery;
  u16 mystery; // sample rate?
  u16 mystery;
  u16 mystery;
  ... etc. total header size 0x40
  MBF0TableEntry[midi_count];
  u32 b1_offset;
  u32 b1_length;
  u32 tbl_offset;
  u32 tbl_length;
  // Followed by midi data
}

struct MBF0TableEntry {
  u8 mystery0; // boolean?
  u8 mystery1;
  u8 soundbank_index;
  u8 zero;
  u32 0x07000000
  u32 midi_offset; // from MBF0Header
  u32 midi_length;
}

Each entry of `midis` is a dict: {"buffer", "mystery0", "mystery1", "mystery4",
"soundbank_index"} (the mysteries optional).
"""

from ..debug import is_debug
from ..utils.dataview import DataView
from ..utils.debug import assert_
from ..utils.number import make_divisible_by
from .b1 import B1
from .s2 import _copy, _slice

MBF0_MAGIC = 0x4D424630
MBF0_HEADER_SIZE = 0x40


class MBF0:
    def __init__(self, data_view):
        self.midis = []
        self.tbl = None
        self.soundbanks = None
        self._soundback_buffer = None
        self._header_contents = None
        self._extract(data_view)

    def _extract(self, view):
        if view.get_uint32(0) != MBF0_MAGIC:  # "MBF0"
            raise ValueError("MBF0 constructor encountered non-MBF0 structure")

        midi_count = view.get_uint32(4)

        # Don't really know what these are, so just grab rest of header in bulk.
        self._header_contents = _slice(view, 8, 8 + 0x38)

        table_entries_offset = MBF0_HEADER_SIZE

        # The MBF0 may have multiple entries that refer to the same buffer.
        # If we've read a buffer already, we'll record so in this map.
        # We'll rely on referential equality during write back to recognize
        # equal entries, and avoid duplicating them.
        buffers_map = {}

        # Extract midi buffers
        for i in range(midi_count):
            table_entry_offset = table_entries_offset + i * 16
            midi_offset = view.get_uint32(table_entry_offset + 8)
            midi_size = view.get_uint32(table_entry_offset + 12)

            if midi_offset in buffers_map:
                buffer = buffers_map[midi_offset]
            else:
                buffer = _slice(view, midi_offset, midi_offset + midi_size)
                buffers_map[midi_offset] = buffer

            self.midis.append({
                "buffer": buffer,
                "mystery0": view.get_uint8(table_entry_offset),
                "mystery1": view.get_uint8(table_entry_offset + 1),
                "mystery4": view.get_uint32(table_entry_offset + 4),
                "soundbank_index": view.get_uint8(table_entry_offset + 2),
            })

            assert_(view.get_uint8(table_entry_offset + 3) == 0)
            assert_(view.get_uint32(table_entry_offset + 4) == 0x07000000
                    or view.get_uint32(table_entry_offset + 4) == 0)

        extra_offsets_offset = MBF0_HEADER_SIZE + 16 * midi_count
        b1offset = view.get_uint32(extra_offsets_offset)
        b1size = view.get_uint32(extra_offsets_offset + 4)
        tbl_offset_start = view.get_uint32(extra_offsets_offset + 8)
        tbl_offset_end = tbl_offset_start + view.get_uint32(extra_offsets_offset + 12)

        # Extract tbl buffer
        self.tbl = _slice(view, tbl_offset_start, tbl_offset_end)

        # Extract B1 structure
        b1view = DataView(view.buffer, view.byte_offset + b1offset, b1size)
        self.soundbanks = B1(b1view)

        # Workaround until B1 can measure itself.
        self._soundback_buffer = _slice(view, b1offset, b1offset + b1size)

    def pack(self, buffer, start_offset=0):
        data_view = DataView(buffer, start_offset)
        current_offset = 0

        data_view.set_uint32(0, MBF0_MAGIC)
        data_view.set_uint32(4, len(self.midis))
        _copy(data_view, self._header_contents, 8)
        current_offset += MBF0_HEADER_SIZE

        current_offset += 16 * len(self.midis)  # Skip over midi entry table.
        current_offset += 16  # Skip over B1 and tbl offsets.

        # Write the midis.
        buffers_map = {}  # id(buffer) -> offset
        for midi_info in self.midis:
            if id(midi_info["buffer"]) in buffers_map:
                continue  # Already written.

            assert_(current_offset % 8 == 0)
            buffers_map[id(midi_info["buffer"])] = current_offset

            _copy(data_view, midi_info["buffer"], current_offset)

            current_offset += make_divisible_by(len(midi_info["buffer"]), 8)

        current_offset = make_divisible_by(current_offset, 16)

        # Write the B1 soundbank.
        b1_offset = current_offset
        b1_length = len(self._soundback_buffer)
        _copy(data_view, self._soundback_buffer, current_offset)
        current_offset += make_divisible_by(b1_length, 8)

        # Write the tbl.
        tbl_offset = current_offset
        tbl_length = len(self.tbl)
        _copy(data_view, self.tbl, current_offset)
        current_offset += make_divisible_by(tbl_length, 8)

        final_offset = make_divisible_by(current_offset, 16)

        # Now go back and fill out upper table.
        current_offset = MBF0_HEADER_SIZE
        for midi_info in self.midis:
            data_view.set_uint8(current_offset, midi_info.get("mystery0") or 0)
            mystery1 = midi_info.get("mystery1")
            data_view.set_uint8(current_offset + 1, mystery1 if isinstance(mystery1, int) else 0x6F)
            data_view.set_uint8(current_offset + 2, midi_info["soundbank_index"])
            data_view.set_uint8(current_offset + 3, 0)
            mystery4 = midi_info.get("mystery4")
            data_view.set_uint32(current_offset + 4,
                                 mystery4 if isinstance(mystery4, int) else 0x07000000)
            data_view.set_uint32(current_offset + 8, buffers_map[id(midi_info["buffer"])])
            data_view.set_uint32(current_offset + 12, len(midi_info["buffer"]))

            current_offset += 16

        data_view.set_uint32(current_offset, b1_offset)
        data_view.set_uint32(current_offset + 4, b1_length)
        data_view.set_uint32(current_offset + 8, tbl_offset)
        data_view.set_uint32(current_offset + 12, tbl_length)

        byte_length_written = final_offset
        if is_debug():
            assert_(self.get_byte_length() == byte_length_written)
        return byte_length_written

    def get_byte_length(self):
        byte_length = 0

        byte_length += 4  # Magic
        byte_length += 4  # Midi count
        byte_length += len(self._header_contents)  # Rest of header
        assert_(byte_length == MBF0_HEADER_SIZE)

        byte_length += len(self.midis) * 16  # Midi info table (sizeof(struct MBF0TableEntry))

        byte_length += 16  # B1 and tbl offsets.

        assert_(byte_length % 16 == 0)  # Should be true at this point.

        seen_buffers = set()
        for midi_info in self.midis:
            if id(midi_info["buffer"]) in seen_buffers:
                continue  # Already counted.
            seen_buffers.add(id(midi_info["buffer"]))

            byte_length += make_divisible_by(len(midi_info["buffer"]), 8)

        byte_length = make_divisible_by(byte_length, 16)

        assert_(len(self._soundback_buffer) % 8 == 0)
        byte_length += len(self._soundback_buffer)

        assert_(len(self.tbl) % 8 == 0)
        byte_length += len(self.tbl)

        byte_length = make_divisible_by(byte_length, 16)
        return byte_length
