"""The MP1 (U) board overlay (port of adapter/MP1.U.boardoverlay.ts).

The assembly is in overlays/mp1_u_boardoverlay.s.tmpl, with <<name>> placeholders
for the values the TypeScript interpolated; create_board_overlay computes them.
"""

from ..types import Game, SpaceSubtype
from .overlayutils import (
    fill_overlay_template, find_toad_indices, get_mainfs_event_file,
    get_shuffle_seed_data, get_spaces_of_subtype, get_star_indices, js_join)

TEMPLATE = "mp1_u_boardoverlay.s.tmpl"


def create_board_overlay(board, board_info, board_index, audio_indices):
    """Create the assembly of the board's overlay.

    Args:
        board: The board (dict, board JSON). The dead space may be added to it.
        board_info: The board info dict of the board being overwritten.
        board_index: Index of the board being overwritten.
        audio_indices: Music indices for the board.

    Returns:
        The overlay assembly source text.
    """
    main_fs_event_dir, main_fs_event_file = get_mainfs_event_file(board_info)

    # Imported here: boards imports the adapters, which import this module.
    from ..boards import get_dead_space_index
    from ..symbols.symbols import get_symbol
    from ..events.additionalbg import (
        get_additional_bg_asm_for_overlay, get_board_additional_bg_hvq_indices)
    from ..events.getaudiochoice import get_audio_index_asm_for_overlay

    boo_indices = get_spaces_of_subtype(SpaceSubtype.BOO, board)

    koopa_indices = get_spaces_of_subtype(SpaceSubtype.KOOPA, board)
    koopa_index = get_dead_space_index(board) if not koopa_indices else koopa_indices[0]

    bowser_indices = get_spaces_of_subtype(SpaceSubtype.BOWSER, board)
    bowser_index = get_dead_space_index(board) if not bowser_indices else bowser_indices[0]

    star_indices = get_star_indices(board)

    show_next_star_fn = "show_next_star_spot" if star_indices else "show_next_star_no_op"
    shuffle_data = get_shuffle_seed_data(len(star_indices))

    # Determine the toad spaces, using distance formula for now.
    toad_spaces = get_spaces_of_subtype(SpaceSubtype.TOAD, board)
    toad_indices = find_toad_indices(board, star_indices, toad_spaces)

    # This runs before we've written the additional bgs, but we can predict the directories.
    additional_bg_indices = get_board_additional_bg_hvq_indices(board)

    prepped_additional_bg_code = get_additional_bg_asm_for_overlay(
        board, board_info["bg_dir"], additional_bg_indices)
    prepped_audio_index_code = get_audio_index_asm_for_overlay(board, audio_indices)

    return fill_overlay_template(TEMPLATE, {
        "additional_bg_code": prepped_additional_bg_code,
        "audio_index_code": prepped_audio_index_code,
        "board_def_file": board_info.get("board_def_file"),
        "boo_count": len(boo_indices),
        "boo_indices": js_join(boo_indices),
        "boo_zeros": js_join([0 for _ in boo_indices]),
        "bowser_index": bowser_index,
        "koopa_index": koopa_index,
        "mainfs_event_dir": main_fs_event_dir,
        "mainfs_event_file": main_fs_event_file,
        "pause_bg_dir": board_info.get("pause_bg_dir"),
        "show_next_star_fn": show_next_star_fn,
        "shuffle_bias": js_join(shuffle_data["bias"]),
        "shuffle_order": js_join(shuffle_data["order"]),
        "star_count": len(star_indices),
        "star_indices_or_0": js_join(star_indices) or 0,
        "sym_EventTableHydrate": get_symbol(Game.MP1_USA, "EventTableHydrate"),
        "sym_FreeMainFS": get_symbol(Game.MP1_USA, "FreeMainFS"),
        "sym_ReadMainFS": get_symbol(Game.MP1_USA, "ReadMainFS"),
        "toad_indices_or_0": js_join(toad_indices) or 0,
        "toad_zeros_or_0": js_join([0 for _ in toad_indices]) or 0,
    })
