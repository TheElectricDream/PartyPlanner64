"""Applies the Gameshark hook to a ROM (port of patches/gameshark/hook.ts)."""

import logging

from ...types import Game
from ...utils.debug import log
from . import cheats


def apply_hook(rom_buffer):
    cheat_count = len(cheats.current_cheats)
    if not cheat_count:
        # This would leave existing cheats if they were already present; doesn't clear them.
        return

    from ...romhandler import romhandler
    from .hook_mp1_u import MP1UHook
    from .hook_mp2_u import MP2UHook
    from .hook_mp3_u import MP3UHook

    game_id = romhandler.get_rom_game()
    if game_id == Game.MP1_USA:
        MP1UHook.apply(rom_buffer)
    elif game_id == Game.MP2_USA:
        MP2UHook.apply(rom_buffer)
    elif game_id == Game.MP3_USA:
        MP3UHook.apply(rom_buffer)
    else:
        logging.getLogger("partyplanner64").warning("Cannot write cheats for this game")
        return

    log("Applied %d Gameshark cheats" % cheat_count)


def rom_supports_cheats():
    from ...romhandler import romhandler

    game_id = romhandler.get_rom_game()
    return game_id in (Game.MP1_USA, Game.MP2_USA, Game.MP3_USA)
