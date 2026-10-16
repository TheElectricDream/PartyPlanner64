from partyplanner64.lib.fs.mainfs import MainFS, _get_file_header_size
from partyplanner64.lib.romhandler import ROM
from partyplanner64.lib.utils.compression import compress
from partyplanner64.lib.utils.dataview import DataView

import pytest


def _rom_with_mainfs(dirs, game=b"NMVE", fs_offset=0x40000):
    """A ROM-like buffer holding a MainFS made of dirs: [[(type, data)]]."""
    rom = ROM(bytearray(0x40))
    rom._rom[0x3B:0x3F] = game
    mainfs = MainFS(rom)
    mainfs._mainfs_cache = [
        [{"compression_type": t, "decompressed_size": len(d), "decompressed": bytearray(d),
          "compressed": compress(t, bytearray(d))} for t, d in files]
        for files in dirs]
    size = mainfs.get_byte_length(False)
    buf = bytearray(fs_offset + size)
    buf[0x3B:0x3F] = game
    end = mainfs.pack(buf, False, fs_offset)
    assert end == size
    rom2 = ROM(buf)
    MainFS(rom2).set_rom_offset(fs_offset, buf)
    return rom2


def test_header_sizes():
    assert [_get_file_header_size(t) for t in range(6)] == [8, 8, 12, 12, 12, 8]
    with pytest.raises(ValueError):
        _get_file_header_size(6)


def test_pack_and_extract():
    dirs = [[(0, b"plain"), (1, b"type one data" * 3), (2, bytes(range(64)))],
            [(3, bytes(32)), (4, bytes(range(32, 96)))],
            []]
    rom = _rom_with_mainfs(dirs, fs_offset=0x48010)  # lower half >= 0x8000: signed fix-up
    mainfs = MainFS(rom)
    assert mainfs.get_rom_offset() == 0x48010
    assert mainfs.get_directory_count() == 3
    assert [mainfs.get_file_count(d) for d in range(3)] == [3, 2, 0]
    mainfs.extract()
    for d, files in enumerate(dirs):
        for f, (t, data) in enumerate(files):
            assert bytes(mainfs.get(d, f)) == data
            assert mainfs.get_file_header_size(d, f) == _get_file_header_size(t)
            assert mainfs.get_compressed_size(d, f) == len(compress(t, bytearray(data)))
    assert mainfs.get_file_count(2) == 0


def test_write_semantics():
    rom = _rom_with_mainfs([[(1, b"abcdefgh" * 4), (0, b"xyz")]])
    mainfs = MainFS(rom)
    mainfs.extract()
    before = mainfs.get_byte_length(False)
    # Equal content: nothing changes (the compressed data is kept).
    mainfs.write(0, 0, bytearray(b"abcdefgh" * 4))
    assert mainfs._mainfs_cache[0][0]["compression_type"] == 1
    assert mainfs.get_byte_length(False) == before
    # New content drops the compression.
    mainfs.write(0, 0, b"new")
    entry = mainfs._mainfs_cache[0][0]
    assert entry["compression_type"] == 0 and "compressed" not in entry and "decompressed_size" not in entry
    # Writing past the end leaves holes.
    mainfs.write(0, 4, b"far")
    assert mainfs.get_file_count(0) == 5
    assert not mainfs.has(0, 2) and mainfs.has(0, 4) and not mainfs.has(0, 9)
    assert mainfs.get_compressed_size(0, 3) == 0 and mainfs.get_file_header_size(0, 3) == 8
    size = mainfs.get_byte_length(False)
    buf = bytearray(size)
    assert mainfs.pack(buf, False) == size
    view = DataView(buf)
    dir_offset = view.get_uint32(4)
    hole = dir_offset + view.get_uint32(dir_offset + 4 + 4 * 2)
    assert buf[hole:hole + 8] == bytes(8)
