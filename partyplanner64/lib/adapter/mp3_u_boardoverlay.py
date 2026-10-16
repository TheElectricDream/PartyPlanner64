"""The MP3 (U) board overlay (port of adapter/MP3.U.boardoverlay.ts).

The assembly is in overlays/mp3_u_boardoverlay.s.tmpl, with <<name>> placeholders
for the values the TypeScript interpolated; create_board_overlay computes them.
"""

import sys

from ..types import Game, SpaceSubtype
from ..utils.number import distance
from .overlayutils import (
    ensure_at_least_two, event_id, fill_overlay_template, find_closest_spaces,
    find_toad_indices, get_arrow_rotation_instructions, get_mainfs_event_file,
    get_shuffle_seed_data, get_spaces_of_subtype, get_star_indices, js_at, js_join)

TEMPLATE = "mp3_u_boardoverlay.s.tmpl"


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
    from ..boards import for_each_event, get_dead_space_index, get_spaces_with_event
    from ..events.builtin.events_common import BankEvent, BooEvent, Gate, ItemShopEvent
    from ..symbols.symbols import get_symbol
    from ..events.additionalbg import (
        get_additional_bg_asm_for_overlay, get_board_additional_bg_hvq_indices)
    from ..events.getaudiochoice import get_audio_index_asm_for_overlay

    boo_indices = get_spaces_of_subtype(SpaceSubtype.BOO, board)
    boo_index = get_dead_space_index(board) if not boo_indices else boo_indices[0]
    boo_event_spaces = get_spaces_with_event(event_id(BooEvent), board)
    primary_boo_event_space = -1
    if not boo_event_spaces:
        boo_event_spaces = [get_dead_space_index(board)]
    else:
        best_distance = sys.float_info.max
        boo_space = js_at(board["spaces"], boo_index)
        if boo_space:
            for boo_event_space_index in boo_event_spaces:
                boo_event_space = board["spaces"][boo_event_space_index]
                dist = distance(boo_event_space["x"], boo_event_space["y"],
                                boo_space["x"], boo_space["y"])
                if dist < best_distance:
                    best_distance = dist
                    primary_boo_event_space = boo_event_space_index

    star_indices = get_star_indices(board)

    show_next_star_fn = "show_next_star_spot" if star_indices else "show_next_star_no_op"
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

    # We want to get the important details about the gate event
    # spaces - only the ones that are the "entry" data.
    gate_id = event_id(Gate)
    spaces_with_gate_events = get_spaces_with_event(gate_id, board)
    gate_event_infos = []

    def _already_added_gate_event_info(gate_space_index):
        return any(info["gateSpaceIndex"] == gate_space_index for info in gate_event_infos)

    for space_index in spaces_with_gate_events:
        gate_event_space = board["spaces"][space_index]

        def _visit(event, event_index, space=None, space_index=None):
            if event["id"] != gate_id:
                return
            if space is not gate_event_space:
                return
            parameter_values = event.get("parameterValues") or {}
            gate_space_index = parameter_values.get("gateSpaceIndex")
            if not _already_added_gate_event_info(gate_space_index):
                gate_event_infos.append({
                    "gateEntryIndex": parameter_values.get("gateEntryIndex"),
                    "gateSpaceIndex": gate_space_index,
                    "gateExitIndex": parameter_values.get("gateExitIndex"),
                    "gatePrevChain": parameter_values.get("gatePrevChain"),
                    "gateNextChain": parameter_values.get("gateNextChain"),
                })

        for_each_event(board, _visit)
    for _ in range(2):  # Ensure at least 2
        if len(gate_event_infos) < 2:
            gate_event_infos.append({
                "gateEntryIndex": get_dead_space_index(board),
                "gateSpaceIndex": get_dead_space_index(board),
                "gateExitIndex": get_dead_space_index(board),
                "gatePrevChain": [0, 0],
                "gateNextChain": [0, 0],
            })

    arrow_rotation_instructions = get_arrow_rotation_instructions(board, Game.MP3_USA)

    mirage_star_enabled = False  # Hard code to false for now.

    additional_bg_indices = get_board_additional_bg_hvq_indices(board)
    prepped_additional_bg_code = get_additional_bg_asm_for_overlay(
        board, board_info["bg_dir"], additional_bg_indices)
    prepped_audio_index_code = get_audio_index_asm_for_overlay(board, audio_indices)

    gate0, gate1 = gate_event_infos[0], gate_event_infos[1]
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
        "best_shop_for_shop_event_spaces_0": best_shop_for_shop_event_spaces[0],
        "best_shop_for_shop_event_spaces_1": best_shop_for_shop_event_spaces[1],
        "board_def_file": board_info.get("board_def_file"),
        "board_index": board_index,
        "boo_count": len(boo_indices),
        "boo_index": boo_index,
        "gate0_entry_index": gate0["gateEntryIndex"],
        "gate0_exit_index": gate0["gateExitIndex"],
        "gate0_next_chain_0": js_at(gate0["gateNextChain"], 0),
        "gate0_next_chain_1": js_at(gate0["gateNextChain"], 1),
        "gate0_prev_chain_0": js_at(gate0["gatePrevChain"], 0),
        "gate0_prev_chain_1": js_at(gate0["gatePrevChain"], 1),
        "gate0_space_index": gate0["gateSpaceIndex"],
        "gate1_entry_index": gate1["gateEntryIndex"],
        "gate1_exit_index": gate1["gateExitIndex"],
        "gate1_next_chain_0": js_at(gate1["gateNextChain"], 0),
        "gate1_next_chain_1": js_at(gate1["gateNextChain"], 1),
        "gate1_prev_chain_0": js_at(gate1["gatePrevChain"], 0),
        "gate1_prev_chain_1": js_at(gate1["gatePrevChain"], 1),
        "gate1_space_index": gate1["gateSpaceIndex"],
        "gate_count": len(gate_event_infos),
        "gate_space_indices": js_join([info["gateSpaceIndex"] for info in gate_event_infos]),
        "item_shop_count": len(item_shop_spaces),
        "item_shop_event_spaces_0": item_shop_event_spaces[0],
        "item_shop_event_spaces_1": item_shop_event_spaces[1],
        "item_shop_spaces": js_join(item_shop_spaces),
        "mainfs_event_dir": main_fs_event_dir,
        "mainfs_event_file": main_fs_event_file,
        "mirage_star_enabled": 1 if mirage_star_enabled else 0,
        "pause_bg_dir": board_info.get("pause_bg_dir"),
        "primary_boo_event_space": primary_boo_event_space,
        "show_next_star_fn": show_next_star_fn,
        "shuffle_bias": js_join(shuffle_data["bias"]),
        "shuffle_order": js_join(shuffle_data["order"]),
        "star_count": len(star_indices),
        "star_indices": js_join(star_indices),
        "star_indices_or_0": js_join(star_indices) or 0,
        "sym_EventTableHydrate": get_symbol(Game.MP3_USA, "EventTableHydrate"),
        "sym_FreeMainFS": get_symbol(Game.MP3_USA, "FreeMainFS"),
        "sym_ReadMainFS": get_symbol(Game.MP3_USA, "ReadMainFS"),
        "toad_indices_or_0": js_join(toad_indices) or 0,
    })
