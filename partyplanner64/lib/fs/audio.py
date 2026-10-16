"""The audio section of the ROM (port of fs/audio.ts)."""

from ..debug import is_debug
from ..types import Game
from ..utils.arrays import copy_range
from ..utils.dataview import DataView
from ..utils.debug import assert_, hexstr, log
from ..utils.number import make_divisible_by

# Each subsection (IOffsetObj): {"type": "S2" | "T3" | "MBF0" | "SBF0" |
# "FXD0" | "Pointer", "byte_length" (optional), "offsets": [{"upper",
# "lower", "ovl" (optional)}]}.
_audio_offsets = {
    Game.MP1_USA: [
        # Length 0x7B3DF0
        # 15396A0
        {
            "type": "S2",
            # byte_length: 0x23F520,
            "offsets": [
                {"upper": 0x00061746, "lower": 0x0006174A},
                {"ovl": 0x6E, "upper": 0xE62, "lower": 0xE66},  # ROM: 0x2DA3D2
            ],
        },

        # 1778BC0
        {
            "type": "S2",
            # byte_length: 0xB9F20,
            "offsets": [
                {"upper": 0x0001AF2A, "lower": 0x0001AF2E},
                {"upper": 0x0006174E, "lower": 0x00061752},
                {"upper": 0x0006177E, "lower": 0x00061782},
                {"ovl": 0x6E, "upper": 0xE6A, "lower": 0xE6E},  # ROM: 0x2DA3DA
                {"ovl": 0x6E, "upper": 0xE92, "lower": 0xE96},  # ROM: 0x2DA402
            ],
        },

        # 1832AE0
        {
            "type": "T3",
            "byte_length": 0x385980,
            "offsets": [
                {"upper": 0x0001AF32, "lower": 0x0001AF36},
                {"upper": 0x0006172E, "lower": 0x00061732},
                {"upper": 0x00061786, "lower": 0x0006178A},
                {"ovl": 0x6E, "upper": 0xE4E, "lower": 0xE52},  # ROM: 0x2DA3BE
                {"ovl": 0x6E, "upper": 0xE9A, "lower": 0xE9E},  # ROM: 0x2DA40A
            ],
        },

        # 1BB8460
        {
            "type": "T3",
            "byte_length": 0x134800,
            "offsets": [
                {"upper": 0x0001AF0E, "lower": 0x0001AF12},
                {"upper": 0x00061762, "lower": 0x00061766},
                {"ovl": 0x6E, "upper": 0xE7A, "lower": 0xE7E},  # ROM: 0x2DA3EA
            ],
        },

        # 1CECC60
        {
            "type": "FXD0",
            "byte_length": 0x830,
            "offsets": [{"upper": 0x0001AF5A, "lower": 0x0001AF5E}],
        },

        # 1CED490, 0xffffffffs EOF
        {
            "type": "Pointer",
            "byte_length": 0,
            "offsets": [{"upper": 0x0001AF66, "lower": 0x0001AF6A}],
        },
    ],

    Game.MP1_JPN: [
        # Length ?
    ],
    Game.MP1_PAL: [
        # Length ?
    ],

    Game.MP2_USA: [
        # Length 0x6DAB50
        # 0x1750450
        {
            "type": "MBF0",
            # byte_length: 0x1B9C40,
            "offsets": [
                {"upper": 0x0001D342, "lower": 0x0001D346},
                {"upper": 0x0007A9EE, "lower": 0x0007A9F2},
                {"upper": 0x0007AA12, "lower": 0x0007AA16},
            ],
        },
        # 0x190A090
        {
            "type": "SBF0",
            "byte_length": 0x3B5380,
            "offsets": [{"upper": 0x0007A9FA, "lower": 0x0007A9FE}],
        },
        # 0x1CBF410
        {
            "type": "SBF0",
            "byte_length": 0x16B150,
            "offsets": [
                {"upper": 0x0001D34E, "lower": 0x0001D352},
                {"upper": 0x0007AA1E, "lower": 0x0007AA22},
            ],
        },
        # 0x1E2A560
        {
            "type": "FXD0",
            "byte_length": 0xA40,
            "offsets": [{"upper": 0x0001D382, "lower": 0x0001D386}],
        },
    ],

    Game.MP2_JPN: [
        # Length ?
    ],
    Game.MP2_PAL: [
        # Length ?
    ],

    Game.MP3_USA: [
        # Length 0x67be40
        # 0x1881C40
        {
            "type": "MBF0",
            # byte_length: 0x1D4C30,
            "offsets": [
                {"upper": 0x0000F26A, "lower": 0x0000F26E},
                {"upper": 0x0004BEF2, "lower": 0x0004BEF6},
            ],
        },
        # 0x1A56870
        {
            "type": "SBF0",
            "byte_length": 0x4A67D0,
            "offsets": [
                {"upper": 0x0000F276, "lower": 0x0000F27A},
                {"upper": 0x0004BEFE, "lower": 0x0004BF02},
            ],
        },
        # 0x1EFD040
        {
            "type": "FXD0",
            "byte_length": 0xA40,
            "offsets": [{"upper": 0x0000F29E, "lower": 0x0000F2A2}],
        },
        # E0F 0x1EFDA80
    ],

    Game.MP3_JPN: [
        # Length ?
    ],
    Game.MP3_PAL: [
        # Length ?
    ],
}


def _read_patch(scenes, rom, patch_info):
    if isinstance(patch_info.get("ovl"), int):
        scene_view = scenes.get_data_view(patch_info["ovl"])
        return scene_view.get_uint16(patch_info["upper"]), scene_view.get_uint16(patch_info["lower"])
    rom_view = rom.get_data_view()
    return rom_view.get_uint16(patch_info["upper"]), rom_view.get_uint16(patch_info["lower"])


class Audio:
    def __init__(self, rom):
        self._rom = rom
        self._buffer_cache = None
        self._parsed_cache = None

    def get_rom_offset(self, subsection=0):
        from ..utils.mips import get_reg_set_address
        scenes = self._rom.get_scenes()
        if not scenes:
            return None
        infos = self.get_patch_info()
        if not infos:
            return None
        if subsection >= len(infos):
            return None
        patch_info = infos[subsection]
        rom_patch_info = patch_info["offsets"][0]
        upper, lower = _read_patch(scenes, self._rom, rom_patch_info)

        offset = get_reg_set_address(upper, lower)
        log("Audio.getROMOffset -> %s" % hexstr(offset))

        if is_debug():
            # Assert that the rest of the patch offsets are valid.
            for o_index, offset_info in enumerate(patch_info["offsets"]):
                another_upper, another_lower = _read_patch(scenes, self._rom, offset_info)
                another_offset = get_reg_set_address(another_upper, another_lower)
                if another_offset != offset:
                    raise RuntimeError(
                        "AudioFS.getROMOffset patch offset %s/%s seems wrong:\n"
                        "          offset: %s vs %s\n"
                        "          reading upper: %s, lower: %s" % (
                            subsection, o_index, hexstr(offset), hexstr(another_offset),
                            hexstr(offset_info["upper"]), hexstr(offset_info["lower"])))

        return offset

    def set_rom_offset(self, new_offset, out_buffer):
        from ..utils.mips import get_reg_set_upper_and_lower
        log("Audio.setROMOffset(%s)" % hexstr(new_offset))
        rom = self._rom
        scenes = rom.get_scenes()
        infos = self.get_patch_info()
        current_offset = new_offset
        for i, info in enumerate(infos):
            upper, lower = get_reg_set_upper_and_lower(current_offset)
            for patch_offset in info["offsets"]:
                if isinstance(patch_offset.get("ovl"), int):
                    scene_view = scenes.get_data_view(patch_offset["ovl"])
                    scene_view.set_uint16(patch_offset["upper"], upper)
                    scene_view.set_uint16(patch_offset["lower"], lower)
                else:
                    rom_view = DataView(out_buffer)
                    rom_view.set_uint16(patch_offset["upper"], upper)
                    rom_view.set_uint16(patch_offset["lower"], lower)

            type = info["type"]
            if type in ("T3", "SBF0", "FXD0"):
                assert_(isinstance(info.get("byte_length"), int))
                assert_(info["byte_length"] % 16 == 0)
                current_offset += info["byte_length"]
            elif type == "S2":
                assert_(bool(self._parsed_cache[i]))
                current_offset += self._parsed_cache[i].get_byte_length()
            elif type == "MBF0":
                assert_(bool(self._parsed_cache[i]))
                current_offset += self._parsed_cache[i].get_byte_length()
            elif type == "Pointer":
                pass
            else:
                raise ValueError("Unhandled audio subsection type: " + type)

    def get_patch_info(self):
        return _audio_offsets.get(self._rom.get_game())

    def read(self, index):
        raise NotImplementedError("audio.read not implemented")

    def write(self, index, value):
        raise NotImplementedError("audio.write not implemented")

    def get_sequence_table_count(self):
        return sum(1 for entry in self._parsed_cache if entry is not None and hasattr(entry, "midis"))

    def get_sequence_table(self, index):
        """Return the index-th sequence table (S2 or MBF0), or None."""
        if self._parsed_cache is None:
            return None
        cur_index = -1
        for entry in self._parsed_cache:
            if entry is not None and hasattr(entry, "midis"):
                cur_index += 1
                if cur_index == index:
                    return entry
        return None

    def get_sound_table_count(self):
        return sum(1 for entry in self._parsed_cache if entry is not None and hasattr(entry, "sounds"))

    def get_sound_table(self, index):
        """Return the index-th sound table (T3 or SBF0), or None."""
        if self._parsed_cache is None:
            return None
        cur_index = -1
        for entry in self._parsed_cache:
            if entry is not None and hasattr(entry, "sounds"):
                cur_index += 1
                if cur_index == index:
                    return entry
        return None

    def extract(self):
        from ..audio.fxd0 import FXD0
        from ..audio.mbf0 import MBF0
        from ..audio.s2 import S2
        from ..audio.sbf0 import SBF0
        from ..audio.t3 import T3

        buffer = self._rom.get_buffer()
        offset = self.get_rom_offset()
        if offset is None:
            return

        infos = self.get_patch_info()
        self._buffer_cache = [None] * len(infos)
        self._parsed_cache = [None] * len(infos)
        for i, info in enumerate(infos):
            type = info["type"]
            if type == "S2":
                s2_offset = self.get_rom_offset(i)
                s2 = self._parsed_cache[i] = S2(self._rom.get_data_view(s2_offset))
                self._buffer_cache[i] = bytearray(buffer[s2_offset:s2_offset + s2.get_byte_length()])
            elif type == "T3":
                assert_(isinstance(info.get("byte_length"), int))
                t3_offset = self.get_rom_offset(i)
                self._buffer_cache[i] = bytearray(buffer[t3_offset:t3_offset + info["byte_length"]])
                self._parsed_cache[i] = T3(self._rom.get_data_view(t3_offset))
            elif type == "MBF0":
                mbf0_offset = self.get_rom_offset(i)
                mbf0 = self._parsed_cache[i] = MBF0(self._rom.get_data_view(mbf0_offset))
                self._buffer_cache[i] = bytearray(buffer[mbf0_offset:mbf0_offset + mbf0.get_byte_length()])
            elif type == "SBF0":
                assert_(isinstance(info.get("byte_length"), int))
                sbf0_offset = self.get_rom_offset(i)
                self._buffer_cache[i] = bytearray(buffer[sbf0_offset:sbf0_offset + info["byte_length"]])
                self._parsed_cache[i] = SBF0(self._rom.get_data_view(sbf0_offset))
            elif type == "FXD0":
                assert_(isinstance(info.get("byte_length"), int))
                fxd0_offset = self.get_rom_offset(i)
                self._buffer_cache[i] = bytearray(buffer[fxd0_offset:fxd0_offset + info["byte_length"]])
                self._parsed_cache[i] = FXD0(self._rom.get_data_view(fxd0_offset))
            elif type == "Pointer":
                self._buffer_cache[i] = self._parsed_cache[i] = None
            else:
                raise ValueError("Unhandled audio subsection type: " + type)

    extract_async = extract

    def pack(self, buffer, offset=0):
        infos = self.get_patch_info()
        if not infos or self._buffer_cache is None:
            raise RuntimeError("Unable to write audio section.")

        current_offset = offset
        for i, info in enumerate(infos):
            type = info["type"]
            if type in ("T3", "SBF0", "FXD0"):
                assert_(isinstance(info.get("byte_length"), int))
                copy_range(buffer, self._buffer_cache[i], current_offset, 0, len(self._buffer_cache[i]))
                current_offset += info["byte_length"]
            elif type in ("S2", "MBF0"):
                current_offset += self._parsed_cache[i].pack(buffer, current_offset)
                current_offset = make_divisible_by(current_offset, 16)
            elif type == "Pointer":
                pass
            else:
                raise ValueError("Unhandled audio subsection type: " + type)

        byte_length_written = current_offset - offset
        assert_(byte_length_written % 16 == 0)
        return byte_length_written

    # Gets the full byte length of the audio section of the ROM.
    def get_byte_length(self):
        infos = self.get_patch_info()
        if not infos:
            raise RuntimeError("Unable to determine audio section length.")

        byte_length = 0
        for i, info in enumerate(infos):
            type = info["type"]
            if type in ("T3", "SBF0", "FXD0"):
                assert_(isinstance(info.get("byte_length"), int))
                byte_length += info["byte_length"]
            elif type in ("S2", "MBF0"):
                byte_length += self._parsed_cache[i].get_byte_length()
            elif type == "Pointer":
                pass
            else:
                raise ValueError("Unhandled audio subsection type: " + type)

        return byte_length
