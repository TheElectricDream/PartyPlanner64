"""T3 - Custom Sound Effects Format (port of audio/T3.ts).

struct T3Header {
  u16 magic; "T3"
  u16 soundfx_count;
  T3SfxTableEntry[soundfx_count];
  u32 zeroes;
  u32 raw_count;
  u32 unknown;
  u32 tbl_offset; // Relative to T3RawTableEntry[] below
  u32 unknown;
  u32 tbl_length;
  u32 unknown;
  u32 * 4 unknown
  T3RawTableEntry[raw_count];
  TBL
}

struct T3SfxTableEntry {
  u4 unknown;
  u12 unknown; // Seems like this could almost be sound index too at times.
  s16 unknown;
  u4 unknown;
  u12 raw_sound_index;
  u16 sample_rate;
}

struct T3RawTableEntry {
  u32 env_offset;
  u32 zeroes;
  u32 wave_offset
  u8 sample_pan;
  u8 sample_volume;
  u8 flags;
  u8 _zero;
}
"""

from ..utils.dataview import DataView
from ..utils.debug import log
from .al_sound_simple import ALSoundSimple
from .s2 import _slice


class T3:
    def __init__(self, data_view):
        self.tbl = None
        self.sounds = []
        if data_view.get_uint16(0) != 0x5433:  # "T3"
            raise ValueError("T3 constructor encountered non-T3 structure")
        self._extract(data_view)

    def _extract(self, view):
        sound_fx_count = view.get_uint16(2)

        # Get metadata about each sound effect. Right now, we just need the sample rate really.
        sound_effect_metadata = []
        for i in range(sound_fx_count):
            sound_effect_metadata.append({
                "raw_sound": view.get_uint16(4 + i * 8 + 4) & 0x0FFF,
                # "raw_sound": view.get_uint16(4 + (i * 8)) & 0x0FFF,
                "sample_rate": view.get_uint16(4 + i * 8 + 6),
            })

        # Extract raw sounds
        raw_sound_count = view.get_uint32(4 + sound_fx_count * 8 + 4)
        table_entries_offset = 4 + sound_fx_count * 8 + 0x2C
        ctl_view = DataView(view.buffer, view.byte_offset + table_entries_offset)
        for i in range(raw_sound_count):
            sound = ALSoundSimple(ctl_view, i * 16)

            for sfxmetadata in sound_effect_metadata:
                if sfxmetadata["raw_sound"] == i:
                    sound.sample_rate = sfxmetadata["sample_rate"]
                    break
            if not sound.sample_rate:
                log("Unknown sample rate for raw sound %d, guessing..." % i)
                sound.sample_rate = 0x5622

            self.sounds.append(sound)

        tbl_offset_start = view.get_uint32(4 + sound_fx_count * 8 + 0xC)
        tbl_offset_end = tbl_offset_start + view.get_uint32(4 + sound_fx_count * 8 + 0x14)

        # Extract tbl buffer
        self.tbl = _slice(view, tbl_offset_start, tbl_offset_end)
