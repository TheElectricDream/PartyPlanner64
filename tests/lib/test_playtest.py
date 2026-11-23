"""Test play (lib/playtest): the options, and the Mario Party 3 boot patch.

The patch is checked against a small stand-in for the ROM, and against the
real Mario Party 3 (U) ROM when it is in `roms/` (or $PP64_ROMS).
"""

import copy
import glob
import os
import struct

import pytest

from partyplanner64.lib import playtest
from partyplanner64.lib.mips import assemble
from partyplanner64.lib.playtest import PlaytestError, mp3
from partyplanner64.lib.symbols.symbols import get_symbol
from partyplanner64.lib.types import BoardType, Game
from partyplanner64.lib.utils.dataview import DataView

ROM_DIRS = [os.environ.get("PP64_ROMS", ""),
            os.path.join(os.path.dirname(__file__), "..", "..", "roms")]


def _mp3_rom_path():
    for directory in ROM_DIRS:
        if not directory:
            continue
        for path in sorted(glob.glob(os.path.join(directory, "*"))):
            if "party 3" in os.path.basename(path).lower() and "(u" in os.path.basename(path).lower():
                return path
    return None


# Options


def test_default_options():
    options = playtest.normalize_options(3)
    assert options == playtest.default_options(3)
    assert [p["control"] for p in options["players"]] == ["pad1", "cpu", "cpu", "cpu"]
    assert [p["character"] for p in options["players"]] == [0, 1, 2, 3]
    assert options["turn"] == 1 and options["turns"] == 20
    # A new dict each time.
    options["players"][0]["character"] = 7
    assert playtest.default_options(3)["players"][0]["character"] == 0


def test_normalize_options_fills_in_and_checks():
    options = playtest.normalize_options(3, {
        "players": [{"character": 7, "control": "pad2", "items": [1, 4]}, {}, {"difficulty": 3},
                    {"control": "pad2"}],
        "coins": 120, "stars": 2, "turns": 35, "turn": 30})
    assert options["players"][0] == {"character": 7, "control": "pad2", "difficulty": 1,
                                     "items": [1, 4]}
    assert options["players"][1] == playtest.default_options(3)["players"][1]
    assert options["players"][2]["difficulty"] == 3
    assert options["players"][3]["control"] == "pad2"       # controllers can be shared
    assert (options["coins"], options["stars"], options["turns"], options["turn"]) == (120, 2, 35, 30)


@pytest.mark.parametrize("options, message", [
    ({"coins": 1000}, "Coins must be from 0 to 999."),
    ({"coins": -1}, "Coins must be from 0 to 999."),
    ({"coins": "50"}, "Coins must be a whole number."),
    ({"stars": True}, "Stars must be a whole number."),
    ({"turns": 0}, "The number of turns must be from 1 to 50."),
    ({"turns": 10, "turn": 11}, "The game starts on turn 11, after its last turn (10)."),
    ({"players": []}, "There are four players."),
    ({"players": [{}, {}, {}, 5]}, "Player 4 is an object."),
    ({"players": [{"character": 8}, {}, {}, {}]}, "Player 1's character must be from 0 to 7."),
    ({"players": [{}, {"control": "pad5"}, {}, {}]},
     "Player 2's control is one of: pad1, pad2, pad3, pad4, cpu."),
    ({"players": [{"items": [1, 2, 3, 4]}, {}, {}, {}]}, "Player 1's items are a list of at most 3."),
    ({"players": [{"items": [99]}, {}, {}, {}]}, "Player 1's items: there is no item 99."),
    ("coins", "The test options are an object."),
])
def test_normalize_options_errors(options, message):
    with pytest.raises(PlaytestError) as e:
        playtest.normalize_options(3, options)
    assert str(e.value) == message


def test_games_without_test_play():
    assert playtest.unsupported_reason(Game.MP3_USA) is None
    assert playtest.unsupported_reason("NMVE", "NORMAL") is None
    assert "duel" in playtest.unsupported_reason(Game.MP3_USA, BoardType.DUEL)
    for game in (Game.MP1_USA, Game.MP2_USA, Game.MP3_JPN):
        assert "Mario Party 3 (U)" in playtest.unsupported_reason(game)
    assert playtest.describe(1) is None
    with pytest.raises(PlaytestError):
        playtest.normalize_options(2)


def test_describe():
    info = playtest.describe(3)
    assert [c["name"] for c in info["characters"]][:3] == ["Mario", "Luigi", "Peach"]
    assert len(info["characters"]) == 8
    assert {"id": 1, "name": "Skeleton Key"} in info["items"]
    assert info["itemSlots"] == 3
    assert [c["id"] for c in info["controls"]] == ["pad1", "pad2", "pad3", "pad4", "cpu"]
    assert info["defaults"] == playtest.default_options(3)


# Mario Party 3: the structures


def test_mp3_addresses_match_the_symbols():
    game = Game.MP3_USA
    assert get_symbol(game, "LoadOverlay") == mp3.FUNC_CALL_SCENE
    assert get_symbol(game, "InitObjSys") == mp3.FUNC_INIT_OBJECTS
    assert get_symbol(game, "osEepromWrite") == mp3.FUNC_EEPROM_WRITE
    assert get_symbol(game, "osEepromLongWrite") == mp3.FUNC_EEPROM_LONG_WRITE
    assert get_symbol(game, "player_structs") == mp3.ADDR_PLAYERS
    assert get_symbol(game, "total_turns") == mp3.ADDR_SYSTEM + 0x02
    assert get_symbol(game, "current_turn") == mp3.ADDR_SYSTEM + 0x03
    assert get_symbol(game, "current_player_index") == mp3.ADDR_SYSTEM + 0x0F
    assert get_symbol(game, "p2_turn_color_status") == mp3.ADDR_PLAYERS + mp3.SIZEOF_PLAYER + 0x1C
    assert get_symbol(game, "overlay_base") == mp3.OVERLAY_RAM_START


def test_mp3_system_data():
    options = playtest.normalize_options(3, {"turns": 35, "turn": 12})
    data = mp3.system_data(4, options)
    assert len(data) == mp3.SIZEOF_SYSTEM == 0x62
    assert data[0x00] == 1                      # Battle Royal
    assert data[0x01] == 4                      # the board
    assert (data[0x02], data[0x03]) == (35, 12)
    assert sorted(data[0x06:0x0E]) == list(range(8))
    assert data[0x0F] == 0                      # the first player's turn
    assert data[0x11] == 0xFF
    assert data[0x48:0x52] == bytes(10)         # the boards' own state starts clear


def test_mp3_player_data():
    options = playtest.normalize_options(3, {
        "players": [{"character": 5, "control": "pad3", "items": [1]},
                    {"character": 2, "control": "cpu", "difficulty": 2}, {}, {}],
        "coins": 300, "stars": 4})
    human = mp3.player_data(0, 2, options)
    assert len(human) == mp3.SIZEOF_PLAYER == 0x38
    assert human[0x02] == 2 and human[0x03] == 5
    assert human[0x04] & 0x01 == 0
    assert struct.unpack_from(">h", human, 0x0A)[0] == 300
    assert struct.unpack_from(">h", human, 0x2A)[0] == 300
    assert human[0x0E] == 4
    assert human[0x18:0x1B] == bytes([1, 0xFF, 0xFF])
    assert human[0x1D] == 0
    assert human[0x20:0x28] == bytes(8)         # the pointers are the game's to set
    cpu = mp3.player_data(1, 0, options)
    assert cpu[0x01] == 2 and cpu[0x03] == 2
    assert cpu[0x04] & 0x01 == 1
    assert cpu[0x18:0x1B] == b"\xFF\xFF\xFF"
    assert cpu[0x1D] == 1


@pytest.mark.parametrize("controls, ports", [
    (["pad1", "cpu", "cpu", "cpu"], [0, 1, 2, 3]),
    (["cpu", "pad1", "cpu", "pad2"], [2, 0, 3, 1]),
    (["pad1", "pad1", "pad1", "pad1"], [0, 0, 0, 0]),
    (["pad4", "cpu", "pad2", "cpu"], [3, 0, 1, 2]),
    (["cpu", "cpu", "cpu", "cpu"], [0, 1, 2, 3]),
])
def test_mp3_ports(controls, ports):
    assert mp3._ports([{"control": c} for c in controls]) == ports


def test_mp3_save_file_data():
    data = mp3.save_file_data()
    assert len(data) == mp3.SIZEOF_SAVE_FILE == 0xA4
    # Flag 0 (a game is in progress) is bit 0 of 0x800CC153.
    assert mp3.ADDR_SAVE_FILE + 0x8B == 0x800CC153
    assert data[0x8B] & 1


def test_mp3_bootstrap_assembles():
    options = playtest.normalize_options(3, {"coins": 77})
    board_info = {"scene_index": 0x4A}
    symbols = {}
    overlay = assemble(mp3.bootstrap_asm(board_info, options), symbol_output_map=symbols)
    assert len(overlay) % 16 == 0
    rodata = symbols["rodata"]
    assert rodata % 16 == 0 and symbols["main"] == 0
    words = struct.unpack(">%dI" % (rodata // 4), overlay[:rodata])
    assert words[0] == 0x27BDFFE8                               # addiu sp, sp, -0x18
    assert 0x0C000000 | ((mp3.FUNC_CALL_SCENE & 0x03FFFFFF) >> 2) in words
    assert 0x0C000000 | ((mp3.FUNC_INIT_OBJECTS & 0x03FFFFFF) >> 2) in words
    assert 0x2404004A in words                                  # addiu a0, zero, the board's scene
    # The data: the system structure, the four players, the save file.
    data = bytes(overlay[rodata:])
    system = bytes(mp3.system_data(2, options))
    assert data.startswith(system)
    players = data[symbols["player_data"] - rodata:symbols["save_file_data"] - rodata]
    assert players[:0x38] == bytes(mp3.player_data(0, 0, options))
    assert struct.unpack_from(">h", players, 3 * 0x38 + 0x0A)[0] == 77
    assert data[symbols["save_file_data"] - rodata:].startswith(bytes(mp3.save_file_data()))


def test_mp3_bootstrap_needs_a_battle_royal_board():
    with pytest.raises(ValueError):
        mp3.bootstrap_asm({"scene_index": 0x5B}, playtest.normalize_options(3))


# Mario Party 3: patching a ROM


class _Scenes:
    def __init__(self):
        self.replaced = None

    def replace(self, index, buffer, info):
        self.replaced = (index, bytes(buffer), dict(info))


class _Rom:
    """As much of a ROM as the patch touches: the main code, and the scenes."""

    def __init__(self):
        self.buffer = bytearray(0x80000)
        for address, (expected, _) in mp3._BOOT_PATCHES.items():
            struct.pack_into(">I", self.buffer, mp3._rom_offset(address), expected)
        for address, expected in mp3._EEPROM_PATCHES.items():
            struct.pack_into(">II", self.buffer, mp3._rom_offset(address), *expected)
        self.scenes = _Scenes()

    def get_data_view(self):
        return DataView(self.buffer)

    def get_scenes(self):
        return self.scenes


def test_mp3_apply():
    rom = _Rom()
    mp3.apply(rom, 1, {"scene_index": 0x49}, playtest.normalize_options(3))
    word = lambda address: struct.unpack_from(">I", rom.buffer, mp3._rom_offset(address))[0]
    # Both of the boot code's choices of first scene are the bootstrap, called alike.
    assert word(0x8000E644) == 0x24040058
    assert word(0x8000E64C) == 0x24060084
    # The EEPROM writes return 0 at once.
    for address in (mp3.FUNC_EEPROM_WRITE, mp3.FUNC_EEPROM_LONG_WRITE):
        assert (word(address), word(address + 4)) == (0x03E00008, 0x00001021)
    index, overlay, info = rom.scenes.replaced
    assert index == mp3.SCENE_BOOT
    assert info["code_start"] == mp3.OVERLAY_RAM_START
    assert info["code_end"] == info["rodata_start"]
    assert info["rodata_end"] == info["bss_start"] == info["bss_end"] \
        == mp3.OVERLAY_RAM_START + len(overlay)


def test_mp3_apply_refuses_other_code():
    rom = _Rom()
    struct.pack_into(">I", rom.buffer, mp3._rom_offset(0x8000E644), 0x24040012)
    before = bytes(rom.buffer)
    with pytest.raises(PlaytestError) as e:
        mp3.apply(rom, 0, {"scene_index": 0x48}, playtest.normalize_options(3))
    assert "0x8000E644" in str(e.value)
    assert bytes(rom.buffer) == before and rom.scenes.replaced is None


def test_finish_rom():
    rom = bytearray(0x40)
    rom[0x3B:0x3F] = b"NMVE"
    playtest.finish_rom(rom)
    assert rom[0x3C:0x3E] == b"ED"          # the homebrew header
    assert rom[0x3F] >> 4 == 2              # 16K EEPROM
    other = bytearray(0x40)
    other[0x3B:0x3F] = b"CLBE"
    with pytest.raises(PlaytestError):
        playtest.finish_rom(other)


# The real ROM


@pytest.fixture
def mp3_rom():
    path = _mp3_rom_path()
    if not path:
        pytest.skip("The Mario Party 3 (U) ROM is not in roms/")
    from partyplanner64.lib.romhandler import romhandler
    with open(path, "rb") as f:
        assert romhandler.set_rom_buffer(bytearray(f.read()))
    yield romhandler
    romhandler.clear()


def test_mp3_real_rom(mp3_rom):
    from partyplanner64.lib.fs.scenes import SIZEOF_SCENE_TABLE_ENTRY, read_overlay_struct
    from partyplanner64.lib.utils.cic import fix_checksum

    rh = mp3_rom
    untouched = rh.save_rom(False)
    original = rh._rom
    rh._rom = copy.deepcopy(original)
    try:
        with pytest.raises(PlaytestError):
            playtest.apply(6, None)                 # a duel board
        with pytest.raises(PlaytestError):
            playtest.apply(99, None)
        playtest.apply(3, {"coins": 10})
        table = rh.get_rom().get_scenes()._overlay_table_rom_offset
        rom = rh.save_rom(False)
        playtest.finish_rom(rom)
        with pytest.raises(PlaytestError):
            playtest.apply(3, None)                 # already patched
    finally:
        rh._rom = original
    # The open ROM is as it was.
    assert rh.save_rom(False) == untouched

    assert rom[0x3B:0x40] == b"NEDE\x20"
    # Its checksum is right (the boot code checks it).
    check = bytearray(rom)
    fix_checksum(check)
    assert check[0x10:0x18] == rom[0x10:0x18]
    # Scene 0x58 is the bootstrap, and it goes to Woody Woods (scene 0x4B).
    info = read_overlay_struct(DataView(rom), table + mp3.SCENE_BOOT * SIZEOF_SCENE_TABLE_ENTRY)
    assert info["ram_start"] == info["code_start"] == mp3.OVERLAY_RAM_START
    overlay = rom[info["rom_start"]:info["rom_end"]]
    assert len(overlay) == info["bss_end"] - info["ram_start"] < 0x400
    code = struct.unpack(">%dI" % ((info["code_end"] - info["code_start"]) // 4),
                         overlay[:info["code_end"] - info["code_start"]])
    assert 0x2404004B in code
    data = overlay[info["rodata_start"] - info["ram_start"]:]
    assert data[1] == 3                             # the board, in the system structure
    assert struct.unpack_from(">h", data, 0x64 + 0x0A)[0] == 10   # the first player's coins
