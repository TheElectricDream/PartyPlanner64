"""MP1 (J) board infos (port of adapter/boardinfo.MP1.J.ts)."""

from .boardinfobase import create_board_info

# DK's Jungle Adventure - (J) ROM
MP1_JPN_DK = create_board_info("MP1_JPN_DK")
MP1_JPN_DK["name"] = "DK's Jungle Adventure"
MP1_JPN_DK["board_def_file"] = 69
MP1_JPN_DK["bg_dir"] = 0
MP1_JPN_DK["str"] = {
    "board_select": 652,
    "koopa_intro": 571,
    "star_comments": [286, 287, 288, 289, 290, 291, 292],
}
MP1_JPN_DK["img"] = {
    "board_select_img": 17,
    "pause_logo_img": 276,
    "intro_logo_img": [356, 357],
    "title_screen_img": 385,
}
MP1_JPN_DK["event_asm_start"] = 0x00
MP1_JPN_DK["event_asm_end"] = 0x00
# MP1_JPN_DK.spaceEventsStartAddr = 0x000F951C;
# MP1_JPN_DK.spaceEventsStartOffset = 0x002448BC;
# MP1_JPN_DK.spaceEventsEndOffset = 0x00244A20;


def get_board_infos():
    return [
        MP1_JPN_DK,
        # MP1_J_PEACH,
        # MP1_J_YOSHI,
        # MP1_J_WARIO,
        # MP1_J_LUIGI,
        # MP1_J_MARIO,
        # MP1_J_BOWSER,
        # MP1_J_ETERNALSTAR,
        # MP1_J_TRAINING,
        # MP1_J_ISLAND,
        # MP1_J_STADIUM,
    ]
