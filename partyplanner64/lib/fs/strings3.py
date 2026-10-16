"""The localized string tables of Mario Party 3 (port of fs/strings3.ts)."""

from ..types import Game
from ..utils.arrays import copy_range
from ..utils.compression import decompress
from ..utils.dataview import DataView
from ..utils.debug import hexstr, log
from ..utils.number import make_divisible_by
from .strings import StringTable, _rom_offset_from_patch

# Locales: "jp", "en", "de", "es", "it", "fr".
_string_offsets = {}
_string_offsets[Game.MP3_USA] = {
    "jp": [
        {"upper": 0x0000F142, "lower": 0x0000F14A},  # 0x1209850, len 0x13250
        {"upper": 0x0005B3CA, "lower": 0x0005B3D2},
    ],
    "en": [
        {"upper": 0x0005B412, "lower": 0x0005B41A},  # 0x121CAA0
    ],
    "de": [
        {"upper": 0x0005B42A, "lower": 0x0005B432},  # 0x12355C0
    ],
    "es": [
        {"upper": 0x0005B436, "lower": 0x0005B43E},  # 0x12765F0
    ],
    "it": [
        {"upper": 0x0005B442, "lower": 0x0005B446},  # 0x1261F90
    ],
    "fr": [
        {"upper": 0x0005B41E, "lower": 0x0005B426},  # 0x124D440
    ],
}
_string_offsets[Game.MP3_JPN] = {
    "jp": [
        {"upper": 0x0000F142, "lower": 0x0000F14A},  # 0x1206E00
        {"upper": 0x0005B262, "lower": 0x0005B26A},
    ],
    # "en": [
    #   { upper: , lower:  }, // 0x121A050
    # ],
    # "de": [
    #   { upper: , lower:  }, // 0x122FCE0
    # ],
    # "es": [
    #   { upper: , lower:  }, // 0x1247B60
    # ],
    # "it": [
    #   { upper: , lower:  }, // 0x125C6B0
    # ],
    # "fr": [
    #   { upper: , lower:  }, // 0x1270D10
    # ],
}


class StringTableSet:
    def __init__(self, data_view):
        self.dirs = self._extract(data_view)

    def _extract(self, view):
        dir_count = self._get_directory_count_from_view(view)
        return [self._read_dir_from_view(view, d) for d in range(dir_count)]

    def _get_directory_count_from_view(self, view):
        return view.get_uint32(0)

    def _read_dir_from_view(self, view, dir):
        entry_offset = self._get_dir_offset_from_view(view, dir)
        entry_view = DataView(view.buffer, view.byte_offset + entry_offset)
        decompressed_dir = self._decompress_dir(entry_view)
        return StringTable(DataView(decompressed_dir))

    def _decompress_dir(self, view):
        decompressed_size = view.get_uint32(0)
        compression_type = view.get_uint32(4)
        dir_start_view = DataView(view.buffer, view.byte_offset + 8)
        return decompress(compression_type, dir_start_view, decompressed_size)

    def _get_dir_offset_from_view(self, view, dir):
        return view.get_uint32(4 * (1 + dir))

    def read(self, dir, index, raw=False):
        if dir < 0 or dir >= self.get_directory_count():
            raise IndexError("Requesting non-existent string directory")
        return self.dirs[dir].read(index, raw)

    def write(self, dir, index, content):
        self.dirs[dir].write(index, content)

    def get_directory_count(self):
        return len(self.dirs)

    def get_string_count(self, dir):
        return self.dirs[dir].get_string_count()

    def get_byte_length(self):
        byte_len = 0
        dir_count = len(self.dirs)

        byte_len += 4  # Count of directories
        byte_len += 4 * dir_count  # Directory offsets

        for d in range(dir_count):
            byte_len += 4  # Decompressed size
            byte_len += 4  # Compression type
            byte_len += self.dirs[d].get_byte_length()
            byte_len = make_divisible_by(byte_len, 2)

        return byte_len

    def pack(self, buffer, offset=0):
        view = DataView(buffer, offset)

        dir_count = self.get_directory_count()
        view.set_uint32(0, dir_count)

        cur_dir_index_offset = 4
        cur_dir_write_offset = 4 + dir_count * 4
        for d in range(dir_count):
            view.set_uint32(cur_dir_index_offset, cur_dir_write_offset)
            cur_dir_index_offset += 4
            view.set_uint32(cur_dir_write_offset, self.dirs[d].get_byte_length())  # Decompressed size
            cur_dir_write_offset += 4
            view.set_uint32(cur_dir_write_offset, 0)  # Compression type
            cur_dir_write_offset += 4
            cur_dir_write_offset = self._pack_dir(d, view, cur_dir_write_offset)
            cur_dir_write_offset = make_divisible_by(cur_dir_write_offset, 2)

        return cur_dir_write_offset

    def _pack_dir(self, d, view, offset):
        decompressed_size = self.dirs[d].get_byte_length()
        decompressed_buffer = bytearray(decompressed_size)
        self.dirs[d].pack(decompressed_buffer, 0)
        copy_range(view, decompressed_buffer, offset, 0, decompressed_size)
        return offset + decompressed_size


class Strings3:
    def __init__(self, rom):
        self._rom = rom
        self._str_fs_instances = None

    def get_rom_offset(self, locale="en"):
        from ..romhandler import romhandler
        rom_view = romhandler.get_data_view()
        locale_offsets = self.get_patch_offsets(locale)
        if not locale_offsets:
            return None
        rom_offset = locale_offsets[0]
        if not rom_offset:
            return None
        _, _, offset = _rom_offset_from_patch(rom_view, rom_offset)
        log("Strings3.getROMOffset[%s] -> %s" % (locale, hexstr(offset)))
        return offset

    def set_rom_offset(self, new_offset, buffer):
        from ..romhandler import romhandler
        rom_view = DataView(buffer)
        cur_offset = new_offset
        locales = self.get_locales(romhandler.get_rom_game())
        for locale in locales:
            patch_offsets = self.get_patch_offsets(locale)
            upper = (cur_offset & 0xFFFF0000) >> 16
            lower = cur_offset & 0x0000FFFF
            if lower & 0x8000:
                upper += 1  # Adjust for signed addition in ASM.
            for patch_offset in patch_offsets:
                rom_view.set_uint16(patch_offset["upper"], upper)
                rom_view.set_uint16(patch_offset["lower"], lower)
            log("Strings3.setROMOffset[%s] -> %s" % (locale, hexstr(((upper << 16) | lower) & 0xFFFFFFFF)))
            cur_offset += make_divisible_by(self._str_fs_instances[locale].get_byte_length(), 16)

    def get_patch_offsets(self, locale="en"):
        from ..romhandler import romhandler
        return _string_offsets[romhandler.get_rom_game()].get(locale)

    def clear(self):
        self._str_fs_instances = None

    def extract(self):
        from ..romhandler import romhandler
        self._str_fs_instances = {}
        for locale in self.get_locales(romhandler.get_rom_game()):
            locale_view = romhandler.get_data_view(self.get_rom_offset(locale))
            self._str_fs_instances[locale] = StringTableSet(locale_view)
        return self._str_fs_instances

    extract_async = extract

    def pack(self, buffer, offset=0):
        from ..romhandler import romhandler
        next_offset = offset
        for locale in self.get_locales(romhandler.get_rom_game()):
            instance = self._str_fs_instances[locale]
            next_offset = next_offset + instance.pack(buffer, next_offset)
            next_offset = make_divisible_by(next_offset, 16)
        return next_offset

    def read(self, locale, dir, index, raw=False):
        return self._str_fs_instances[locale].read(dir, index, raw)

    # Writes a pre-made buffer for now.
    def write(self, locale, dir, index, content):
        self._str_fs_instances[locale].write(dir, index, content)

    def get_locales(self, game):
        return list(_string_offsets[game].keys())

    def get_directory_count(self, locale):
        return self._str_fs_instances[locale].get_directory_count()

    def get_string_count(self, locale, dir):
        return self._str_fs_instances[locale].get_string_count(dir)

    # Gets the required byte length of the string section of the ROM.
    def get_byte_length(self):
        from ..romhandler import romhandler
        byte_len = 0
        for locale in self.get_locales(romhandler.get_rom_game()):
            byte_len += make_divisible_by(self._str_fs_instances[locale].get_byte_length(), 16)
        return byte_len
