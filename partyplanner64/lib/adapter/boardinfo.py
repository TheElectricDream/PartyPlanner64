"""Board info lookup by game (port of adapter/boardinfo.ts)."""

from ..types import Game
from ..utils.debug import log


def get_board_infos(game_id):
    """Return the list of board info dicts for a game ID, or None."""
    game_id = getattr(game_id, "value", game_id)
    if game_id == Game.MP1_USA.value:
        from .boardinfo_mp1_u import get_board_infos as get_mp1u_board_infos
        return get_mp1u_board_infos()
    if game_id == Game.MP1_JPN.value:
        from .boardinfo_mp1_j import get_board_infos as get_mp1j_board_infos
        return get_mp1j_board_infos()
    if game_id == Game.MP2_USA.value:
        from .boardinfo_mp2 import get_board_infos as get_mp2_board_infos
        return get_mp2_board_infos()
    if game_id == Game.MP3_USA.value:
        from .boardinfo_mp3 import get_board_infos as get_mp3_board_infos
        return get_mp3_board_infos()

    log("Missing boardinfo for " + str(game_id))
    return None


def get_board_info_by_index(game_id, index):
    return get_board_infos(game_id)[index]


def get_arrow_rotation_limit():
    # 8 arrows is the imposed restriction by the game.
    return 8
