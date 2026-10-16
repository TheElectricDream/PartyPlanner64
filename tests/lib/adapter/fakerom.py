"""A fake ROM for driving the adapters without a Mario Party ROM.

Mirrors the fakes in tests/fixtures/adapter/gen_overwrite.ts: every write the
adapter makes is recorded in `log`, in order.
"""

import hashlib
import json

from partyplanner64.lib.utils.dataview import DataView

GAME_IDS = {1: "CLBE", 2: "NMWE", 3: "NMVE"}

# What the fake string tables read (the string index is appended).
STRS = {
    "CLBE": "\u3014<GREEN>Fake Board<DEFAULT>\nFirst line\nSecond line\n<BLUE>Map Difficulty  \u3009\u3009\u3009<DEFAULT>",
    "NMWE": "\u3014<BLUE>Fake Board\u0019<PURPLE>\t\tDifficulty\u0019 : \u3013\u3013\nFirst line\nSecond line",
    "NMVE": "\u3014<GREEN>xFake Board{5}\nFirst line\nSecond \u3013 line",
}


def blob(buf):
    """How the fixtures record a buffer: hex when small, else length and SHA-1."""
    data = bytes(buf)
    if len(data) <= 0x1000:
        return data.hex()
    return "len=%d sha1=%s" % (len(data), hashlib.sha1(data).hexdigest())


def runs(buf):
    """The non-zero runs of a buffer, as [offset, hex] (zero gaps under 4 bytes kept)."""
    u8 = bytes(buf)
    n = len(u8)
    out = []
    i = 0
    while i < n:
        if u8[i] == 0:
            i += 1
            continue
        j = i
        while j < n and (u8[j] != 0 or (j + 1 < n and u8[j + 1] != 0)
                         or (j + 2 < n and u8[j + 2] != 0) or (j + 3 < n and u8[j + 3] != 0)):
            j += 1
        out.append([i, u8[i:j].hex()])
        i = j
    return out


class FakeMainFS:
    def __init__(self, log):
        self.files = {}
        self.log = log

    def get(self, d, f):
        key = "%d/%d" % (d, f)
        if key not in self.files:
            self.files[key] = bytearray(0x2000)
        return self.files[key]

    def has(self, d, f):
        return "%d/%d" % (d, f) in self.files

    def write(self, d, f, content):
        self.files["%d/%d" % (d, f)] = content
        self.log.append(["mainfs.write", d, f, blob(content)])


class FakeScenes:
    def __init__(self, log):
        self.bufs = {}
        self.log = log

    def get_info(self, i):
        base = (0x80100000 + i * 0x1000) & 0xFFFFFFFF
        return {
            "rom_start": 0x200000 + i * 0x40000, "rom_end": 0x200000 + i * 0x40000 + 0x30000,
            "ram_start": base, "code_start": base, "code_end": base + 0x20000,
            "rodata_start": base + 0x20000, "rodata_end": base + 0x28000,
            "bss_start": base + 0x28000, "bss_end": base + 0x30000,
        }

    def get_data_view(self, i):
        if i not in self.bufs:
            self.bufs[i] = bytearray(0x30000)
        return DataView(self.bufs[i])

    get_code_data_view = get_data_view

    def replace(self, i, buf, info=None):
        self.log.append(["scenes.replace", i, blob(buf), info])


class FakeHVQFS:
    def __init__(self, log):
        self.log = log
        self.bg = {}

    def read_background(self, dir):
        return dict(self.bg, src="bg%d" % dir)

    def update_metadata(self, dir, values):
        self.log.append(["hvqfs.updateMetadata", dir, json.loads(json.dumps(values))])

    def write_background(self, dir, *args):
        self.log.append(["hvqfs.writeBackground", dir])

    def get_directory_count(self):
        return 100


class FakeStrings:
    def __init__(self, log, game):
        self.log = log
        self.game = game

    def write(self, i, buf):
        self.log.append(["strings.write", i, blob(buf)])

    def read(self, i, raw=False):
        return STRS[self.game] + str(i)


class FakeStrings3:
    def __init__(self, log, game):
        self.log = log
        self.game = game

    def read(self, locale, d, i, raw=False):
        return STRS[self.game] + "%d/%d" % (d, i)

    def write(self, locale, d, i, buf):
        self.log.append(["strings3.write", locale, d, i, blob(buf)])


class FakeAnimationFS:
    def __init__(self, log):
        self.log = log

    def set_set_entry_count(self, s, c):
        self.log.append(["animationfs.setSetEntryCount", s, c])


class FakeSeqTable:
    def __init__(self):
        self.midis = []


class FakeAudio:
    def get_sequence_table(self, index):
        return FakeSeqTable()


class FakeROM:
    def __init__(self, game_version):
        self.log = []
        self.game = GAME_IDS[game_version]
        self.mainfs = FakeMainFS(self.log)
        self.scenes = FakeScenes(self.log)
        self.hvqfs = FakeHVQFS(self.log)
        self.strings = FakeStrings(self.log, self.game)
        self.strings3 = FakeStrings3(self.log, self.game)
        self.animationfs = FakeAnimationFS(self.log)
        self.audio = FakeAudio()
        self.rom_buffer = bytearray(0xD0000)

    def get_game(self):
        return self.game

    def get_main_fs(self):
        return self.mainfs

    def get_scenes(self):
        return self.scenes

    def get_hvqfs(self):
        return self.hvqfs

    def get_strings(self):
        return self.strings

    def get_strings3(self):
        return self.strings3

    def get_animation_fs(self):
        return self.animationfs

    def get_audio(self):
        return self.audio


def install(monkeypatch, game_version):
    """Point the romhandler singleton at a new FakeROM; returns it."""
    from partyplanner64.lib.romhandler import romhandler

    rom = FakeROM(game_version)
    monkeypatch.setattr(romhandler, "get_rom", lambda: rom)
    monkeypatch.setattr(romhandler, "get_rom_game", lambda: rom.game)
    monkeypatch.setattr(romhandler, "get_game_version", lambda: game_version)
    monkeypatch.setattr(romhandler, "get_data_view", lambda *a: DataView(rom.rom_buffer))
    return rom
