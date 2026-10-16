"""The MP2 (U) board overlay (port of adapter/MP2.U.boardoverlay.ts).

The assembly is in overlays/mp2_u_boardoverlay.s.tmpl, with <<name>> placeholders
for the values the TypeScript interpolated; create_board_overlay computes them.
"""

from ..types import Game, SpaceSubtype
from .overlayutils import (
    ensure_at_least_two, event_id, fill_overlay_template, find_closest_spaces,
    find_toad_indices, get_arrow_rotation_instructions, get_mainfs_event_file,
    get_shuffle_seed_data, get_spaces_of_subtype, get_star_indices, js_join)

TEMPLATE = "mp2_u_boardoverlay.s.tmpl"


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
    from ..boards import get_dead_space_index, get_spaces_with_event
    from ..events.builtin.events_common import BankEvent, BooEvent, ItemShopEvent
    from ..events.additionalbg import (
        get_additional_bg_asm_for_overlay, get_board_additional_bg_hvq_indices)
    from ..events.getaudiochoice import get_audio_index_asm_for_overlay

    star_indices = get_star_indices(board)

    # show_next_star_fn = "show_next_star_spot" if star_indices else "show_next_star_no_op"
    shuffle_data = get_shuffle_seed_data(len(star_indices))

    # Determine the toad spaces, using distance formula for now.
    toad_spaces = get_spaces_of_subtype(SpaceSubtype.TOAD, board)
    toad_indices = find_toad_indices(board, star_indices, toad_spaces)

    bank_coin_spaces = get_spaces_of_subtype(SpaceSubtype.BANKCOIN, board)
    ensure_at_least_two(bank_coin_spaces, board)

    # Find the closest Bank subtype space for each bank event space.
    bank_spaces = get_spaces_of_subtype(SpaceSubtype.BANK, board)
    bank_event_spaces = get_spaces_with_event(event_id(BankEvent), board)
    best_bank_for_bank_spaces = find_closest_spaces(board, bank_event_spaces, bank_spaces)
    if not bank_spaces:
        bank_spaces.append(get_dead_space_index(board))
    ensure_at_least_two(bank_event_spaces, board)
    ensure_at_least_two(best_bank_for_bank_spaces, board)

    # Find the closest ItemShop subtype space for each shop event space.
    item_shop_spaces = get_spaces_of_subtype(SpaceSubtype.ITEMSHOP, board)
    item_shop_event_spaces = get_spaces_with_event(event_id(ItemShopEvent), board)
    best_shop_for_shop_event_spaces = find_closest_spaces(
        board, item_shop_event_spaces, item_shop_spaces)
    if not item_shop_spaces:
        item_shop_spaces.append(get_dead_space_index(board))
    ensure_at_least_two(item_shop_event_spaces, board)
    ensure_at_least_two(best_shop_for_shop_event_spaces, board)

    # Find the closest Boo subtype space for each boo event space.
    boo_indices = get_spaces_of_subtype(SpaceSubtype.BOO, board)
    boo_event_spaces = get_spaces_with_event(event_id(BooEvent), board)
    best_boo_for_boo_event_spaces = find_closest_spaces(board, boo_event_spaces, boo_indices)
    if not boo_indices:
        boo_indices.append(get_dead_space_index(board))
    ensure_at_least_two(boo_event_spaces, board)
    ensure_at_least_two(best_boo_for_boo_event_spaces, board)

    arrow_rotation_instructions = get_arrow_rotation_instructions(board, Game.MP2_USA)

    additional_bg_indices = get_board_additional_bg_hvq_indices(board)
    prepped_additional_bg_code = get_additional_bg_asm_for_overlay(
        board, board_info["bg_dir"], additional_bg_indices)
    prepped_audio_index_code = get_audio_index_asm_for_overlay(board, audio_indices)

    return fill_overlay_template(TEMPLATE, {
        "additional_bg_code": prepped_additional_bg_code,
        "arrow_rotation_instructions": "\n".join(arrow_rotation_instructions),
        "audio_index_code": prepped_audio_index_code,
        "bank_coin_spaces": js_join(bank_coin_spaces),
        "bank_count": len(bank_spaces),
        "bank_event_spaces_0": bank_event_spaces[0],
        "bank_event_spaces_1": bank_event_spaces[1],
        "bank_spaces": js_join(bank_spaces),
        "best_bank_for_bank_spaces_0": best_bank_for_bank_spaces[0],
        "best_bank_for_bank_spaces_1": best_bank_for_bank_spaces[1],
        "best_boo_for_boo_event_spaces_0": best_boo_for_boo_event_spaces[0],
        "best_boo_for_boo_event_spaces_1": best_boo_for_boo_event_spaces[1],
        "best_shop_for_shop_event_spaces_0": best_shop_for_shop_event_spaces[0],
        "board_def_file": board_info.get("board_def_file"),
        "board_index": board_index,
        "board_index_x4": board_index * 4,
        "boo_count": len(boo_indices),
        "boo_event_spaces_0": boo_event_spaces[0],
        "boo_indices": js_join(boo_indices),
        "item_shop_count": len(item_shop_spaces),
        "item_shop_spaces": js_join(item_shop_spaces),
        "mainfs_event_dir": main_fs_event_dir,
        "mainfs_event_file": main_fs_event_file,
        "shuffle_bias": js_join(shuffle_data["bias"]),
        "shuffle_order": js_join(shuffle_data["order"]),
        "star_count": len(star_indices),
        "star_indices_or_0": js_join(star_indices) or 0,
        "toad_indices_or_0": js_join(toad_indices) or 0,
    })
