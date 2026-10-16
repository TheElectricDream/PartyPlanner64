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
        base = 0x80100000
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

    def write_background(self, dir, img_data, width, height, metadata=None):
        self.log.append(["hvqfs.writeBackground", dir, width, height, blob(img_data.data)])

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


def pattern(w, h, seed):
    """A deterministic RGBA32 image (as gen_images.ts makes)."""
    out = bytearray(w * h * 4)
    i = 0
    for y in range(h):
        for x in range(w):
            out[i] = (x * 3 + y + seed) & 0xFF
            out[i + 1] = (x * y + seed * 5) & 0xFF
            out[i + 2] = (x + y * 7) & 0xFF
            out[i + 3] = 255
            i += 4
    return out


def prefill(game_version, adapter, rom):
    """Fill the fake ROM like the stock boards (as gen_load.ts does): a board def for
    every board, and in each board's scene the values the board info points at and
    an event table reached through a call to EventTableHydrate."""
    from partyplanner64.lib.adapter import boarddef
    from partyplanner64.lib.adapter.boardinfo import get_board_infos
    from partyplanner64.lib.mips import parse as parse_inst
    from partyplanner64.lib.symbols.symbols import get_symbol

    game_id = GAME_IDS[game_version]
    loop = {
        "spaces": [{"type": t, "x": 10 * i, "y": 5 * i, "z": i}
                   for i, t in enumerate([0, 1, 2, 1, 1, 2, 1, 1])],
        "links": {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 0},
    }
    jal = parse_inst("JAL %d" % get_symbol(game_id, "EventTableHydrate"))

    def as_list(o):
        return [] if o is None else (o if isinstance(o, list) else [o])

    for j, info in enumerate(get_board_infos(game_id)):
        rom.mainfs.write(adapter.board_def_directory, info["board_def_file"],
                         boarddef.create(loop, [[0, 1, 2, 3, 4, 5, 6, 7]]))
        if not isinstance(info.get("scene_index"), int):
            continue
        v = rom.scenes.get_data_view(info["scene_index"])
        for n, k in enumerate(["koopa_space_inst", "bowser_space_inst", "goomba_space_inst",
                               "boo_space_inst", "toad_space_inst"]):
            if info.get(k):
                v.set_uint16(info[k] + 2, n + 1)
        for off in as_list(info.get("star_space_arr_offset")):
            for i in range(info.get("star_space_count") or 0):
                v.set_uint16(off + 2 * i, (i % 7) + 1)
        for off in as_list(info.get("toad_space_arr_offset")):
            for i in range(info.get("star_space_count") or 0):
                v.set_uint16(off + 2 * i, (i % 5) + 2)
        if info.get("boos_loop_fn_offset"):
            v.set_uint16(info["boos_loop_fn_offset"] + 0x2A, 2)
            v.set_int16(info["boos_readback_fn_offset"] + 0xD2, 0x1000)
            v.set_uint16(0x1000, 5)
            v.set_uint16(0x1002, 6)
        for off in as_list(info.get("bank_arr_offset")):
            for i in range(info.get("bank_count") or 0):
                v.set_uint16(off + 2 * i, 7 + i)
        for off in as_list(info.get("bank_coin_arr_offset")):
            for i in range(info.get("bank_count") or 0):
                v.set_uint16(off + 2 * i, 1 + i)
        for off in as_list(info.get("item_shop_arr_offset")):
            for i in range(info.get("item_shop_count") or 0):
                v.set_uint16(off + 2 * i, 2 + i)
        for off in as_list(info.get("boo_arr_offset")):
            for i in range(info.get("boo_count") or 0):
                v.set_uint16(off + 2 * i, 3 + i)
        if info.get("audio_index_offset"):
            v.set_uint16(info["audio_index_offset"], 0x12 + j)
        v.set_uint32(0x100, 0x3C048010)  # LUI A0, 0x8010
        v.set_uint32(0x104, jal)
        v.set_uint32(0x108, 0x24840800)  # ADDIU A0, A0, 0x800
        v.set_int16(0x800, 1)
        v.set_uint32(0x804, 0x80100900)
        v.set_int16(0x808, -1)
        v.set_uint16(0x900, 1)
        v.set_uint16(0x902, 1)
        v.set_uint32(0x904, 0x80100A00)
    del rom.log[:]
