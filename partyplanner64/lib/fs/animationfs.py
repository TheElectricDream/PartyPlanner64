"""Animated board backgrounds of Mario Party 2 (port of fs/animationfs.ts).

The cache is a list of sets; a set is a list of entries; an entry is a dict
{tile index: {"compression_type", "decompressed", "compressed"}} (an
object with integer keys in the TypeScript, visited in ascending order).
"""

from ..types import Game
from ..utils.arrays import array_buffers_equal, copy_range
from ..utils.canvas import ImageData, image_data_to_data_url
from ..utils.compression import compress, decompress, get_compressed_size
from ..utils.dataview import DataView
from ..utils.debug import hexstr, log
from ..utils.img.rgba5551 import rgba5551from_rgba32, rgba5551to_rgba32
from ..utils.img.tiler import from_tiles, to_tiles
from ..utils.number import make_divisible_by

_anim_fs_offsets = {}
_anim_fs_offsets[Game.MP2_USA] = [
    # 0x16EC470
    {"upper": 0x000546C6, "lower": 0x000546CA},
]


class Animationfs:
    def __init__(self, rom):
        self._rom = rom
        self._animfs_cache = None

    def get_rom_offset(self):
        rom_view = self._rom.get_data_view()
        patch_offsets = self.get_patch_offsets()
        if not patch_offsets:
            return None
        rom_offset = patch_offsets[0]
        upper = rom_view.get_uint16(rom_offset["upper"]) << 16
        lower = rom_view.get_uint16(rom_offset["lower"])
        offset = (upper | lower) & 0xFFFFFFFF
        if offset & 0x80000000:
            offset -= 0x100000000
        if lower & 0x8000:
            offset = offset - 0x00010000  # Account for signed addition workaround.
        log("AnimationFS.getROMOffset -> %s" % hexstr(offset))
        return offset

    def set_rom_offset(self, new_offset, buffer):
        rom_view = DataView(buffer)
        patch_offsets = self.get_patch_offsets()
        if not patch_offsets:
            return
        upper = (new_offset & 0xFFFF0000) >> 16
        lower = new_offset & 0x0000FFFF
        if lower & 0x8000:
            upper += 1  # ASM adjust for the signed addition.
        for patch_offset in patch_offsets:
            rom_view.set_uint16(patch_offset["upper"], upper)
            rom_view.set_uint16(patch_offset["lower"], lower)
        log("AnimationFS.setROMOffset -> %s" % hexstr(((upper << 16) | lower) & 0xFFFFFFFF))

    def get_patch_offsets(self):
        return _anim_fs_offsets.get(self._rom.get_game())

    def get(self, set, entry, index):
        return self._animfs_cache[set][entry][index]["decompressed"]

    def write(self, set, entry, tile_buffer, index):
        compressed = compress(3, tile_buffer)

        while len(self._animfs_cache) <= set:
            self._animfs_cache.append(None)
        if self._animfs_cache[set] is None:
            self._animfs_cache[set] = []
        entries = self._animfs_cache[set]
        while len(entries) <= entry:
            entries.append(None)
        if entries[entry] is None:
            entries[entry] = {}
        entries[entry][index] = {
            "compression_type": 3,
            "decompressed": tile_buffer,
            "compressed": compressed,
        }

    def _create_ordered_tiles(self, img_data, width, height):
        tile_x_count = width // 64
        tile_y_count = height // 48

        tiles32 = to_tiles(img_data.data, tile_x_count, tile_y_count, 64 * 4, 48)
        tiles16 = [rgba5551from_rgba32(tile32, 64, 48) for tile32 in tiles32]
        ordered_tiles = []
        for y in range(tile_y_count - 1, -1, -1):
            for x in range(tile_x_count):
                ordered_tiles.append(tiles16[y * tile_x_count + x])
        return ordered_tiles

    def write_animation_background(self, set, entry, main_img_data, anim_img_data, width, height):
        log("AnimationFS.writeAnimationBackground, set: %s, entry: %s, img is %sx%s"
            % (set, entry, width, height))

        ordered_main_tiles = self._create_ordered_tiles(main_img_data, width, height)
        ordered_anim_tiles = self._create_ordered_tiles(anim_img_data, width, height)

        self.clear_set_entry(set, entry)

        # Write the tiles that are different to the sparse tree.
        for i in range(len(ordered_anim_tiles)):
            if not array_buffers_equal(ordered_main_tiles[i], ordered_anim_tiles[i]):
                self.write(set, entry, ordered_anim_tiles[i], i + 1)

    def _unorder_tiles(self, tiles, tile_x_count, tile_y_count):
        unordered = []
        for y in range(tile_y_count - 1, -1, -1):
            for x in range(tile_x_count):
                unordered.append(tiles[y * tile_x_count + x])
        return unordered

    def _read_animation_background(self, set, entry, ordered_main_tiles, width, height):
        tiles = self._animfs_cache[set][entry]
        ordered_anim_bg_tiles = []
        for i in range(len(ordered_main_tiles)):
            if (i + 1) in tiles:
                ordered_anim_bg_tiles.append(DataView(tiles[i + 1]["decompressed"]))
            else:
                ordered_anim_bg_tiles.append(DataView(ordered_main_tiles[i]))

        tile_width = 64
        tile_height = 48
        tile_x_count = width // 64
        tile_y_count = height // 48

        ordered_anim_bg_tiles = self._unorder_tiles(ordered_anim_bg_tiles, tile_x_count, tile_y_count)

        bg_buffer_rgba16 = from_tiles(ordered_anim_bg_tiles, tile_x_count, tile_y_count,
                                      tile_width * 2, tile_height)
        bg_buffer_rgba32 = rgba5551to_rgba32(bg_buffer_rgba16, width, height)
        return image_data_to_data_url(ImageData(width, height, bg_buffer_rgba32))

    def read_animation_backgrounds(self, set, main_img_data, width, height):
        """Return a PNG data URL for each animation frame of a set."""
        entries = self.get_set_entry_count(set)
        ordered_main_tiles = self._create_ordered_tiles(main_img_data, width, height)
        return [self._read_animation_background(set, entry, ordered_main_tiles, width, height)
                for entry in range(entries)]

    def extract(self):
        starting_offset = self.get_rom_offset()
        if starting_offset is None:
            return None
        view = self._rom.get_data_view()
        self._animfs_cache = self._extract_sets(view, starting_offset)
        return self._animfs_cache

    extract_async = extract

    def _extract_sets(self, view, offset):
        sets = []
        count = view.get_uint32(offset) - 1  # Extra offset
        for i in range(count):
            set_offset = view.get_uint32(offset + 4 + i * 4)
            sets.append(self._extract_set_entries(view, offset + set_offset))
        return sets

    def _extract_set_entries(self, view, offset):
        set_entries = []
        count = view.get_uint32(offset)
        for i in range(count):
            set_entry_offset = view.get_uint32(offset + 4 + i * 4)
            set_entries.append(self._extract_tiles(view, offset + set_entry_offset))
        return set_entries

    def _extract_tiles(self, view, offset):
        tiles = {}
        count = view.get_uint32(offset) - 1  # Extra offset
        for i in range(count):
            tile_offset = view.get_uint32(offset + 4 + i * 4)
            tile = self._read_tile(view, offset + tile_offset)
            tiles[tile["index"]] = {
                "compression_type": tile["compression_type"],
                "compressed": tile["compressed"],
                "decompressed": tile["decompressed"],
            }
        return dict(sorted(tiles.items()))

    def _read_tile(self, view, offset):
        index = view.get_uint32(offset)
        compression_type = view.get_uint32(offset + 4)  # 3
        decompressed_size = view.get_uint32(offset + 8)  # 0x1800
        buffer = view.buffer
        file_start_offset = offset + 12
        file_start_view = DataView(buffer, file_start_offset)
        decompressed = decompress(compression_type, file_start_view, decompressed_size)
        compressed_size = decompressed.compressed_size
        if compressed_size is None:
            compressed_size = get_compressed_size(compression_type, file_start_view, decompressed_size)
        return {
            "index": index,
            "compression_type": compression_type,
            "compressed": bytearray(buffer[file_start_offset:file_start_offset + (compressed_size or 0)]),
            "decompressed": decompressed,
        }

    def pack(self, buffer, offset=0):
        view = DataView(buffer, offset)

        set_count = self.get_set_count()
        view.set_uint32(0, set_count + 1)  # Extra offset

        cur_set_index_offset = 4
        cur_set_write_offset = 4 + (set_count + 1) * 4
        for s in range(set_count):
            view.set_uint32(cur_set_index_offset, cur_set_write_offset)
            cur_set_index_offset += 4
            cur_set_write_offset = self._write_set(s, view, cur_set_write_offset)
            cur_set_write_offset = make_divisible_by(cur_set_write_offset, 4)

        view.set_uint32(cur_set_index_offset, cur_set_write_offset)  # Extra offset

        return cur_set_write_offset

    def _write_set(self, s, view, offset):
        set_entry_count = self.get_set_entry_count(s)
        view.set_uint32(offset, set_entry_count)  # No extra offsets at middle layer

        cur_set_entry_index_offset = offset + 4
        cur_set_entry_write_offset = offset + 4 + set_entry_count * 4
        for e in range(set_entry_count):
            view.set_uint32(cur_set_entry_index_offset, cur_set_entry_write_offset - offset)
            cur_set_entry_index_offset += 4
            cur_set_entry_write_offset = self._write_tiles(s, e, view, cur_set_entry_write_offset)
            cur_set_entry_write_offset = make_divisible_by(cur_set_entry_write_offset, 4)

        return cur_set_entry_write_offset

    def _write_tiles(self, s, e, view, offset):
        tile_count = self.get_set_entry_tile_count(s, e)
        view.set_uint32(offset, tile_count + 1)  # Extra offset

        cur_tile_index_offset = offset + 4
        cur_tile_write_offset = offset + 4 + (tile_count + 1) * 4
        for t in sorted(self._animfs_cache[s][e]):
            view.set_uint32(cur_tile_index_offset, cur_tile_write_offset - offset)
            cur_tile_index_offset += 4
            cur_tile_write_offset = self._write_tile(s, e, t, view, cur_tile_write_offset)
            cur_tile_write_offset = make_divisible_by(cur_tile_write_offset, 4)

        view.set_uint32(cur_tile_index_offset, cur_tile_write_offset - offset)

        return cur_tile_write_offset

    def _write_tile(self, s, e, t, view, offset):
        tile = self._animfs_cache[s][e][t]
        view.set_uint32(offset, int(t))
        view.set_uint32(offset + 4, 3)  # Compression type
        view.set_uint32(offset + 8, len(tile["decompressed"]))  # Decompressed size
        copy_range(view, tile["compressed"], offset + 12, 0, len(tile["compressed"]))
        return offset + 12 + len(tile["compressed"])

    def get_set_count(self):
        return len(self._animfs_cache)

    def get_set_entry_count(self, set):
        return len(self._animfs_cache[set])

    # This is exposed so that we can blow away animations for a stock board (count = 0)
    def set_set_entry_count(self, set, count):
        entries = self._animfs_cache[set]
        del entries[count:]
        while len(entries) < count:
            entries.append(None)
        return count

    def clear_set_entry(self, set, entry):
        entries = self._animfs_cache[set]
        while len(entries) <= entry:
            entries.append(None)
        entries[entry] = {}
        return entries[entry]

    def get_set_entry_tile_count(self, set, entry):
        return len(self._animfs_cache[set][entry])

    def get_byte_length(self):
        byte_len = 0

        set_count = self.get_set_count()
        byte_len += 4  # Count of sets
        byte_len += 4 * (set_count + 1)  # Set offsets + the extra offset

        for s in range(set_count):
            set_entry_count = self.get_set_entry_count(s)

            byte_len += 4  # Count of set entries
            byte_len += 4 * set_entry_count  # Set entry offsets (no extra offset)

            for e in range(set_entry_count):
                tile_count = self.get_set_entry_tile_count(s, e)
                byte_len += 4  # Count of tiles
                byte_len += 4 * (tile_count + 1)  # Tile offsets + the extra offset

                for t in sorted(self._animfs_cache[s][e]):
                    tile = self._animfs_cache[s][e][t]
                    byte_len += 4  # Index
                    byte_len += 4  # Compression type
                    byte_len += 4  # Decompressed size
                    byte_len += len(tile["compressed"])
                    byte_len = make_divisible_by(byte_len, 4)

        return byte_len
