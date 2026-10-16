"""A fake ROM for the ROM pages' routes (audio, models, sprites, strings, patches, debug).

There is no Mario Party ROM in the repository: `fake_rom` puts a stand-in romhandler
(partyplanner64.lib.romhandler.romhandler) behind the live server of tests/server/conftest.py.
Its file systems hold synthetic data: image packs made with ImgPack.to_pack, the FORM and
MTNX files of the model tests, a few strings, songs, sounds and overlays.
"""

import json
import struct
from pathlib import Path

import pytest

from partyplanner64.lib.utils.dataview import DataView
from partyplanner64.lib.utils.img.img_pack import to_pack

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_MODELS = json.loads((FIXTURES / "models" / "models_ref.json").read_text())
FORM_BYTES = bytes.fromhex(_MODELS["forms"]["skeleton"]["input"])
MTNX_BYTES = bytes.fromhex(_MODELS["mtnx"]["input"])

GAMES = {1: "CLBE", 2: "NMWE", 3: "NMVE"}


def rgba(w, h, seed=0):
    return bytearray(((x * 7 + y * 13 + seed) % 256) for y in range(h) for x in range(w) for _ in range(4))


def img_pack(w, h, seed=0):
    return bytes(to_pack([{"src": rgba(w, h, seed), "width": w, "height": h, "bpp": 32}], 32, 0))


class FakeMainFS:
    """dir 0: junk; dir 1: an image pack, a FORM, an MTNX; dir 2: a FORM, an image pack."""

    def __init__(self):
        self.files = {(0, 0): bytes(32),
                      (1, 0): img_pack(8, 4, 1), (1, 1): FORM_BYTES, (1, 2): MTNX_BYTES,
                      (2, 0): FORM_BYTES, (2, 1): img_pack(4, 4, 2)}
        self.writes = []

    def get_directory_count(self):
        return 3

    def get_file_count(self, d):
        return len([k for k in self.files if k[0] == d])

    def get(self, d, f):
        return self.files[(d, f)]

    def write(self, d, f, content):
        self.files[(d, f)] = bytes(content)
        self.writes.append((d, f))

    def get_rom_offset(self):
        return 0x10000

    def get_byte_length(self, write_decompressed=False):
        return 0x1000

    def get_compressed_size(self, d, f):
        return 0x100

    def get_file_header_size(self, d, f):
        return 12


class FakeStrings:
    def __init__(self, texts):
        self.strs = [t.encode("latin-1") + b"\x00" for t in texts]

    def get_string_count(self):
        return len(self.strs)

    def read(self, i, raw=False):
        if i >= len(self.strs):
            raise ValueError("Requesting non-existent string entry")
        return self.strs[i] if raw else self.strs[i].rstrip(b"\x00").decode("latin-1")

    def write(self, i, content):
        self.strs[i] = bytes(content)


class FakeStrings3:
    def __init__(self):
        self.tables = {"en": [FakeStrings(["Hello", "A Star"]), FakeStrings(["Coins"])],
                       "de": [FakeStrings(["Hallo"])]}

    def get_locales(self, game):
        return list(self.tables)

    def get_directory_count(self, locale):
        return len(self.tables[locale])

    def get_string_count(self, locale, d):
        return self.tables[locale][d].get_string_count()

    def read(self, locale, d, i, raw=False):
        return self.tables[locale][d].read(i, raw)

    def write(self, locale, d, i, content):
        self.tables[locale][d].write(i, content)


class FakeSeqTable:
    def __init__(self):
        self.midis = [{"buffer": bytearray(b"game midi %d" % i), "soundbank_index": 0}
                      for i in range(3)]
        self.soundbanks = type("B1", (), {"banks": [object(), object()]})()


class FakeSound:
    sample_rate = 22050


class FakeSoundTable:
    tbl = b""

    def __init__(self):
        self.sounds = [FakeSound(), FakeSound()]


class FakeAudio:
    def __init__(self):
        self.seq = [FakeSeqTable()]
        self.snd = [FakeSoundTable()]

    def get_sequence_table_count(self):
        return 1

    def get_sequence_table(self, i):
        return self.seq[i]

    def get_sound_table_count(self):
        return 1

    def get_sound_table(self, i):
        return self.snd[i]


# ADDIU SP SP -0x18; SW RA 0x10(SP); JR RA; NOP
CODE = struct.pack(">4I", 0x27BDFFE8, 0xAFBF0010, 0x03E00008, 0)
RODATA = struct.pack(">4I", 1, 2, 3, 4)


class FakeScenes:
    def __init__(self):
        ram = 0x80100000
        self.infos = [{"rom_start": 0x200000 + i * 0x1000, "rom_end": 0x200000 + i * 0x1000 + 0x20,
                       "ram_start": ram, "code_start": ram, "code_end": ram + 0x10,
                       "rodata_start": ram + 0x10, "rodata_end": ram + 0x20,
                       "bss_start": ram + 0x20, "bss_end": ram + 0x28} for i in range(2)]
        self.data = [bytearray(CODE + RODATA) for _ in range(2)]
        self.replaced = None

    def count(self):
        return len(self.infos)

    def get_info(self, i):
        return self.infos[i] if 0 <= i < len(self.infos) else None

    def get_data_view(self, i):
        return DataView(self.data[i])

    def get_code_data_view(self, i):
        return DataView(self.data[i], 0, 0x10)

    def get_ro_data_view(self, i):
        return DataView(self.data[i], 0x10, 0x10)

    def replace(self, i, buffer, values):
        self.data[i] = bytearray(buffer)
        self.infos[i].update(values)
        self.replaced = (i, values)


class FakeROM:
    def __init__(self):
        self.mainfs = FakeMainFS()
        self.strings = FakeStrings(["Hello <RED>World", "Get a Star!", "Coins"])
        self.strings3 = FakeStrings3()
        self.audio = FakeAudio()
        self.scenes = FakeScenes()

    def get_main_fs(self):
        return self.mainfs

    def get_strings(self):
        return self.strings

    def get_strings3(self):
        return self.strings3

    def get_audio(self):
        return self.audio

    def get_scenes(self):
        return self.scenes


class FakeRomHandler:
    def __init__(self, version=1):
        self.version = version
        self.rom = FakeROM()

    def get_rom(self):
        return self.rom

    def get_rom_game(self):
        return GAMES[self.version] if self.rom else None

    def get_game_version(self):
        return self.version if self.rom else None

    def rom_supported(self):
        return True

    def rom_is_loaded(self):
        return self.rom is not None

    def get_data_view(self, start=0, end=0):
        return DataView(bytearray(CODE * 16))

    def clear(self):
        self.rom = None


@pytest.fixture
def fake_rom(monkeypatch):
    """Returns a function (version=1) that opens a fake ROM; gives the FakeRomHandler."""
    import partyplanner64.lib.romhandler as romhandler_module

    def open_rom(version=1):
        handler = FakeRomHandler(version)
        monkeypatch.setattr(romhandler_module, "romhandler", handler)
        return handler
    return open_rom
