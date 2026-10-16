"""The main file system of the game (port of fs/mainfs.ts).

Each read file (IMainFsReadInfo) is a dict: {"compression_type",
"decompressed_size" (optional), "decompressed" (bytearray), "compressed"
(optional bytearray)}.
"""

import time

from ..debug import is_debug
from ..types import Game
from ..utils.arrays import array_buffers_equal, copy_range
from ..utils.compression import decompress
from ..utils.dataview import DataView
from ..utils.debug import hexstr, log
from ..utils.number import make_divisible_by

_main_fs_offsets = {}

_main_fs_offsets[Game.MP1_USA] = [
    # Default 0x0031C7E0
    {"upper": 0x157A6, "lower": 0x157AA},
    {"upper": 0x3C016, "lower": 0x3C01E},
]
_main_fs_offsets[Game.MP1_JPN] = [
    {"upper": 0x156D6, "lower": 0x156DA},
    {"upper": 0x3BF32, "lower": 0x3BF3A},
]
_main_fs_offsets[Game.MP1_PAL] = [
    # Default 0x003373C0
    {"upper": 0x160F6, "lower": 0x160FA},
    {"upper": 0x3D83A, "lower": 0x3D83E},
]
_main_fs_offsets[Game.MP2_USA] = [
    # Default 0x0041DD30
    {"upper": 0x416E6, "lower": 0x416EE},
]
_main_fs_offsets[Game.MP2_JPN] = [
    # Default 0x00417540
    {"upper": 0x40D8A, "lower": 0x40D92},
]
_main_fs_offsets[Game.MP3_USA] = [{"upper": 0x3619E, "lower": 0x361A6}]
_main_fs_offsets[Game.MP3_JPN] = [
    # Default 0x005517F0
    {"upper": 0x3618A, "lower": 0x36192},
]


def _get_file_header_size(compression_type):
    if compression_type in (0, 1, 5):
        return 8  # Don't duplicate decompressed size.
    if compression_type in (2, 3, 4):  # 3 never occurs
        return 12
    raise ValueError("_getFileHeaderSize(%s) not handled" % compression_type)


def _js_or(a, b):
    """a || b for a size that may be missing or zero."""
    return a if a else b


class MainFS:
    def __init__(self, rom):
        self._rom = rom
        self._mainfs_cache = None

    def get_rom_offset(self):
        rom_view = self._rom.get_data_view()
        patch_offsets = self.get_patch_offsets()
        if not patch_offsets:
            return None
        rom_offset = patch_offsets[0]
        upper = rom_view.get_uint16(rom_offset["upper"]) << 16
        lower = rom_view.get_uint16(rom_offset["lower"])
        offset = _to_int32(upper | lower)
        if lower & 0x8000:
            offset = offset - 0x00010000  # Account for signed addition workaround.
        log("MainFS.getROMOffset -> %s" % hexstr(offset))

        if is_debug():
            # Assert that the rest of the patch offsets are valid.
            for i in range(1, len(patch_offsets)):
                another_upper = rom_view.get_uint16(patch_offsets[i]["upper"]) << 16
                another_lower = rom_view.get_uint16(patch_offsets[i]["lower"])
                if another_upper != upper or another_lower != lower:
                    raise RuntimeError("MainFS.getROMOffset patch offset %d seems wrong" % i)

        return offset

    def set_rom_offset(self, new_offset, buffer):
        from ..utils.mips import get_reg_set_address, get_reg_set_upper_and_lower
        rom_view = DataView(buffer)
        patch_offsets = self.get_patch_offsets()
        upper, lower = get_reg_set_upper_and_lower(new_offset)
        for patch_offset in patch_offsets:
            rom_view.set_uint16(patch_offset["upper"], upper)
            rom_view.set_uint16(patch_offset["lower"], lower)
        log("MainFS.setROMOffset -> %s" % hexstr(get_reg_set_address(upper, lower)))

    def get_patch_offsets(self):
        return _main_fs_offsets.get(self._rom.get_game())

    def get(self, dir, file):
        return self._mainfs_cache[dir][file]["decompressed"]

    def has(self, dir, file):
        files = self._mainfs_cache[dir]
        return 0 <= file < len(files) and bool(files[file])

    def read(self, dir, file, all):
        buffer = self._rom.get_buffer()

        fs_offset = self.get_rom_offset()
        fs_view = DataView(buffer, fs_offset)

        dir_offset = fs_offset + fs_view.get_uint32(4 * (1 + dir))
        dir_view = DataView(buffer, dir_offset)

        file_entry_offset = dir_offset + dir_view.get_uint32(4 * (1 + file))
        file_view = DataView(buffer, file_entry_offset)
        decompressed_size = file_view.get_uint32(0)
        compression_type = file_view.get_uint32(4)
        file_start_offset = file_entry_offset + _get_file_header_size(compression_type)
        file_start_view = DataView(buffer, file_start_offset)

        result = {
            "compression_type": compression_type,
            "decompressed_size": decompressed_size,
            "decompressed": decompress(compression_type, file_start_view, decompressed_size),
        }
        if is_debug():
            # Assert decompressedSize matches
            if decompressed_size != len(result["decompressed"]):
                raise RuntimeError("MainFS Dir: %s, File: %s decompressed size mismatch" % (dir, file))
        if all:
            compressed_size = result["decompressed"].compressed_size
            result["compressed"] = bytearray(
                buffer[file_start_offset:file_start_offset + compressed_size])
        return result

    def write(self, dir, file, content):
        files = self._mainfs_cache[dir]
        while len(files) <= file:
            files.append(None)  # A sparse array in the TypeScript.
        file_data = files[file]
        if not file_data:
            log("Adding new file to MainFS: %s/%s" % (dir, file))
            file_data = files[file] = {"compression_type": 0}
        elif content is not file_data["decompressed"] and \
                array_buffers_equal(content, file_data["decompressed"]):
            return  # Don't bother, because we would just end up losing the compressed data.

        if file_data.get("compressed") is not None:
            file_data.pop("decompressed_size", None)
            file_data.pop("compressed", None)
            file_data["compression_type"] = 0

        file_data["decompressed"] = bytearray(content)

    def extract(self):
        t0 = time.perf_counter() if is_debug() else None

        dir_count = self.get_directory_count()
        self._mainfs_cache = [None] * dir_count
        for d in range(dir_count):
            file_count = self.get_file_count(d)
            self._mainfs_cache[d] = [self.read(d, f, True) for f in range(file_count)]

        if t0 is not None:
            log("MainFS.extract() -> %sms" % ((time.perf_counter() - t0) * 1000))

        return self._mainfs_cache

    extract_async = extract

    def pack(self, buffer, write_decompressed, offset=0):
        view = DataView(buffer, offset)

        dir_count = self.get_directory_count()
        view.set_uint32(0, dir_count)

        cur_dir_index_offset = 4
        cur_dir_write_offset = 4 + dir_count * 4
        for d in range(dir_count):
            view.set_uint32(cur_dir_index_offset, cur_dir_write_offset)
            cur_dir_index_offset += 4
            cur_dir_write_offset = self._write_dir(d, view, cur_dir_write_offset, write_decompressed)
            cur_dir_write_offset = make_divisible_by(cur_dir_write_offset, 2)

        return cur_dir_write_offset

    def _write_dir(self, d, view, offset, write_decompressed):
        file_count = self.get_file_count(d)
        view.set_uint32(offset, file_count)

        cur_file_index_offset = offset + 4
        cur_file_write_offset = offset + 4 + file_count * 4
        for f in range(file_count):
            view.set_uint32(cur_file_index_offset, cur_file_write_offset - offset)
            cur_file_index_offset += 4
            cur_file_write_offset = self._write_file(d, f, view, cur_file_write_offset, write_decompressed)
            cur_file_write_offset = make_divisible_by(cur_file_write_offset, 2)

        return cur_file_write_offset

    def _write_file(self, d, f, view, offset, write_decompressed):
        file_data = self._mainfs_cache[d][f]
        if not file_data:
            view.set_uint32(offset, 0)  # No file, no size
            view.set_uint32(offset + 4, 0)
            file_start_offset = offset + 8
            if _get_file_header_size(0) == 12:
                # Duplicate decompressed size
                view.set_uint32(offset + 8, 0)
                file_start_offset += 4
            return file_start_offset

        size = _js_or(file_data.get("decompressed_size"), len(file_data["decompressed"]))
        view.set_uint32(offset, size)

        compression_type = 0 if write_decompressed else file_data["compression_type"]
        view.set_uint32(offset + 4, compression_type)

        file_start_offset = offset + 8
        if _get_file_header_size(compression_type) == 12:
            # Duplicate decompressed size
            view.set_uint32(offset + 8, size)
            file_start_offset += 4

        if write_decompressed:
            bytes_to_write = file_data["decompressed"]
        else:
            bytes_to_write = file_data.get("compressed")
            if bytes_to_write is None:
                bytes_to_write = file_data["decompressed"]
        copy_range(view, bytes_to_write, file_start_offset, 0, len(bytes_to_write))

        return file_start_offset + len(bytes_to_write)

    def get_directory_count(self):
        if self._mainfs_cache is not None:
            return len(self._mainfs_cache)

        buffer = self._rom.get_buffer()
        fs_view = DataView(buffer, self.get_rom_offset())
        return fs_view.get_uint32(0)

    def get_file_count(self, dir):
        if self._mainfs_cache is not None and 0 <= dir < len(self._mainfs_cache) \
                and self._mainfs_cache[dir] is not None:
            return len(self._mainfs_cache[dir])

        buffer = self._rom.get_buffer()
        fs_offset = self.get_rom_offset()
        fs_view = DataView(buffer, fs_offset)
        dir_offset = fs_offset + fs_view.get_uint32(4 * (1 + dir))
        dir_view = DataView(buffer, dir_offset)
        return dir_view.get_uint32(0)

    def get_byte_length(self, write_decompressed):
        dir_count = len(self._mainfs_cache)

        byte_len = 0
        byte_len += 4  # Count of directories
        byte_len += 4 * dir_count  # Directory offsets

        for d in range(dir_count):
            file_count = len(self._mainfs_cache[d])

            byte_len += 4  # Count of files
            byte_len += 4 * file_count  # File offsets

            for f in range(file_count):
                file_data = self._mainfs_cache[d][f]

                if not file_data:
                    # Happens if we write a new file at a specific place and leave gaps.
                    byte_len += _get_file_header_size(0)
                else:
                    # Decompressed size, compression type, and perhaps duplicated decompressed size.
                    byte_len += _get_file_header_size(
                        0 if write_decompressed else file_data["compression_type"])

                    if file_data.get("compressed") is not None and not write_decompressed:
                        # We never touched it.
                        byte_len += len(file_data["compressed"])
                    else:
                        byte_len += len(file_data["decompressed"])
                    byte_len = make_divisible_by(byte_len, 2)

        return byte_len

    def _cached(self, dir, file):
        files = self._mainfs_cache[dir]
        return files[file] if 0 <= file < len(files) else None

    def get_compressed_size(self, dir, file):
        """Returns the current compressed size of a file."""
        if self._mainfs_cache is not None and self._cached(dir, file):
            if self._cached(dir, file).get("compressed") is not None:
                return len(self._cached(dir, file)["compressed"])
        return 0

    def get_file_header_size(self, dir, file):
        if self._mainfs_cache is not None and self._cached(dir, file):
            if isinstance(self._cached(dir, file).get("compression_type"), int):
                return _get_file_header_size(self._cached(dir, file)["compression_type"])
        return 8


def _to_int32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value
