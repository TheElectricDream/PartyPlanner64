"""Play-testing a board: a ROM that boots straight into it, in the middle of a game.

A normal ROM boots through the logos, the title screen, the file select and
the game's set-up screens before a board is played, and a board starts with
its opening scenes. A test ROM skips all of that: the boot code is patched
so that the game sets up a game in progress (the players, their coins and
stars, the turn) and goes straight to the board, as if a saved game had been
resumed. It is meant for emulators, as the quick way to try a board and its
events; nothing is saved from a test ROM.

    from partyplanner64.lib import playtest

    options = playtest.normalize_options(3, {"coins": 50})
    playtest.apply(rom_board_index, options)      # on the loaded ROM (romhandler)
    rom = romhandler.save_rom(False)
    playtest.finish_rom(rom)                      # the header, after saving

`apply` changes the loaded ROM for good (its boot code no longer reaches the
title screen), so callers work on a copy of the ROM; `partyplanner64.state`
does (`build_test_rom`).

Each game has a module (mp3.py) with what was learned about how it starts a
board; a game without one cannot be play-tested yet (`unsupported_reason`).
"""

from ..types import BoardType, Game


class PlaytestError(Exception):
    """The board (or the ROM) cannot be play-tested; the message says why."""


# How a player is controlled: one of the four controllers, or the game.
CONTROLS = [
    {"id": "pad1", "name": "Controller 1"},
    {"id": "pad2", "name": "Controller 2"},
    {"id": "pad3", "name": "Controller 3"},
    {"id": "pad4", "name": "Controller 4"},
    {"id": "cpu", "name": "Computer"},
]
_CONTROL_IDS = [c["id"] for c in CONTROLS]

MAX_COINS = 999
MAX_STARS = 99


def _module(game):
    """The module for a game ID (e.g. "NMVE"), or None."""
    game = getattr(game, "value", game)
    if game == Game.MP3_USA.value:
        from . import mp3
        return mp3
    return None


def _module_for_version(game_version):
    return _module({3: Game.MP3_USA}.get(game_version))


def unsupported_reason(game, board_type=BoardType.NORMAL):
    """Why a board of this type cannot be play-tested in this game, or None if it can.

    game: a game ID ("NMVE"). board_type: BoardType, or its value.
    """
    module = _module(game)
    if module is None:
        return ("Test play is only available for Mario Party 3 (U) so far; "
                "save the ROM and play the board from the game's menus.")
    board_type = getattr(board_type, "value", board_type) or BoardType.NORMAL.value
    if board_type not in module.BOARD_TYPES:
        return "Test play is not available for duel boards yet."
    return None


def describe(game_version):
    """What a game's test options can be: {characters, items, itemSlots, difficulties,
    controls, maxTurns, defaults}; None for a game that cannot be play-tested."""
    module = _module_for_version(game_version)
    if module is None:
        return None
    return {
        "characters": [{"id": i, "name": n} for i, n in enumerate(module.CHARACTERS)],
        "items": [{"id": i, "name": n} for i, n in module.ITEMS],
        "itemSlots": module.ITEM_SLOTS,
        "difficulties": [{"id": i, "name": n} for i, n in enumerate(module.DIFFICULTIES)],
        "controls": [dict(c) for c in CONTROLS],
        "maxTurns": module.MAX_TURNS,
        "maxCoins": MAX_COINS,
        "maxStars": MAX_STARS,
        "defaults": default_options(game_version),
    }


def default_options(game_version):
    """The test options a game starts with (see normalize_options)."""
    module = _module_for_version(game_version)
    characters = len(module.CHARACTERS) if module else 4
    return {
        "players": [
            {"character": i % characters, "control": "pad1" if i == 0 else "cpu",
             "difficulty": 1, "items": []}
            for i in range(4)
        ],
        "coins": 50,
        "stars": 0,
        "turns": 20,
        "turn": 1,
    }


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise PlaytestError("%s must be a whole number." % name)
    value = int(value)
    if not low <= value <= high:
        raise PlaytestError("%s must be from %d to %d." % (name, low, high))
    return value


def normalize_options(game_version, options=None):
    """Check test options and fill in what is missing; returns a new dict.

    options (all optional):
        players: four of {character, control, difficulty, items}. character: an index
            into the game's characters. control: "pad1".."pad4" or "cpu" (players may
            share a controller: with "pad1" for all four, one person plays every
            turn). difficulty: of a computer player, an index into the game's
            difficulties. items: the items held (item ids), at most the game's slots.
        coins, stars: what every player starts with.
        turns: the length of the game. turn: the turn it starts on (1 is the first).

    Raises PlaytestError for values the game does not have.
    """
    module = _module_for_version(game_version)
    if module is None:
        raise PlaytestError("Mario Party %s cannot be play-tested yet." % game_version)
    out = default_options(game_version)
    options = options or {}
    if not isinstance(options, dict):
        raise PlaytestError("The test options are an object.")

    players = options.get("players")
    if players is not None:
        if not isinstance(players, (list, tuple)) or len(players) != 4:
            raise PlaytestError("There are four players.")
        item_ids = [i for i, _ in module.ITEMS]
        for n, (player, default) in enumerate(zip(players, out["players"])):
            if not isinstance(player, dict):
                raise PlaytestError("Player %d is an object." % (n + 1))
            name = "Player %d's" % (n + 1)
            if player.get("character") is not None:
                default["character"] = _int(player["character"], 0, len(module.CHARACTERS) - 1,
                                            name + " character")
            if player.get("control") is not None:
                if player["control"] not in _CONTROL_IDS:
                    raise PlaytestError("%s control is one of: %s." % (name, ", ".join(_CONTROL_IDS)))
                default["control"] = player["control"]
            if player.get("difficulty") is not None:
                default["difficulty"] = _int(player["difficulty"], 0, len(module.DIFFICULTIES) - 1,
                                             name + " difficulty")
            if player.get("items") is not None:
                items = player["items"]
                if not isinstance(items, (list, tuple)) or len(items) > module.ITEM_SLOTS:
                    raise PlaytestError("%s items are a list of at most %d."
                                        % (name, module.ITEM_SLOTS))
                for item in items:
                    if isinstance(item, bool) or item not in item_ids:
                        raise PlaytestError("%s items: there is no item %r." % (name, item))
                default["items"] = [int(i) for i in items]

    if options.get("coins") is not None:
        out["coins"] = _int(options["coins"], 0, MAX_COINS, "Coins")
    if options.get("stars") is not None:
        out["stars"] = _int(options["stars"], 0, MAX_STARS, "Stars")
    if options.get("turns") is not None:
        out["turns"] = _int(options["turns"], 1, module.MAX_TURNS, "The number of turns")
    if options.get("turn") is not None:
        out["turn"] = _int(options["turn"], 1, module.MAX_TURNS, "The turn")
    if out["turn"] > out["turns"]:
        raise PlaytestError("The game starts on turn %d, after its last turn (%d)."
                            % (out["turn"], out["turns"]))
    return out


def apply(rom_board_index, options=None):
    """Patch the loaded ROM (romhandler) to boot into the board at rom_board_index.

    options: test options (normalize_options); the defaults if None.
    Raises PlaytestError when the ROM's game or the board cannot be play-tested.
    """
    from ..adapter.boardinfo import get_board_infos
    from ..romhandler import romhandler

    game = romhandler.get_rom_game()
    module = _module(game)
    if module is None:
        raise PlaytestError(unsupported_reason(game))
    board_infos = get_board_infos(game) or []
    if isinstance(rom_board_index, bool) or not isinstance(rom_board_index, int) \
            or not 0 <= rom_board_index < len(board_infos):
        raise PlaytestError("There is no ROM board %r." % (rom_board_index,))
    board_info = board_infos[rom_board_index]
    reason = unsupported_reason(game, board_info.get("type") or BoardType.NORMAL)
    if reason:
        raise PlaytestError(reason)
    options = normalize_options(romhandler.get_game_version(), options)
    module.apply(romhandler.get_rom(), rom_board_index, board_info, options)


def finish_rom(rom_buffer):
    """The last changes to a saved test ROM (a bytearray, changed in place): its header.

    Call it on what romhandler.save_rom returned, after `apply`.
    """
    game = "".join(chr(b) for b in rom_buffer[0x3B:0x3F])
    module = _module(game)
    if module is None:
        raise PlaytestError(unsupported_reason(game))
    module.finish_rom(rom_buffer)
