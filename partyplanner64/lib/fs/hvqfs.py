"""The HVQ file system: board backgrounds (port of fs/hvqfs.ts).

The background metadata (IHVQMetadata) is a dict with the TypeScript's
camelCase keys (tileWidth, tileHeight, tileCountX, tileCountY, fov,
scaleFactor, cameraEyePosX/Y/Z, lookatPointX/Y/Z, cameraUpVecX/Y/Z),
because it is what boards store in `board["bg"]`.
"""

import time

from ..debug import is_debug
from ..types import Game
from ..utils.arrays import copy_range
from ..utils.canvas import ImageData, image_data_to_data_url
from ..utils.dataview import DataView
from ..utils.debug import hexstr, log
from ..utils.img.hvq import decode, encode
from ..utils.img.rgba5551 import rgba5551to_rgba32, rgba5551from_rgba32
from ..utils.img.tiler import from_tiles, to_tiles
from ..utils.number import make_divisible_by

_hvqfs_offsets = {}

_hvqfs_offsets[Game.MP1_USA] = [
    # Default at 0x00FE2310
    {"upper": 0x00057626, "lower": 0x0005762a},
    {"upper": 0x0005d012, "lower": 0x0005d016},
    {"ovl": 0x01, "upper": 0x236, "lower": 0x23e}, # ROM: 0xD5416
    {"ovl": 0x3f, "upper": 0xad6, "lower": 0xade}, # ROM: 0x259D76
    {"ovl": 0x40, "upper": 0x59fe, "lower": 0x5a06}, # ROM: 0x25F8AE
    {"ovl": 0x41, "upper": 0x722, "lower": 0x72a}, # ROM: 0x260392
    {"ovl": 0x42, "upper": 0x389a, "lower": 0x38a2}, # ROM: 0x27C76A
    {"ovl": 0x43, "upper": 0x3e62, "lower": 0x3e6a}, # ROM: 0x280992
    {"ovl": 0x44, "upper": 0xe16, "lower": 0xe1e}, # ROM: 0x281A96
    {"ovl": 0x45, "upper": 0x88a, "lower": 0x892}, # ROM: 0x2825CA
    {"ovl": 0x46, "upper": 0x2896, "lower": 0x289e}, # ROM: 0x2850B6
    {"ovl": 0x47, "upper": 0x8b6, "lower": 0x8be}, # ROM: 0x285AE6
    {"ovl": 0x48, "upper": 0xa9a, "lower": 0xaa2}, # ROM: 0x28660A
    {"ovl": 0x49, "upper": 0xaaa, "lower": 0xab2}, # ROM: 0x2871AA
    {"ovl": 0x4a, "upper": 0x14a2, "lower": 0x14aa}, # ROM: 0x288742
    {"ovl": 0x4b, "upper": 0x118e, "lower": 0x1196}, # ROM: 0x289A2E
    {"ovl": 0x4c, "upper": 0xebe, "lower": 0xec6}, # ROM: 0x28AA5E
    {"ovl": 0x4d, "upper": 0xff2, "lower": 0xffa}, # ROM: 0x28BB92
    {"ovl": 0x4e, "upper": 0x1206, "lower": 0x120e}, # ROM: 0x28CE76
    {"ovl": 0x4f, "upper": 0xeee, "lower": 0xef6}, # ROM: 0x28DEDE
    {"ovl": 0x50, "upper": 0x4f6, "lower": 0x4fe}, # ROM: 0x28E526
    {"ovl": 0x51, "upper": 0x5d2, "lower": 0x5da}, # ROM: 0x28EC02
    {"ovl": 0x52, "upper": 0x1a46, "lower": 0x1a4e}, # ROM: 0x2906E6
    {"ovl": 0x53, "upper": 0x942, "lower": 0x94a}, # ROM: 0x291232
    {"ovl": 0x54, "upper": 0xb62, "lower": 0xb6a}, # ROM: 0x291EC2
    {"ovl": 0x55, "upper": 0x10fe, "lower": 0x1106}, # ROM: 0x29311E
    {"ovl": 0x56, "upper": 0x78a, "lower": 0x792}, # ROM: 0x2939EA
    {"ovl": 0x57, "upper": 0x1896, "lower": 0x189e}, # ROM: 0x295306
    {"ovl": 0x59, "upper": 0x8aa, "lower": 0x8b2}, # ROM: 0x295CFA
    {"ovl": 0x5a, "upper": 0xbbe, "lower": 0xbc6}, # ROM: 0x2969FE
    {"ovl": 0x5b, "upper": 0xf62, "lower": 0xf6a}, # ROM: 0x297AD2
    {"ovl": 0x5c, "upper": 0x362, "lower": 0x36a}, # ROM: 0x297F42
    {"ovl": 0x5d, "upper": 0xa32, "lower": 0xa3a}, # ROM: 0x2989E2
    {"ovl": 0x5e, "upper": 0x179a, "lower": 0x17a2}, # ROM: 0x29A27A
    {"ovl": 0x5f, "upper": 0x622, "lower": 0x62a}, # ROM: 0x29AA22
    {"ovl": 0x60, "upper": 0x62e, "lower": 0x636}, # ROM: 0x29B15E
    {"ovl": 0x61, "upper": 0x54fa, "lower": 0x5502}, # ROM: 0x2A090A
    {"ovl": 0x62, "upper": 0x2ca2, "lower": 0x2caa}, # ROM: 0x2A51A2
    {"ovl": 0x64, "upper": 0x5a66, "lower": 0x5a6e}, # ROM: 0x2B70D6
    {"ovl": 0x65, "upper": 0x2cce, "lower": 0x2cd6}, # ROM: 0x2BA16E
    {"ovl": 0x77, "upper": 0x29ea, "lower": 0x29f2}, # ROM: 0x2FD79A
    {"ovl": 0x78, "upper": 0x2976, "lower": 0x297e}, # ROM: 0x3002B6
    {"ovl": 0x79, "upper": 0xdfe, "lower": 0xe06}, # ROM: 0x3013AE
    {"ovl": 0x7b, "upper": 0x24b2, "lower": 0x24b6}, # ROM: 0x306322
    {"ovl": 0x7c, "upper": 0x153e, "lower": 0x1546}, # ROM: 0x309F8E
    {"ovl": 0x7d, "upper": 0x12ea, "lower": 0x12f2}, # ROM: 0x30D82A
    {"ovl": 0x80, "upper": 0x1e9a, "lower": 0x1ea2}, # ROM: 0x3146EA
    {"ovl": 0x82, "upper": 0x1322, "lower": 0x132a}, # ROM: 0x317762
]
_hvqfs_offsets[Game.MP1_JPN] = [
    {"upper": 0x00057496, "lower": 2}, # "TODO": Needs conversion
    {"upper": 0x0005cbd2, "lower": 2},
    {"upper": 0x000d48c6, "lower": 6},
    {"upper": 0x002592a6, "lower": 6},
    {"upper": 0x0025ede6, "lower": 6},
    {"upper": 0x0025f8d2, "lower": 6},
    {"upper": 0x0027bcaa, "lower": 6},
    {"upper": 0x0027fec2, "lower": 6},
    {"upper": 0x00280fc6, "lower": 6},
    {"upper": 0x00281afa, "lower": 6},
    {"upper": 0x002845e6, "lower": 6},
    {"upper": 0x00285016, "lower": 6},
    {"upper": 0x00285b3a, "lower": 6},
    {"upper": 0x002866da, "lower": 6},
    {"upper": 0x00287c72, "lower": 6},
    {"upper": 0x00288f5e, "lower": 6},
    {"upper": 0x00289f8e, "lower": 6},
    {"upper": 0x0028b0c2, "lower": 6},
    {"upper": 0x0028c3a6, "lower": 6},
    {"upper": 0x0028d40e, "lower": 6},
    {"upper": 0x0028da56, "lower": 6},
    {"upper": 0x0028e132, "lower": 6},
    {"upper": 0x0028fc16, "lower": 6},
    {"upper": 0x00290762, "lower": 6},
    {"upper": 0x002913f2, "lower": 6},
    {"upper": 0x0029264e, "lower": 6},
    {"upper": 0x00292f1a, "lower": 6},
    {"upper": 0x00294836, "lower": 6},
    {"upper": 0x0029522a, "lower": 6},
    {"upper": 0x00295f2a, "lower": 6},
    {"upper": 0x00296ffe, "lower": 6},
    {"upper": 0x00297462, "lower": 6},
    {"upper": 0x00297f02, "lower": 6},
    {"upper": 0x0029979e, "lower": 6},
    {"upper": 0x00299f42, "lower": 6},
    {"upper": 0x0029a67e, "lower": 6},
    {"upper": 0x0029fe06, "lower": 6},
    {"upper": 0x002a46d6, "lower": 6},
    {"upper": 0x002b6656, "lower": 6},
    {"upper": 0x002b96ee, "lower": 6},
    {"upper": 0x002fcad2, "lower": 6},
    {"upper": 0x002ff5f6, "lower": 6},
    {"upper": 0x003006ee, "lower": 6},
    {"upper": 0x00305662, "lower": 2},
    {"upper": 0x003092ce, "lower": 6},
    {"upper": 0x0030cb6a, "lower": 6},
    {"upper": 0x00313a1a, "lower": 6},
    {"upper": 0x00316a02, "lower": 6},
]
# MP1_PAL 0x10357D0
_hvqfs_offsets[Game.MP2_USA] = [
    # Default at 0x01164160
    {"upper": 0x00054bd2, "lower": 0x00054bda},
    {"upper": 0x00063a36, "lower": 0x00063a3e},
    {"upper": 0x00074d6a, "lower": 0x00074d6e},
    {"ovl": 0x3f, "upper": 0x9a, "lower": 0xa2}, # ROM: 0x2A8A3A
    {"ovl": 0x40, "upper": 0x96, "lower": 0x9e}, # ROM: 0x2AEE46
    {"ovl": 0x42, "upper": 0x9a, "lower": 0xa2}, # ROM: 0x2C081A
    {"ovl": 0x44, "upper": 0x9a, "lower": 0xa2}, # ROM: 0x2DA94A
    {"ovl": 0x46, "upper": 0x9e, "lower": 0xa6}, # ROM: 0x2F17CE
    {"ovl": 0x48, "upper": 0xa2, "lower": 0xaa}, # ROM: 0x306C42
    {"ovl": 0x4a, "upper": 0x9a, "lower": 0xa2}, # ROM: 0x31EEDA
    {"ovl": 0x4d, "upper": 0xe12, "lower": 0xe1a}, # ROM: 0x329842
    {"ovl": 0x4e, "upper": 0xae, "lower": 0xb6}, # ROM: 0x32A26E
    {"ovl": 0x4f, "upper": 0xa6, "lower": 0xae}, # ROM: 0x3354E6
    {"ovl": 0x50, "upper": 0xa6, "lower": 0xae}, # ROM: 0x343106
    {"ovl": 0x51, "upper": 0x57fa, "lower": 0x5802}, # ROM: 0x35860A
    {"ovl": 0x52, "upper": 0x340e, "lower": 0x3416}, # ROM: 0x35C1EE
    {"ovl": 0x53, "upper": 0x9a, "lower": 0xa2}, # ROM: 0x35D1AA
    {"ovl": 0x54, "upper": 0xf6e, "lower": 0xf76}, # ROM: 0x3615DE
    {"ovl": 0x55, "upper": 0x9e, "lower": 0xa6}, # ROM: 0x36178E
    {"ovl": 0x62, "upper": 0xce, "lower": 0xd6}, # ROM: 0x3D4DEE
    {"ovl": 0x6d, "upper": 0x39e2, "lower": 0x39ea}, # ROM: 0x40A022
    {"ovl": 0x6e, "upper": 0x15b6, "lower": 0x15be}, # ROM: 0x40B8E6
    {"ovl": 0x70, "upper": 0x1b5a, "lower": 0x1b62}, # ROM: 0x4107BA
    {"ovl": 0x72, "upper": 0x1e, "lower": 0x26}, # ROM: 0x4157AE
]
# MP2 JPN 0x1156170
_hvqfs_offsets[Game.MP3_USA] = [
    # Default at 0x128CC60
    {"ovl": 0x81, "upper": 0x11e66, "lower": 0x11e6e}, # ROM: 0xD07A6
    {"ovl": 0x81, "upper": 0x25716, "lower": 0x2571e}, # ROM: 0xE4056
    {"ovl": 0x80, "upper": 0x1304a, "lower": 0x13052}, # ROM: 0xFD7DA
    {"ovl": 0x80, "upper": 0x21e86, "lower": 0x21e8e}, # ROM: 0x10C616
    {"ovl": 0x4f, "upper": 0x632a, "lower": 0x6332}, # ROM: 0x3BF99A
    {"ovl": 0x50, "upper": 0x3946, "lower": 0x394e}, # ROM: 0x3C6106
    {"ovl": 0x51, "upper": 0x1a62, "lower": 0x1a6a}, # ROM: 0x3C7D72
    {"ovl": 0x53, "upper": 0x3372, "lower": 0x337a}, # ROM: 0x3CDB72
    {"ovl": 0x54, "upper": 0x1bd6, "lower": 0x1bde}, # ROM: 0x3CFA96
    {"ovl": 0x62, "upper": 0x51d6, "lower": 0x51de}, # ROM: 0x45A696
    {"ovl": 0x64, "upper": 0x380a, "lower": 0x3812}, # ROM: 0x463F9A
    {"ovl": 0x65, "upper": 0x2f4a, "lower": 0x2f52}, # ROM: 0x4672AA
    {"ovl": 0x6e, "upper": 0xa3ba, "lower": 0xa3be}, # ROM: 0x4CCF8A
    {"ovl": 0x71, "upper": 0x1632, "lower": 0x163a}, # ROM: 0x4E83F2
    {"ovl": 0x73, "upper": 0x12a, "lower": 0x132}, # ROM: 0x4F031A
    {"ovl": 0x74, "upper": 0x55e, "lower": 0x566}, # ROM: 0x4F3CDE
    {"ovl": 0x7a, "upper": 0x274a, "lower": 0x2752}, # ROM: 0x52671A
    {"ovl": 0x7c, "upper": 0x787a, "lower": 0x787e}, # ROM: 0x549A9A
    {"ovl": 0x7d, "upper": 0x18ee, "lower": 0x18f6}, # ROM: 0x54F5FE
    {"ovl": 0x7d, "upper": 0x28b6, "lower": 0x28be}, # ROM: 0x5505C6
]
# MP3 JPN 0x1287380


_METADATA_LAYOUT = (
    # (key, offset, is_float). Note the Y/Z order in the file.
    ("tileWidth", 0, False),
    ("tileHeight", 4, False),
    ("tileCountX", 8, False),
    ("tileCountY", 12, False),
    ("fov", 16, True),
    ("scaleFactor", 20, True),
    ("cameraEyePosX", 24, True),
    ("cameraEyePosZ", 28, True),
    ("cameraEyePosY", 32, True),
    ("lookatPointX", 36, True),
    ("lookatPointZ", 40, True),
    ("lookatPointY", 44, True),
    ("cameraUpVecX", 48, True),
    ("cameraUpVecZ", 52, True),
    ("cameraUpVecY", 56, True),
)

# The order the TypeScript object literal lists the keys in (the file's).
_METADATA_KEYS = tuple(key for key, _, _ in _METADATA_LAYOUT)


def _read_patch(scenes, rom, patch_info):
    if isinstance(patch_info.get("ovl"), int):
        scene_view = scenes.get_data_view(patch_info["ovl"])
        return scene_view.get_uint16(patch_info["upper"]), scene_view.get_uint16(patch_info["lower"])
    rom_view = rom.get_data_view()
    return rom_view.get_uint16(patch_info["upper"]), rom_view.get_uint16(patch_info["lower"])


class HVQFS:
    def __init__(self, rom):
        self._rom = rom
        self._hvq_cache = None
        self._hvq_metadata = None

    def get_rom_offset(self):
        from ..utils.mips import get_reg_set_address
        rom = self._rom
        scenes = rom.get_scenes() if rom else None
        if not scenes:
            return None

        patch_offsets = self.get_patch_offsets()
        if not patch_offsets:
            return None
        rom_patch_info = patch_offsets[0]
        if not rom_patch_info:
            return None
        upper, lower = _read_patch(scenes, rom, rom_patch_info)

        offset = get_reg_set_address(upper, lower)

        # $$log(`HVQFS.getROMOffset -> ${$$hex(offset)}`);

        if is_debug():
            # Assert that the rest of the patch offsets are valid.
            for i in range(1, len(patch_offsets)):
                another_patch_offset = patch_offsets[i]
                another_upper, another_lower = _read_patch(scenes, rom, another_patch_offset)
                if another_upper != upper or another_lower != lower:
                    raise RuntimeError(
                        "HVQFS.getROMOffset patch offset %d seems wrong:\n"
                        "          offset: %s vs %s\n"
                        "          reading upper: %s, lower: %s" % (
                            i, hexstr(offset),
                            hexstr(another_upper >> 16) + hexstr(another_lower, ""),
                            hexstr(another_patch_offset["upper"]),
                            hexstr(another_patch_offset["lower"])))

        return offset

    def set_rom_offset(self, new_offset, buffer):
        from ..utils.mips import get_reg_set_upper_and_lower
        log("HVQFS.setROMOffset(%s)" % hexstr(new_offset))
        rom = self._rom
        scenes = rom.get_scenes()
        patch_offsets = self.get_patch_offsets()
        upper, lower = get_reg_set_upper_and_lower(new_offset)
        for patch_offset in patch_offsets:
            if isinstance(patch_offset.get("ovl"), int):
                scene_view = scenes.get_data_view(patch_offset["ovl"])
                scene_view.set_uint16(patch_offset["upper"], upper)
                scene_view.set_uint16(patch_offset["lower"], lower)
            else:
                rom_view = DataView(buffer)
                rom_view.set_uint16(patch_offset["upper"], upper)
                rom_view.set_uint16(patch_offset["lower"], lower)
        log("HVQFS.setROMOffset -> %s" % hexstr(((upper << 16) | lower) & 0xFFFFFFFF))

    def get_patch_offsets(self):
        game_offsets = _hvqfs_offsets.get(self._rom.get_game())
        if not game_offsets:
            return None

        result = []
        for offset in game_offsets:
            if offset["lower"] < 10 and not offset.get("ovl"):
                # Delete when JPN is converted
                result.append({
                    "upper": offset["upper"],
                    "lower": offset["upper"] + 2 + offset["lower"],
                })
            else:
                result.append({
                    "upper": offset["upper"],
                    "lower": offset["lower"],
                    "ovl": offset.get("ovl"),
                })
        return result

    def get(self, dir, file):
        return self._hvq_cache[dir][file]

    def read(self, dir, file):
        buffer = self._rom.get_buffer()

        fs_offset = self.get_rom_offset()
        fs_view = DataView(buffer, fs_offset)

        bg_offset = fs_offset + fs_view.get_uint32(4 * (1 + dir))
        bg_view = DataView(buffer, bg_offset)

        file_offset = bg_offset + bg_view.get_uint32(4 * (1 + file))
        next_file_offset = bg_offset + bg_view.get_uint32(4 * (1 + file + 1))

        return bytearray(buffer[file_offset:next_file_offset])

    def write(self, dir, file, content):
        self._hvq_cache[dir][file] = bytearray(content)

    def extract(self):
        t0 = time.perf_counter() if is_debug() else None

        bg_count = self.get_directory_count()
        self._hvq_cache = [None] * bg_count
        self._hvq_metadata = [None] * bg_count
        for b in range(bg_count):
            file_count = self.get_hvq_file_count(b)
            self._hvq_cache[b] = [self.read(b, f) for f in range(file_count)]
            self._read_metadata(b)

        if t0 is not None:
            log("HVQFS.extract() -> %sms" % ((time.perf_counter() - t0) * 1000))

        return self._hvq_cache

    extract_async = extract

    def pack(self, buffer, offset=0):
        view = DataView(buffer, offset)

        bg_count = self.get_directory_count()
        view.set_uint32(0, bg_count + 1)

        cur_bg_index_offset = 4
        cur_bg_write_offset = 4 + (bg_count + 1) * 4
        for b in range(bg_count):
            view.set_uint32(cur_bg_index_offset, cur_bg_write_offset)
            cur_bg_index_offset += 4
            cur_bg_write_offset = self._write_bg(b, view, cur_bg_write_offset)
            cur_bg_write_offset = make_divisible_by(cur_bg_write_offset, 4)

        view.set_uint32(cur_bg_index_offset, cur_bg_write_offset)

        return cur_bg_write_offset

    def _write_bg(self, b, view, offset):
        file_count = self.get_hvq_file_count(b)
        view.set_uint32(offset, file_count + 1)

        self._write_metadata(b)

        cur_file_index_offset = offset + 4
        cur_file_write_offset = offset + 4 + (file_count + 1) * 4
        for f in range(file_count):
            view.set_uint32(cur_file_index_offset, cur_file_write_offset - offset)
            cur_file_index_offset += 4
            cur_file_write_offset = self._write_file(b, f, view, cur_file_write_offset)
            cur_file_write_offset = make_divisible_by(cur_file_write_offset, 4)

        view.set_uint32(cur_file_index_offset, cur_file_write_offset - offset)

        return cur_file_write_offset

    def _write_file(self, b, f, view, offset):
        file_bytes = self._hvq_cache[b][f]
        copy_range(view, file_bytes, offset, 0, len(file_bytes))
        return offset + len(file_bytes)

    def _read_metadata(self, dir):
        info_view = DataView(self._hvq_cache[dir][0], 0)
        metadata = {}
        for key, off, is_float in _METADATA_LAYOUT:
            metadata[key] = info_view.get_float32(off) if is_float else info_view.get_uint32(off)
        self._set_metadata(dir, metadata)

    def _write_metadata(self, dir):
        info_view = DataView(self._hvq_cache[dir][0], 0)
        metadata = self.get_metadata(dir)
        for key, off, is_float in _METADATA_LAYOUT:
            if is_float:
                info_view.set_float32(off, _js_number(metadata.get(key)))
            else:
                info_view.set_uint32(off, _js_int(metadata.get(key)))

    def _get_bg_dimensions(self, dir):
        metadata = self._hvq_metadata[dir]

        width = metadata["tileWidth"] * metadata["tileCountX"]
        height = metadata["tileHeight"] * metadata["tileCountY"]
        return [width, height]

    def get_metadata(self, dir):
        return self._hvq_metadata[dir]

    def _set_metadata(self, dir, metadata):
        while len(self._hvq_metadata) <= dir:
            self._hvq_metadata.append(None)
        self._hvq_metadata[dir] = metadata

    def update_metadata(self, dir, values):
        """Updates the HVQ metadata to reflect new values.

        Need to be careful, old boards may not have all or some values.
        values is a dict with the camelCase metadata keys (a board's bg).
        """
        metadata = self.get_metadata(dir)
        for key in ("tileWidth", "tileHeight", "tileCountX", "tileCountY", "fov", "scaleFactor",
                    "cameraEyePosX", "cameraEyePosZ", "cameraEyePosY",
                    "lookatPointX", "lookatPointZ", "lookatPointY",
                    "cameraUpVecX", "cameraUpVecZ", "cameraUpVecY"):
            if key in values:
                metadata[key] = values[key]
        self._set_metadata(dir, metadata)

    def read_background_img_data(self, dir):
        """Return the ImageData of background `dir`."""
        tile_count = len(self._hvq_cache[dir]) - 1

        metadata = self.get_metadata(dir)
        tile_width = metadata["tileWidth"]
        tile_height = metadata["tileHeight"]
        tile_x_count = metadata["tileCountX"]
        tile_y_count = metadata["tileCountY"]

        width = tile_width * tile_x_count
        height = tile_height * tile_y_count

        log("HVQFS.readBackground, dir: %s, tiles: %s, board is %sx%s" % (dir, tile_count, width, height))

        # Grab DataViews of all of the tiles.
        game = self._rom.get_game_version()
        adjust = 1 if game == 1 else 2  # Skip HVQ-MPS in newer games
        hvq_tiles = [DataView(t) for t in self._hvq_cache[dir][adjust:]]
        rgba16_tiles = [decode(t) for t in hvq_tiles]
        rgba16_views = [DataView(t) for t in rgba16_tiles]
        ordered_rgb16_tiles = []
        for y in range(tile_y_count - 1, -1, -1):
            for x in range(tile_x_count):
                ordered_rgb16_tiles.append(rgba16_views[y * tile_x_count + x])
        bg_buffer_rgba16 = from_tiles(ordered_rgb16_tiles, tile_x_count, tile_y_count,
                                      tile_width * 2, tile_height)
        bg_buffer_rgba32 = rgba5551to_rgba32(bg_buffer_rgba16, width, height)
        return ImageData(width, height, bg_buffer_rgba32)

    def is_hvq_compressed(self, dir):
        """Return whether background `dir` has HVQ-compressed tiles.

        Real HVQ decoding was never implemented (utils/img/hvq.py), so these
        tiles read as black: the game's own backgrounds. Backgrounds written by
        PartyPlanner64 use other encodings and read properly.
        """
        tiles = self._hvq_cache[dir] if dir < len(self._hvq_cache) else None
        if not tiles:
            return False
        adjust = 1 if self._rom.get_game_version() == 1 else 2
        return any(bytes(t[:3]) == b"HVQ" for t in tiles[adjust:])

    def read_background(self, dir):
        """Return the background as the metadata plus width, height and src (a PNG data URL)."""
        metadata = self.get_metadata(dir)
        width, height = self._get_bg_dimensions(dir)
        bg_image_data = self.read_background_img_data(dir)
        result = dict(metadata)
        result.update({
            "width": width,
            "height": height,
            "src": image_data_to_data_url(bg_image_data),
        })
        return result

    def write_background(self, dir, img_data, width, height, metadata=None):
        tile_x_count = width // 64
        tile_y_count = height // 48
        tile_count = tile_x_count * tile_y_count

        log("HVQFS.writeBackground, dir: %s, img is %sx%s" % (dir, width, height))

        rgba32tiles = to_tiles(img_data.data, tile_x_count, tile_y_count, 64 * 4, 48)
        rgba16tiles = [rgba5551from_rgba32(tile32, 64, 48) for tile32 in rgba32tiles]
        hvq_tiles = [encode(tile16, 64, 48) for tile16 in rgba16tiles]

        ordered_hvq_tiles = []
        for y in range(tile_y_count - 1, -1, -1):
            for x in range(tile_x_count):
                ordered_hvq_tiles.append(hvq_tiles[y * tile_x_count + x])

        game = self._rom.get_game_version()

        if dir >= len(self._hvq_cache) or self._hvq_cache[dir] is None:
            if not metadata:
                raise ValueError("Cannot write a new HVQ background without metadata")

            while len(self._hvq_cache) <= dir:
                self._hvq_cache.append(None)  # A sparse array in the TypeScript.
            self._hvq_cache[dir] = []

            # TODO: Hard coding these seems bad.
            if game > 1:
                self._hvq_cache[dir].append(self._hvq_cache[3][0])

                # Well... we probably need HVQ-MPS, but for now it doesn't matter which.
                self._hvq_cache[dir].append(self._hvq_cache[3][1])
            else:
                self._hvq_cache[dir].append(self._hvq_cache[0][0])
            self._read_metadata(dir)

        if metadata:
            self.update_metadata(dir, metadata)

        files = self._hvq_cache[dir]
        first = 1 if game == 1 else 2  # MP2/3 also has the HVQ-MPS to skip
        for i in range(first, tile_count + first):
            tile = ordered_hvq_tiles[i - first]
            if i < len(files):
                files[i] = tile
            else:
                files.append(tile)

    def get_directory_count(self):
        if self._hvq_cache is not None:
            return len(self._hvq_cache)

        buffer = self._rom.get_buffer()
        hvq_fs_offset = self.get_rom_offset()
        if hvq_fs_offset is None:
            return 0
        hvq_fs_view = DataView(buffer, hvq_fs_offset)
        return hvq_fs_view.get_uint32(0) - 1  # The last dir is a fake.

    def get_hvq_file_count(self, dir):
        if self._hvq_cache is not None and dir < len(self._hvq_cache) and self._hvq_cache[dir] is not None:
            return len(self._hvq_cache[dir])

        buffer = self._rom.get_buffer()
        hvq_fs_offset = self.get_rom_offset()
        if hvq_fs_offset is None:
            return 0
        hvq_fs_view = DataView(buffer, hvq_fs_offset)

        hvq_file_offset = hvq_fs_offset + hvq_fs_view.get_uint32(4 * (1 + dir))
        hvq_file_view = DataView(buffer, hvq_file_offset)
        return hvq_file_view.get_uint32(0) - 1  # The last file is a lie.

    def get_byte_length(self):
        byte_len = 0

        bg_count = len(self._hvq_cache)

        byte_len += 4  # Count of backgrounds
        byte_len += 4 * (bg_count + 1)  # Background offsets + the extra offset

        for b in range(bg_count):
            file_count = len(self._hvq_cache[b])

            byte_len += 4  # Count of files
            byte_len += 4 * (file_count + 1)  # File offsets + the extra offset

            for f in range(file_count):
                byte_len += len(self._hvq_cache[b][f])
                byte_len = make_divisible_by(byte_len, 4)

        return byte_len


def _js_number(value):
    """ToNumber for a metadata value (undefined -> NaN)."""
    if value is None:
        return float("nan")
    return float(value)


def _js_int(value):
    """ToUint32 for a metadata value (undefined/NaN -> 0)."""
    if value is None:
        return 0
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        return 0
    return int(value)
