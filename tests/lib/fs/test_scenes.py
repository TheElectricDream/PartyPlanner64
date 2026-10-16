import struct

import pytest

from partyplanner64.lib.fs.scenes import Scenes
from partyplanner64.lib.romhandler import ROM


def _rom(count, decoy=True):
    buf = bytearray(0x10000)
    pos = 0x200
    if decoy:
        buf[0x101:0x105] = b"\x44\x20\x00\x00"  # unaligned: ignored
        buf[0x104:0x108] = b"\x44\x20\x00\x00"  # aligned but no table before it
    rom_start = 0x8000
    for i in range(count):
        ram = 0x80100000 + i * 0x1000
        struct.pack_into(">9I", buf, pos, rom_start, rom_start + 0x20, ram, ram, ram + 0x10,
                         ram + 0x10, ram + 0x20, ram + 0x20, ram + 0x30)
        buf[rom_start:rom_start + 0x20] = bytes([i]) * 0x20
        rom_start += 0x20
        pos += 36
    buf[pos:pos + 4] = b"\x44\x20\x00\x00"
    return ROM(buf)


def test_find_and_extract():
    rom = _rom(61)
    scenes = Scenes(rom)
    scenes.extract()
    assert scenes.count() == 61
    assert scenes.get_info(3)["rom_start"] == 0x8060
    assert scenes.get_info(61) is None and scenes.get_info(-1) is None
    assert scenes.get_data_view(2).get_uint8(0) == 2
    assert scenes.get_code_data_view(1).byte_length == 0x10
    assert scenes.get_ro_data_view(1).byte_offset == 0x10
    assert scenes.get_byte_length() == 61 * 0x20
    with pytest.raises(RuntimeError):
        scenes.get_data_view(61)


def test_short_table_not_found():
    scenes = Scenes(_rom(60))
    scenes.extract()
    assert scenes.count() == 0
    with pytest.raises(RuntimeError):
        scenes.get_data_view(0)
    with pytest.raises(RuntimeError):
        scenes.pack(bytearray(16))


def test_replace_shifts_following():
    rom = _rom(62)
    scenes = Scenes(rom)
    scenes.extract()
    with pytest.raises(ValueError):
        scenes.replace(1, bytearray(15))
    scenes.replace(1, bytearray(0x40), {"code_end": 0x80101040, "bss_end": 0})
    assert scenes.get_info(1)["rom_end"] == 0x8020 + 0x40
    assert scenes.get_info(1)["code_end"] == 0x80101040
    assert scenes.get_info(1)["bss_end"] == 0x80101030  # 0 is not applied
    assert scenes.get_info(2)["rom_start"] == 0x8040 + 0x20
    out = bytearray(rom.get_buffer()) + bytearray(0x100)
    scenes.pack(out)
    assert struct.unpack_from(">I", out, 0x200 + 36 + 4)[0] == 0x8060
