"""The string table of Mario Party 1 and 2 (port of fs/strings.ts)."""

from ..debug import is_debug
from ..types import Game
from ..utils.arrays import copy_range
from ..utils.dataview import DataView
from ..utils.debug import hexstr, log
from ..utils.number import make_divisible_by

_string_offsets = {}
_string_offsets[Game.MP1_USA] = [{"upper": 0x0001AE6E, "lower": 0x0001AE76}]
_string_offsets[Game.MP1_JPN] = [{"upper": 0x0001AD9E, "lower": 0x0001ADA6}]
# TODO: PAL has more tables for other langs. Defining ENG only for now.
_string_offsets[Game.MP1_PAL] = [
    # Default at 0x0FF0850
    {"upper": 0x0001BA32, "lower": 0x0001BA36},
]
_string_offsets[Game.MP2_USA] = [
    # Default at 0x1142DD0
    {"upper": 0x0001D22A, "lower": 0x0001D232},
    {"upper": 0x00089356, "lower": 0x0008935E},
    {"upper": 0x0008936A, "lower": 0x00089372},
]
# MP2_JPN 0x113E720


def _get_character_map():
    from ..adapter.adapters import get_rom_adapter
    return get_rom_adapter({}).get_character_map()


def _map_get(map, val):
    """map[val] for a character map keyed by int (or by numeric strings)."""
    if val in map:
        return map[val]
    key = str(val)
    if key in map:
        return map[key]
    return None


class StringTable:
    def __init__(self, data_view):
        self.strs = self._extract(data_view)

    def _extract(self, view):
        str_count = self._get_string_count_from_view(view)
        return [self._read_from_view(view, s) for s in range(str_count)]

    def _get_string_count_from_view(self, view):
        return view.get_uint32(0)

    def _read_from_view(self, view, index):
        entry_offset = self._get_string_offset_from_view(view, index)
        entry_view = DataView(view.buffer, view.byte_offset + entry_offset)
        str_size = entry_view.get_uint16(0)
        start = view.byte_offset + entry_offset + 2
        return bytearray(view.buffer[start:start + str_size])

    def _get_string_offset_from_view(self, view, index):
        return view.get_uint32(4 * (1 + index))

    def read(self, index, raw=False):
        """Return string `index`: its bytes when raw, else the decoded text."""
        if index >= self.get_string_count():
            raise IndexError("Requesting non-existent string entry")

        data = self.strs[index]
        if raw:
            return data
        map = _get_character_map()
        return "".join(self._byte_to_str(b, map) for b in data)

    def _byte_to_str(self, val, map=None):
        if map is None:
            map = _get_character_map()
        mapped = _map_get(map, val)
        if mapped is not None:
            return mapped
        return chr(val)

    def write(self, index, content):
        self.strs[index] = bytearray(content)

    def get_string_count(self):
        return len(self.strs)

    def get_byte_length(self, apply_compression=False):
        byte_len = 0
        str_count = len(self.strs)

        byte_len += 4  # Count of strings
        byte_len += 4 * str_count  # String offsets

        for s in range(str_count):
            byte_len += 2  # String length
            byte_len += len(self.strs[s])
            byte_len = make_divisible_by(byte_len, 2)

        if apply_compression:
            # Assuming dumb compress01
            byte_len += byte_len / 8 + 16  # to be safe

        return byte_len

    def pack(self, buffer, offset=0):
        view = DataView(buffer, offset)

        str_count = self.get_string_count()
        view.set_uint32(0, str_count)

        cur_str_index_offset = 4
        cur_str_write_offset = 4 + str_count * 4
        for s in range(str_count):
            view.set_uint32(cur_str_index_offset, cur_str_write_offset)
            cur_str_index_offset += 4
            cur_str_write_offset = self._pack_str(s, view, cur_str_write_offset)
            cur_str_write_offset = make_divisible_by(cur_str_write_offset, 2)

        return cur_str_write_offset

    def _pack_str(self, s, view, offset):
        str_bytes = self.strs[s]
        view.set_uint16(offset, len(str_bytes))
        copy_range(view, str_bytes, offset + 2, 0, len(str_bytes))
        return offset + 2 + len(str_bytes)


def _rom_offset_from_patch(rom_view, rom_offset):
    upper = rom_view.get_uint16(rom_offset["upper"]) << 16
    lower = rom_view.get_uint16(rom_offset["lower"])
    offset = (upper | lower) & 0xFFFFFFFF
    if offset & 0x80000000:
        offset -= 0x100000000
    if lower & 0x8000:
        offset = offset - 0x00010000  # Signed ASM addition workaround.
    return upper, lower, offset


class Strings:
    def __init__(self, rom):
        self._rom = rom
        self._str_fs_instance = None

    def get_rom_offset(self):
        from ..romhandler import romhandler
        rom_view = romhandler.get_data_view()
        patch_offsets = self.get_patch_offsets()
        if not patch_offsets:
            return None
        rom_offset = patch_offsets[0]
        if not rom_offset:
            return None
        upper, lower, offset = _rom_offset_from_patch(rom_view, rom_offset)
        log("Strings.getROMOffset -> %s" % hexstr(offset))

        if is_debug():
            # Assert that the rest of the patch offsets are valid.
            for i in range(1, len(patch_offsets)):
                another_upper = rom_view.get_uint16(patch_offsets[i]["upper"]) << 16
                another_lower = rom_view.get_uint16(patch_offsets[i]["lower"])
                if another_upper != upper or another_lower != lower:
                    raise RuntimeError("Strings.getROMOffset patch offset %d seems wrong" % i)

        return offset

    def set_rom_offset(self, new_offset, buffer):
        rom_view = DataView(buffer)
        patch_offsets = self.get_patch_offsets()
        upper = (new_offset & 0xFFFF0000) >> 16
        lower = new_offset & 0x0000FFFF
        if lower & 0x8000:
            upper += 1  # Adjust for signed addition in ASM.
        for patch_offset in patch_offsets:
            rom_view.set_uint16(patch_offset["upper"], upper)
            rom_view.set_uint16(patch_offset["lower"], lower)
        log("Strings.setROMOffset -> %s" % hexstr(((upper << 16) | lower) & 0xFFFFFFFF))

    def get_patch_offsets(self):
        from ..romhandler import romhandler
        return _string_offsets.get(romhandler.get_rom_game())

    def extract(self):
        from ..romhandler import romhandler
        rom_offset = self.get_rom_offset()
        if rom_offset is None:
            return None
        view = romhandler.get_data_view(rom_offset)
        self._str_fs_instance = StringTable(view)
        return self._str_fs_instance

    extract_async = extract

    def pack(self, buffer, offset=0):
        return self._str_fs_instance.pack(buffer, offset)

    def read(self, index, raw=False):
        return self._str_fs_instance.read(index, raw)

    # Writes a pre-made buffer for now.
    def write(self, index, content):
        self._str_fs_instance.write(index, content)

    def clear(self):
        self._str_fs_instance = None

    def get_string_count(self):
        return self._str_fs_instance.get_string_count()

    # Gets the required byte length of the string section of the ROM.
    def get_byte_length(self):
        return self._str_fs_instance.get_byte_length()


def str_to_bytes(str):
    """Encode text with the game's character map (longest match first)."""
    map = _get_character_map()
    # Work in UTF-16 code units, as JavaScript strings do.
    if any(ord(c) > 0xFFFF for c in str):
        units = str.encode("utf-16-be", "surrogatepass")
        str = "".join(chr((units[i] << 8) | units[i + 1]) for i in range(0, len(units), 2))
    # JavaScript visits integer keys in ascending order.
    entries = sorted(((int(k), v) for k, v in map.items()), key=lambda kv: kv[0])
    result = []
    cur_idx = 0
    length = len(str)
    while cur_idx < length:
        last_match_len = 0
        last_match = None
        for byte, chars in entries:
            if str[cur_idx:cur_idx + len(chars)] == chars:
                if len(chars) > last_match_len:
                    last_match_len = len(chars)
                    last_match = byte

        if last_match_len == 0:
            last_match_len = 1
            last_match = ord(str[cur_idx])

        result.append(last_match)
        cur_idx += last_match_len

    return result

