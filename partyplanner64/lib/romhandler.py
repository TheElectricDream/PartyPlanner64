"""The loaded ROM and the romhandler singleton (port of romhandler.ts)."""

import array

from .types import Game
from .utils.arrays import copy_range
from .utils.cic import fix_checksum
from .utils.dataview import DataView
from .utils.debug import log
from .utils.number import make_divisible_by


class ROM:
    """Represents a loaded Mario Party ROM in memory.

    The buffer is a bytearray (byte-swapped in place to big-endian when the
    file was a .v64 or .n64 dump).
    """

    def __init__(self, rom):
        if not isinstance(rom, bytearray):
            rom = bytearray(rom)
        self._rom = rom

        self._scenes = None
        self._mainfs = None
        self._hvqfs = None
        self._audio = None
        self._strings = None
        self._strings3 = None
        self._animation_fs = None

        self._game_id = None
        self._game_version = None

        self.byte_swap_if_needed()

    def get_buffer(self):
        return self._rom

    def set_buffer(self, rom):
        self._rom = rom

    def get_data_view(self, starting_offset=0, end_offset=0):
        if self._rom is None:
            raise RuntimeError("ROM not loaded, cannot get DataView.")
        if end_offset:
            return DataView(self._rom, starting_offset, end_offset - starting_offset)
        return DataView(self._rom, starting_offset)

    def get_game(self):
        """Return the game ID (a Game value such as "NMVE"), or None."""
        if self._game_id:
            return self._game_id

        if len(self._rom) < 0x40:
            return None

        self._game_id = "".join(chr(b) for b in self._rom[0x3B:0x3F])
        return self._game_id

    def get_game_version(self):
        if self._game_version is not None:
            return self._game_version

        game_id = self.get_game()
        if not game_id:
            return None

        if game_id in (Game.MP1_USA, Game.MP1_JPN, Game.MP1_PAL):
            self._game_version = 1
            return 1
        if game_id in (Game.MP2_USA, Game.MP2_JPN):
            self._game_version = 2
            return 2
        if game_id in (Game.MP3_USA, Game.MP3_JPN):
            self._game_version = 3
            return 3

        return None

    def rom_recognized(self):
        return self.get_game_version() is not None

    def rom_supported(self):
        return self.get_game() in (Game.MP1_USA, Game.MP2_USA, Game.MP3_USA)

    def get_scenes(self):
        if not self._scenes:
            raise RuntimeError("ROM was not loaded")
        return self._scenes

    def get_main_fs(self):
        if not self._mainfs:
            raise RuntimeError("ROM was not loaded")
        return self._mainfs

    def get_hvqfs(self):
        if not self._hvqfs:
            raise RuntimeError("ROM was not loaded")
        return self._hvqfs

    def get_audio(self):
        if not self._audio:
            raise RuntimeError("ROM was not loaded")
        return self._audio

    def get_strings(self):
        if not self._strings:
            raise RuntimeError("ROM was not loaded")
        return self._strings

    def get_strings3(self):
        if not self._strings3:
            raise RuntimeError("ROM was not loaded")
        return self._strings3

    def get_animation_fs(self):
        if not self._animation_fs:
            raise RuntimeError("ROM was not loaded, or doesn't have animations")
        return self._animation_fs

    def load(self):
        """Extract every file system of the ROM (loadAsync)."""
        from .fs.animationfs import Animationfs
        from .fs.audio import Audio
        from .fs.hvqfs import HVQFS
        from .fs.mainfs import MainFS
        from .fs.scenes import Scenes
        from .fs.strings import Strings
        from .fs.strings3 import Strings3

        game_version = self.get_game_version()

        self._scenes = Scenes(self)
        self._scenes.extract()
        self._mainfs = MainFS(self)
        self._mainfs.extract()
        if game_version == 3:
            self._strings3 = Strings3(self)
            self._strings3.extract()
        else:
            self._strings = Strings(self)
            self._strings.extract()
        self._hvqfs = HVQFS(self)
        self._hvqfs.extract()
        self._audio = Audio(self)
        self._audio.extract()
        if game_version == 2:
            self._animation_fs = Animationfs(self)
            self._animation_fs.extract()

        # Now that we've extracted, shrink _rom to just be the initial part of the ROM.
        ovl_start = self._scenes.get_info(0)
        self.set_buffer(bytearray(self.get_buffer()[:ovl_start["rom_start"]]))
        return True

    def byte_swap_if_needed(self):
        rom = self._rom
        if rom is None or len(rom) < 4:
            return
        magic = int.from_bytes(rom[0:4], "big")
        if magic == 0x80371240:
            return  # Normal, big endian ROM.

        log("Byteswapping ROM...")
        even_len = len(rom) - (len(rom) % 2)
        four_len = len(rom) - (len(rom) % 4)
        if magic == 0x37804012:
            # BADC, .v64 format
            _swap(rom, even_len, "H")
        elif magic == 0x40123780:
            # DCBA, little endian
            _swap(rom, four_len, "I")
        elif magic == 0x12408037:
            # CDAB, wordswapped
            view = memoryview(rom)[:four_len]
            halves = bytes(view)
            view[0::4] = halves[2::4]
            view[1::4] = halves[3::4]
            view[2::4] = halves[0::4]
            view[3::4] = halves[1::4]
            view.release()


def _swap(buffer, length, typecode):
    """Reverse the bytes of each 2- or 4-byte unit of buffer[:length], in place."""
    arr = array.array(typecode)
    arr.frombytes(bytes(buffer[:length]))
    arr.byteswap()
    buffer[:length] = arr.tobytes()


class RomHandler:
    """The ROM Handler handles the ROM... it holds the ROM buffer reference and
    orchestrates ROM loading and saving via adapter code."""

    def __init__(self):
        self._rom = None

    def get_rom(self):
        return self._rom

    def get_rom_game(self):
        return self._rom.get_game() if self._rom else None

    def get_rom_buffer(self):
        return self._rom.get_buffer() if self._rom else None

    def clear(self):
        self._rom = None

    def set_rom_buffer(self, buffer, skip_supported_check=False, on_error=None):
        """Load a ROM file's bytes. Returns True when the ROM was loaded.

        on_error(message) is called (and False returned) when the ROM is not
        recognized or not supported.
        """
        if on_error is None:
            def on_error(msg):
                pass

        if buffer is None:
            self.clear()
            return False

        rom = self._rom = ROM(buffer)

        if not rom.rom_recognized():
            on_error("File is not recognized as any valid ROM.")
            self.clear()
            return False

        if not skip_supported_check and not rom.rom_supported():
            on_error("This ROM is not supported right now.")
            self.clear()
            return False

        from .patches.gameshark.cheats import reset_cheats
        reset_cheats()

        return rom.load()

    def save_rom(self, write_decompressed):
        """Return a new bytearray of the whole ROM with every change written."""
        rom = self._rom
        if not rom:
            raise RuntimeError("Cannot save ROM, buffer was not present")

        from .adapter.adapters import get_rom_adapter
        from .patches.gameshark.hook import apply_hook

        game_version = self.get_game_version()

        initial_len = len(rom.get_buffer())

        # Grab all the sizes of the different sections.
        scene_len = make_divisible_by(rom.get_scenes().get_byte_length(), 16)
        main_len = make_divisible_by(rom.get_main_fs().get_byte_length(write_decompressed), 16)
        if game_version == 3:
            strs_len = make_divisible_by(rom.get_strings3().get_byte_length(), 16)
        else:
            strs_len = make_divisible_by(rom.get_strings().get_byte_length(), 16)
        hvq_len = make_divisible_by(rom.get_hvqfs().get_byte_length(), 16)
        audio_len = make_divisible_by(rom.get_audio().get_byte_length(), 16)
        animation_len = 0
        if game_version == 2:
            animation_len = make_divisible_by(rom.get_animation_fs().get_byte_length(), 16)

        # Seems to crash unless HVQ is aligned so that the +1 ADDIU trick is not needed. Just fudge strsLen to push it up.
        while (initial_len + scene_len + main_len + strs_len) & 0x8000:
            strs_len += 0x1000

        new_rom_buffer = bytearray(
            initial_len + scene_len + main_len + strs_len + hvq_len + animation_len + audio_len)

        copy_range(new_rom_buffer, rom.get_buffer(), 0, 0, initial_len)

        apply_hook(new_rom_buffer)  # Before main fs is packed

        mainfs = rom.get_main_fs()
        mainfs.pack(new_rom_buffer, write_decompressed, initial_len + scene_len)
        mainfs.set_rom_offset(initial_len + scene_len, new_rom_buffer)

        if game_version == 3:
            strings3 = rom.get_strings3()
            strings3.pack(new_rom_buffer, initial_len + scene_len + main_len)
            strings3.set_rom_offset(initial_len + scene_len + main_len, new_rom_buffer)
        else:
            strings = rom.get_strings()
            strings.pack(new_rom_buffer, initial_len + scene_len + main_len)
            strings.set_rom_offset(initial_len + scene_len + main_len, new_rom_buffer)

        hvqfs = rom.get_hvqfs()
        hvqfs.pack(new_rom_buffer, initial_len + scene_len + main_len + strs_len)
        hvqfs.set_rom_offset(initial_len + main_len + scene_len + strs_len, new_rom_buffer)

        if game_version == 2:
            animationfs = rom.get_animation_fs()
            animationfs.pack(new_rom_buffer, initial_len + scene_len + main_len + strs_len + hvq_len)
            animationfs.set_rom_offset(initial_len + scene_len + main_len + strs_len + hvq_len,
                                       new_rom_buffer)

        audio = rom.get_audio()
        audio.pack(new_rom_buffer,
                   initial_len + scene_len + main_len + strs_len + hvq_len + animation_len)
        audio.set_rom_offset(initial_len + scene_len + main_len + strs_len + hvq_len + animation_len,
                             new_rom_buffer)

        # Do this last, so that any patches made to scenes just prior take effect.
        rom.get_scenes().pack(new_rom_buffer, initial_len)

        adapter = get_rom_adapter({})
        on_after_save = getattr(adapter, "on_after_save", None)
        if on_after_save:
            on_after_save(DataView(new_rom_buffer))

        fix_checksum(new_rom_buffer)

        rom.set_buffer(bytearray(new_rom_buffer[:initial_len]))

        return new_rom_buffer

    def rom_is_loaded(self):
        return bool(self._rom)

    def get_data_view(self, starting_offset=0, end_offset=0):
        if not self._rom:
            raise RuntimeError("ROM not loaded, cannot get DataView.")
        return self._rom.get_data_view(starting_offset, end_offset)

    def get_game_version(self):
        return self._rom.get_game_version() if self._rom else None

    def rom_recognized(self):
        return self._rom.rom_recognized() if self._rom else False

    def rom_supported(self):
        return self._rom.rom_supported() if self._rom else False


romhandler = RomHandler()

