"""SBF0 - Custom Sound Effects Format (port of audio/SBF0.ts).

struct SBF0Header {
  u32 magic; "SBF0"
  u32 soundfx_count;
  u32 zeroes;
  u32 zeroes;
  u16 mystery;
  u16 mystery;
  u16 mystery; // sample rate?
  u16 mystery;
  u16 mystery;
  ... more fields
  0x44: u32 raw_count;
  0x54: u32 tbl_offset;
  0x58: u32 tbl_length;
  ... more fields
  0x70: u32 ?;
  SBF0RawTableEntry[raw_count];
  TBL
  SBF0SfxTableEntryOffsets[soundfx_count]; (0x1EEA64C in MP3)
  SBF0SfxTableEntry entries follow
}

struct SBF0RawTableEntry {
  u32 env_offset;
  u32 sample_rate;
  u32 wave_offset
  u8 sample_pan;
  u8 sample_volume;
  u8 flags;
  u8 _zero;
}

struct SBF0SfxTableEntry {
  u8 num_infos;
  u8 unknown;
  u16 zeroes?;
  u32 zeroes?;
  SBF0SfxTableEntryInner[num_infos];
}

struct SBF0SfxTableEntryInner {
  u16 unknown;
  u16 unknown;
  u32 info_offset;
}
"""

from ..debug import is_debug
from ..utils.dataview import DataView
from ..utils.debug import hexstr, log
from .al_sound_simple import ALSoundSimple
from .s2 import _slice


class SBF0:
    def __init__(self, data_view):
        self.tbl = None
        self.sounds = []
        if data_view.get_uint32(0) != 0x53424630:  # "SBF0"
            raise ValueError("SBF0 constructor encountered non-SBF0 structure")
        self._extract(data_view)

    def _extract(self, view):
        sound_count = view.get_uint32(0x44)
        table_entries_offset = 0x74

        if sound_count == 0:
            raise ValueError("Does soundCount === 0?")

        # Extract sounds
        ctl_view = DataView(view.buffer, view.byte_offset + table_entries_offset)
        for i in range(sound_count):
            self.sounds.append(ALSoundSimple(ctl_view, i * 16))

        tbl_offset_start = view.get_uint32(0x54)
        tbl_offset_end = tbl_offset_start + view.get_uint32(0x58)

        # Extract tbl buffer
        self.tbl = _slice(view, tbl_offset_start, tbl_offset_end)

        # Extract the sound effects list.
        # This list count is higher than the actual raw sound count,
        # presumably because some entries use the same raw data.
        if is_debug():
            details = ""  # This is just a temporary info extraction thing...
            sound_fx_count = view.get_uint32(4)
            sound_fx_list_offset = tbl_offset_end
            for i in range(sound_fx_count):
                offset = view.get_uint32(sound_fx_list_offset + i * 4)

                subcount = view.get_uint8(sound_fx_list_offset + offset)
                substructstart = sound_fx_list_offset + offset + 8
                for s in range(subcount):
                    sound_fx_info_offset = view.get_uint32(substructstart + s * 8 + 4)

                    sound_fx_info_type = view.get_uint8(sound_fx_list_offset + sound_fx_info_offset)
                    if sound_fx_info_type in (0x92, 0x93):
                        raw_sound_index = view.get_uint16(sound_fx_list_offset + sound_fx_info_offset + 1)
                    elif sound_fx_info_type in (0x12, 0x13):
                        raw_sound_index = view.get_uint16(sound_fx_list_offset + sound_fx_info_offset + 2)
                    elif sound_fx_info_type in (0x01, 0xA0):
                        continue
                    else:
                        raise ValueError(
                            "Unrecongized soundFxInfoType " + hexstr(sound_fx_info_type) + " at "
                            + hexstr(view.byte_offset + sound_fx_list_offset + sound_fx_info_offset))
                    details += "\n%s: %s" % (hexstr(i), hexstr(raw_sound_index))
            log(details)
