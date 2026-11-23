"""Play-testing Mario Party 3 (U): boot a ROM straight into a Battle Royal board.

Everything here was worked out from the game's own code and from watching its
memory while it runs (addresses are RAM addresses of the (U) ROM; code of the
main segment is at ROM offset `address - 0x80000400 + 0x1000`).

Scenes. The game is a set of overlays ("scenes"), each entered at its first
function with an event number and status flags:

- 0x80048128 calls a scene (`LoadOverlay` in the symbols): it pushes
  {u32 scene, s16 event, u16 status} on the scene stack (0x800D2010, 8 bytes
  an entry; s16 depth at 0x800A1768) and asks for the change (0x80048228);
  0x8004819C returns to an entry further down the stack.
- Status bit 0x2 loads the Battle Royal boards' shared code (overlay 0x80, at
  0x800D6B70) before the scene; the board overlays (0x48-0x4D) need it.

Booting. The main thread (0x8000E63C) calls scene 0x58 (the logos), or scene
0x67 when the EEPROM's data is not valid. From there the player reaches the
title screen, the file select and Party Mode.

Resuming. Party Mode resumes a saved Battle Royal like this (overlay 0x77,
0x80108690): it reads the saved game into the game state (0x8005086C), which
is one system structure (0x62 bytes at 0x800CD058) and four player structures
(0x38 bytes each, from 0x800D1108); sets the play mode (0x800CD058) to 1 and
flag 0 of the save file's flags (0x800CC153, bit 0: "a game is in progress");
then calls scene 0x47 with event 0 and status 0x92. Scene 0x47 sees the flag,
skips the opening scenes (which player goes first, the star's first place) and
calls the board's overlay with event 2: the board, at the start of a turn.

The test ROM does the same, with a game state of its own making. Its scene
0x58 is replaced by a small overlay (bootstrap, below) that writes the system
structure, the players and a new save file's data, then calls the board's
overlay with event 1: the board's once-a-game set-up (the players on the start
space, the stars' order...), which a new game runs before its opening scenes.
Event 1 ends by returning to the scene below it on the stack, where the
bootstrap put scene 0x47, which goes on to the board as for a resumed game.
The values of the structures are those of a real game at its first turn (20
turns, bonus stars, every mini-game), read from the game's memory.

Saving. Nothing is saved: the "save data is usable" byte (0x800CBAB0) is
cleared, which the save routines check, and osEepromWrite and
osEepromLongWrite return at once, so emulators keep no save file for a test
ROM either.

The header. Emulators pick a ROM's save type (Mario Party 3 needs the 16K
EEPROM, and hangs at boot with the 4K one) from a database keyed by the ROM's
checksums, which an edited ROM is not in. The test ROM therefore has the
"Advanced Homebrew ROM Header" (cartridge ID "ED", save type in the last
header byte), which mupen64plus (RMG, RMG-K, simple64...), ares and flash
carts read.
"""

import struct

from ..types import BoardType

BOARD_TYPES = (BoardType.NORMAL.value,)

# The characters, by the number the game gives them (byte 3 of a player).
CHARACTERS = ["Mario", "Luigi", "Peach", "Yoshi", "Wario", "Donkey Kong", "Waluigi", "Daisy"]

# Computer players' skill (byte 1 of a player).
DIFFICULTIES = ["Easy", "Normal", "Hard", "Super Hard"]

# The items (the three s8 at 0x18 of a player; -1 is an empty slot).
ITEMS = [
    (0x00, "Mushroom"),
    (0x01, "Skeleton Key"),
    (0x02, "Poison Mushroom"),
    (0x03, "Reverse Mushroom"),
    (0x04, "Cellular Shopper"),
    (0x05, "Warp Block"),
    (0x06, "Plunder Chest"),
    (0x07, "Bowser Phone"),
    (0x08, "Dueling Glove"),
    (0x09, "Lucky Lamp"),
    (0x0A, "Golden Mushroom"),
    (0x0B, "Boo Bell"),
    (0x0C, "Boo Repellant"),
    (0x0D, "Bowser Suit"),
    (0x0E, "Magic Lamp"),
    (0x0F, "Koopa Kard"),
    (0x10, "Barter Box"),
    (0x11, "Lucky Charm"),
    (0x12, "Wacky Watch"),
]
ITEM_SLOTS = 3
MAX_TURNS = 50

# Scenes (overlays).
SCENE_BOOT = 0x58               # the logos: the first scene; replaced by the bootstrap
SCENE_BOARD_HANDOFF = 0x47      # starts or resumes a Battle Royal board
SCENE_FIRST_BOARD = 0x48        # Chilly Waters; the six boards follow each other
OVERLAY_RAM_START = 0x801059A0  # where every scene's overlay is loaded

# Game state.
ADDR_SYSTEM = 0x800CD058        # 0x62 bytes
ADDR_PLAYERS = 0x800D1108       # 4 x 0x38 bytes, in turn order
ADDR_SAVE_FILE = 0x800CC0C8     # 0xA4 bytes: the open save file
ADDR_SAVE_USABLE = 0x800CBAB0   # u8: 0 = the save routines do nothing
ADDR_SCENE_STACK = 0x800D2010
ADDR_SCENE_DEPTH = 0x800A1768
SIZEOF_SYSTEM = 0x62
SIZEOF_PLAYER = 0x38
SIZEOF_SAVE_FILE = 0xA4

# Code.
FUNC_CALL_SCENE = 0x80048128    # (scene, event, status)
FUNC_INIT_OBJECTS = 0x80047160  # (max objects, max processes): every scene's first call
FUNC_EEPROM_WRITE = 0x80072020          # osEepromWrite
FUNC_EEPROM_LONG_WRITE = 0x800724A0     # osEepromLongWrite

# The main thread's choice of first scene: {RAM address: (instruction, replacement)}.
#   8000E63C: beqz  s0, 8000E650     ; s0: the EEPROM's data is not valid
#   8000E644: addiu a0, zero, 0x67 / 8000E64C: addiu a2, zero, 0x82
#   8000E650: addiu a0, zero, 0x58 / 8000E654: addiu a2, zero, 0x84
#   8000E658: jal   0x80048128
_BOOT_PATCHES = {
    0x8000E644: (0x24040067, 0x24040000 | SCENE_BOOT),
    0x8000E64C: (0x24060082, 0x24060084),
}
# The first two instructions of osEepromWrite and osEepromLongWrite become
# `jr ra` / `move v0, zero` (return 0: no error).
_EEPROM_PATCHES = {
    FUNC_EEPROM_WRITE: (0x27BDFFB0, 0xAFB10034),
    FUNC_EEPROM_LONG_WRITE: (0x27BDFFC0, 0xAFB50034),
}
_RETURN_ZERO = (0x03E00008, 0x00001021)

_BOOTSTRAP_ASM = """
.org 0x{org:08X}
main:
  addiu SP, SP, -0x18
  sw    RA, 0x10(SP)

  ; The game in progress: the system structure, the players, the save file.
  lui   A0, hi(0x{system:08X})
  addiu A0, A0, lo(0x{system:08X})
  lui   A1, hi(system_data)
  addiu A1, A1, lo(system_data)
  jal   copy
   addiu A2, R0, {system_size}
  lui   A0, hi(0x{players:08X})
  addiu A0, A0, lo(0x{players:08X})
  lui   A1, hi(player_data)
  addiu A1, A1, lo(player_data)
  jal   copy
   addiu A2, R0, {players_size}
  lui   A0, hi(0x{save_file:08X})
  addiu A0, A0, lo(0x{save_file:08X})
  lui   A1, hi(save_file_data)
  addiu A1, A1, lo(save_file_data)
  jal   copy
   addiu A2, R0, {save_file_size}

  ; Nothing is saved.
  lui   AT, hi(0x{save_usable:08X})
  sb    R0, lo(0x{save_usable:08X})(AT)

  addiu A0, R0, 10
  jal   0x{init_objects:08X}
   addu  A1, R0, R0

  ; Push the scene that starts the board, for the board's set-up to return to.
  lui   V1, hi(0x{scene_depth:08X})
  lh    V0, lo(0x{scene_depth:08X})(V1)
  addiu V0, V0, 1
  sh    V0, lo(0x{scene_depth:08X})(V1)
  sll   V0, V0, 3
  lui   V1, hi(0x{scene_stack:08X})
  addiu V1, V1, lo(0x{scene_stack:08X})
  addu  V1, V1, V0
  addiu V0, R0, {handoff_scene}
  sw    V0, 0(V1)
  sh    R0, 4(V1)
  addiu V0, R0, 0x92
  sh    V0, 6(V1)

  ; The board's once-a-game set-up (event 1).
  addiu A0, R0, {board_scene}
  addiu A1, R0, 1
  jal   0x{call_scene:08X}
   addiu A2, R0, 0x192

  lw    RA, 0x10(SP)
  jr    RA
   addiu SP, SP, 0x18

; A0: to, A1: from, A2: byte count (not 0)
copy:
  lbu   T0, 0(A1)
  sb    T0, 0(A0)
  addiu A1, A1, 1
  addiu A2, A2, -1
  bgtz  A2, copy
   addiu A0, A0, 1
  jr    RA
   nop

.align 16
rodata:
system_data:
{system_words}
player_data:
{player_words}
save_file_data:
{save_file_words}
.align 16
"""


def board_scene(board_info):
    """The scene (overlay) of a Battle Royal board, from its board info."""
    return board_info["scene_index"]


def system_data(board_index, options):
    """The system structure (0x62 bytes at 0x800CD058) of a game at the start of a turn.

    Offsets, as far as they are known:
        0x00  play mode: 1 = Battle Royal (2 = Duel)
        0x01  board (0 = Chilly Waters ... 5 = Waluigi's Island)
        0x02  number of turns        0x03  the turn (1 = the first)
        0x05  which of the star places has the star: an index into the order at
        0x06  (8 bytes) the order of the star places; the board's set-up shuffles it
        0x0F  the player whose turn it is
        0x11  the current space (s8, -1 = none), used during a turn
        0x15  message speed (0, 1 or 2)
        0x17  19 bytes of 0x3F, and 0x2A: 19 bytes of 0x03 (used by duels)
        0x48  10 bytes: the boards' own state (bank coins, ...), all 0
        0x5E  the board flags (4 bytes, flag n is bit n % 8 of byte n / 8)
    Bytes that are not understood have the values of a real game.
    """
    data = bytearray(SIZEOF_SYSTEM)
    data[0x00] = 1
    data[0x01] = board_index
    data[0x02] = options["turns"]
    data[0x03] = options["turn"]
    data[0x06:0x0E] = bytes(range(8))
    data[0x0E] = 0xFF
    data[0x11] = 0xFF
    data[0x12] = 2
    data[0x14] = 1
    data[0x15] = 1
    data[0x17:0x2A] = b"\x3F" * 19
    data[0x2A:0x3D] = b"\x03" * 19
    data[0x5E] = 0xE8
    data[0x5F] = 0xBD
    return data


def _ports(players):
    """The controller port of each player: a computer player gets a free one."""
    taken = {int(p["control"][3]) - 1 for p in players if p["control"] != "cpu"}
    free = [port for port in range(4) if port not in taken]
    ports = []
    for player in players:
        if player["control"] != "cpu":
            ports.append(int(player["control"][3]) - 1)
        else:
            ports.append(free.pop(0) if free else len(ports))
    return ports


def player_data(turn_position, port, options):
    """A player structure (0x38 bytes); the four are in the order they take their turns.

    Offsets, as far as they are known:
        0x01  computer player's skill (0 easy ... 3 super hard)
        0x02  controller port (0-3)        0x03  character
        0x04  flags: 0x01 = computer player; 0x04 is set once the game has started
        0x0A  s16 coins                    0x0E  s8 stars
        0x0F  where the player is: chain, and 0x10: the space's index in it; then the
              next ones. The board's set-up puts every player on the first space.
        0x18  three s8 items (-1 = none)   0x1C  the colour of the space landed on
        0x1D  position in the turn order
        0x24  pointer to the player's object, set by the board
        0x2A  s16 most coins held (for the coin star)
    """
    player = options["players"][turn_position]
    cpu = player["control"] == "cpu"
    data = bytearray(SIZEOF_PLAYER)
    data[0x01] = player["difficulty"]
    data[0x02] = port
    data[0x03] = player["character"]
    data[0x04] = 0x04 | (0x01 if cpu else 0)
    struct.pack_into(">h", data, 0x0A, options["coins"])
    data[0x0E] = options["stars"]
    data[0x0F:0x17] = bytes([0, 0, 0, 1, 0xFF, 0xFF, 0, 0xFF])
    items = list(player["items"]) + [0xFF] * ITEM_SLOTS
    data[0x18:0x18 + ITEM_SLOTS] = bytes(items[:ITEM_SLOTS])
    data[0x1D] = turn_position
    struct.pack_into(">h", data, 0x2A, options["coins"])
    data[0x35] = 0xFF
    return data


def save_file_data():
    """The open save file (0xA4 bytes at 0x800CC0C8): a new file, with a game in progress.

    It starts with the mini-game records (24 bytes); the flags are from 0x8B (flag n
    is bit n % 8 of byte 0x8B + n / 8); the file's name ("D K", two bytes a
    character) is at 0x94; the options follow.
    """
    data = bytearray(SIZEOF_SAVE_FILE)
    data[0x00:0x18] = bytes.fromhex("910200640e100e10070803e80e100e100e10000015180000")
    data[0x8B] = 0x01                     # flag 0: a Battle Royal is in progress
    data[0x8E] = 0x0C
    data[0x90] = 0xC0
    data[0x94:0x9A] = bytes.fromhex("82638140826a")
    data[0x9E] = 0x02
    data[0xA0] = 0x01
    data[0xA1] = 0x01
    return data


def _words(data):
    data = bytes(data) + bytes(-len(data) % 4)
    return "\n".join(".word 0x%08X" % w for w in struct.unpack(">%dI" % (len(data) // 4), data))


def bootstrap_asm(board_info, options):
    """The assembly of the overlay that replaces scene 0x58."""
    scene = board_scene(board_info)
    board_index = scene - SCENE_FIRST_BOARD
    if not 0 <= board_index < 6:
        raise ValueError("Scene 0x%X is not a Battle Royal board." % scene)
    ports = _ports(options["players"])
    players = b"".join(player_data(i, ports[i], options) for i in range(4))
    return _BOOTSTRAP_ASM.format(
        org=OVERLAY_RAM_START,
        system=ADDR_SYSTEM, system_size=SIZEOF_SYSTEM,
        players=ADDR_PLAYERS, players_size=len(players),
        save_file=ADDR_SAVE_FILE, save_file_size=SIZEOF_SAVE_FILE,
        save_usable=ADDR_SAVE_USABLE,
        init_objects=FUNC_INIT_OBJECTS, call_scene=FUNC_CALL_SCENE,
        scene_depth=ADDR_SCENE_DEPTH, scene_stack=ADDR_SCENE_STACK,
        handoff_scene=SCENE_BOARD_HANDOFF, board_scene=scene,
        system_words=_words(system_data(board_index, options)),
        player_words=_words(players),
        save_file_words=_words(save_file_data()))


def _rom_offset(address):
    return address - 0x80000400 + 0x1000


def apply(rom, rom_board_index, board_info, options):
    """Patch a loaded ROM (lib.romhandler.ROM) to boot into the board of board_info.

    options: normalized test options (playtest.normalize_options).
    """
    from ..mips import assemble
    from . import PlaytestError

    view = rom.get_data_view()
    patches = {}
    for address, (expected, replacement) in _BOOT_PATCHES.items():
        patches[address] = ((expected,), (replacement,))
    for address, expected in _EEPROM_PATCHES.items():
        patches[address] = (expected, _RETURN_ZERO)
    for address, (expected, _) in patches.items():
        found = tuple(view.get_uint32(_rom_offset(address) + 4 * i) for i in range(len(expected)))
        if found != tuple(expected):
            raise PlaytestError(
                "The ROM's code at 0x%08X is not Mario Party 3 (U)'s (%s), so it cannot be "
                "patched for test play." % (address, " ".join("%08X" % w for w in found)))

    symbols = {}
    overlay = assemble(bootstrap_asm(board_info, options), symbol_output_map=symbols)
    rodata = symbols["rodata"]
    end = OVERLAY_RAM_START + len(overlay)
    rom.get_scenes().replace(SCENE_BOOT, bytearray(overlay), {
        "code_start": OVERLAY_RAM_START,
        "code_end": OVERLAY_RAM_START + rodata,
        "rodata_start": OVERLAY_RAM_START + rodata,
        "rodata_end": end,
        "bss_start": end,
        "bss_end": end,
    })

    for address, (_, replacement) in patches.items():
        for i, word in enumerate(replacement):
            view.set_uint32(_rom_offset(address) + 4 * i, word)


def finish_rom(rom_buffer):
    """Give a saved test ROM the homebrew header: cartridge ID "ED", 16K EEPROM."""
    rom_buffer[0x3C:0x3E] = b"ED"
    rom_buffer[0x3F] = 0x20           # high nibble: save type 2 (16K EEPROM)
