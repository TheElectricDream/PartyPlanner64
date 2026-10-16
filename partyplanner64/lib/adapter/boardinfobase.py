"""Board infos: known facts about each game board (port of adapter/boardinfobase.ts).

BoardInfos are a PP64-specific object that represents known info about each
game board. Here a board info is a dict with snake_case keys (the
IBoardInfo fields by the naming rule):

    on_load(board)            Called when the board is being parsed.
    on_after_overwrite(board) Called after the board has been written to ROM.
    on_write_events(board)    Called prior to writing events.

    name, type, can_overwrite, board_def_file, bg_dir, pause_bg_dir,
    anim_bg_set, costume_type,
    str: {board_select, board_names, board_greeting, board_greeting_duel,
          board_winner, board_play_count, koopa_intro, star_comments},
    img: {board_select_img, board_select_icon_coords, board_select_icon_mask,
          pause_logo_img, stats_logo_img, intro_logo_img, intro_logo_img_dimens,
          title_screen_img, splash_logo_img, splash_logo_text_img, gate_img,
          mini_map_with_bg, mini_map_dots},
    scene_index, mainfs_event_file, mainfs_board_file, event_asm_start,
    event_asm_end, space_event_tables, koopa_space_inst, bowser_space_inst,
    goomba_space_inst, boo_space_inst, boos_loop_fn_offset,
    boos_readback_fn_offset, boo_count, boo_arr_offset, star_space_arr_offset,
    star_space_count, toad_space_inst, toad_space_arr_offset,
    audio_index_offset, bank_arr_offset, bank_coin_arr_offset, bank_count,
    item_shop_arr_offset, item_shop_count, arrow_rot_start_offset,
    arrow_rot_end_offset, gate_neighbors_offset, gate_arr_offset, gate_count

Optional fields are absent when not set: read them with .get().
"""

_board_infos = {}


def create_board_info(id, props=None):
    """Create (and register) a board info dict."""
    if id in _board_infos:
        raise ValueError("Cannot create an already existing BoardInfo %s." % id)
    board_info = {}
    if props:
        board_info.update(props)
    _board_infos[id] = board_info
    return board_info


dummy_board_info = {
    "name": "Test Info",
    "board_def_file": 1,
    "bg_dir": 1,
    "str": {},
    "img": {},
}
