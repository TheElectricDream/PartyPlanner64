"""The overlays ("scenes") of the game (port of fs/scenes.ts).

ISceneInfo is a dict: rom_start, rom_end, ram_start, code_start, code_end,
rodata_start, rodata_end, bss_start, bss_end.
"""

import struct

from ..utils.arrays import copy_range
from ..utils.dataview import DataView
from ..utils.debug import hexstr, log

SIZEOF_SCENE_TABLE_ENTRY = 9 * 4

_TABLE_END = 0x44200000
_TABLE_END_BYTES = b"\x44\x20\x00\x00"

_SCENE_INFO_KEYS = ("rom_start", "rom_end", "ram_start", "code_start", "code_end",
                    "rodata_start", "rodata_end", "bss_start", "bss_end")
_ENTRY = struct.Struct(">9I")


class Scenes:
    """Handles the overlays used in the game."""

    def __init__(self, rom):
        self._rom = rom
        self._overlay_table_rom_offset = None
        self._overlays = []
        self._scene_info = []

    def count(self):
        return len(self._scene_info)

    def get_info(self, index):
        if 0 <= index < len(self._scene_info):
            return self._scene_info[index]
        return None

    def get_data_view(self, index):
        buffer = self._overlays[index] if 0 <= index < len(self._overlays) else None
        if buffer is None:
            if not self._overlays:
                raise RuntimeError("Overlay table was not parsed")
            raise RuntimeError("Index %s was not within the overlay table (0 - %d)"
                               % (index, len(self._overlays) - 1))
        return DataView(self._overlays[index])

    def get_code_data_view(self, index):
        info = self._scene_info[index]
        start_addr = info["code_start"] & 0x7FFFFFFF
        end_addr = info["code_end"] & 0x7FFFFFFF
        return DataView(self._overlays[index], 0, end_addr - start_addr)

    def get_ro_data_view(self, index):
        info = self._scene_info[index]
        start_addr = info["rodata_start"] & 0x7FFFFFFF
        end_addr = info["rodata_end"] & 0x7FFFFFFF
        ram_start = info["ram_start"] & 0x7FFFFFFF
        return DataView(self._overlays[index], start_addr - ram_start, end_addr - start_addr)

    def get_byte_length(self):
        return sum(info["rom_end"] - info["rom_start"] for info in self._scene_info)

    def extract(self):
        self._overlays = []
        self._scene_info = []

        scene_table_offset = self._overlay_table_rom_offset = self.find_overlay_table_offset()
        if not scene_table_offset:
            log("Overlay table not found in current ROM")
            return
        log("Scene table found at ROM offset %s" % hexstr(scene_table_offset))

        rom_buffer = self._rom.get_buffer()
        rom_view = self._rom.get_data_view()
        cur_offset = scene_table_offset
        while rom_view.get_uint32(cur_offset) != _TABLE_END:
            info = read_overlay_struct(rom_view, cur_offset)
            self._scene_info.append(info)
            self._overlays.append(bytearray(rom_buffer[info["rom_start"]:info["rom_end"]]))
            cur_offset += SIZEOF_SCENE_TABLE_ENTRY

    extract_async = extract

    def pack(self, buffer, offset=0):
        scene_table_offset = self._overlay_table_rom_offset
        if not scene_table_offset:
            raise RuntimeError("Overlay table ROM offset wasn't determined")

        rom_view = DataView(buffer)
        cur_offset = scene_table_offset
        i = 0
        while rom_view.get_uint32(cur_offset) != _TABLE_END:
            # Write all values, some may not have changed.
            info = self._scene_info[i]
            _ENTRY.pack_into(buffer, cur_offset, *[info[k] & 0xFFFFFFFF for k in _SCENE_INFO_KEYS])

            ovl_buffer = self._overlays[i]
            copy_range(buffer, ovl_buffer, info["rom_start"], 0, len(ovl_buffer))

            cur_offset += SIZEOF_SCENE_TABLE_ENTRY
            i += 1

    def replace(self, index, buffer, new_info_values=None):
        if len(buffer) % 16:
            raise ValueError("Cannot have overlay byte length that is not divisible by 16")

        self._overlays[index] = buffer

        info = self._scene_info[index]
        old_size = info["rom_end"] - info["rom_start"]
        diff = len(buffer) - old_size
        info["rom_end"] = info["rom_start"] + len(buffer)

        if new_info_values:
            for value_name, new_value in new_info_values.items():
                if new_value:
                    info[value_name] = new_value

        for other_info in self._scene_info[index + 1:]:
            if info["rom_start"] < other_info["rom_start"]:
                other_info["rom_start"] += diff
                other_info["rom_end"] += diff

        log("Replaced overlay %s with new buffer of length %d" % (hexstr(index), len(buffer)),
            new_info_values)

    def find_overlay_table_offset(self):
        rom_view = self._rom.get_data_view()
        buf = rom_view.buffer
        base = rom_view.byte_offset
        end = base + rom_view.byte_length
        # Look for the value that always seems to follow the table (at
        # 4-byte aligned offsets).
        pos = buf.find(_TABLE_END_BYTES, base, end)
        while pos >= 0:
            i = pos - base
            if i % 4 == 0:
                # See if the data before the value looks like an overlay table.
                table_entries = 0
                current_offset = i - SIZEOF_SCENE_TABLE_ENTRY
                while looks_like_overlay_table_entry(rom_view, current_offset):
                    table_entries += 1
                    current_offset -= SIZEOF_SCENE_TABLE_ENTRY
                if table_entries > 60:
                    return current_offset + SIZEOF_SCENE_TABLE_ENTRY
                pos = buf.find(_TABLE_END_BYTES, pos + 4, end)
            else:
                pos = buf.find(_TABLE_END_BYTES, pos + 1, end)
        return None

    # Private in the TypeScript, but kept reachable by its name.
    _find_overlay_table_offset = find_overlay_table_offset


def read_overlay_struct(rom_view, offset):
    values = _ENTRY.unpack_from(rom_view.buffer, rom_view.byte_offset + offset) \
        if offset >= 0 and offset + SIZEOF_SCENE_TABLE_ENTRY <= rom_view.byte_length \
        else [rom_view.get_uint32(offset + 4 * k) for k in range(9)]
    return dict(zip(_SCENE_INFO_KEYS, values))


def looks_like_overlay_table_entry(rom_view, offset):
    if offset < 0:
        return False
    info = read_overlay_struct(rom_view, offset)
    return (not looks_like_ram_pointer(info["rom_start"])
            and not looks_like_ram_pointer(info["rom_end"])
            and looks_like_ram_pointer(info["ram_start"])
            and looks_like_ram_pointer(info["code_start"])
            and looks_like_ram_pointer(info["code_end"])
            and looks_like_ram_pointer(info["rodata_start"])
            and looks_like_ram_pointer(info["rodata_end"])
            and looks_like_ram_pointer(info["bss_start"])
            and looks_like_ram_pointer(info["bss_end"])
            and info["rom_start"] <= info["rom_end"]
            and info["ram_start"] == info["code_start"]
            and info["code_start"] <= info["code_end"]
            and info["rodata_start"] <= info["rodata_end"]
            and info["bss_start"] <= info["bss_end"])


def looks_like_ram_pointer(value):
    return (value & 0x80000000) == 0x80000000
