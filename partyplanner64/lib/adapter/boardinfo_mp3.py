"""MP3 (U) board infos (port of adapter/boardinfo.MP3.ts)."""

from ..types import BoardType
from .boardinfobase import create_board_info


def _make_on_load(get_info):
    def on_load(board):
        from ..romhandler import romhandler
        hvqfs = romhandler.get_rom().get_hvqfs()
        board["otherbg"]["largescene"] = hvqfs.read_background(get_info()["bg_dir"] + 1)["src"]
    return on_load


# Chilly Waters - (U) ROM
MP3_CHILLY = create_board_info("MP3_CHILLY", {
    "name": "Chilly Waters",
    "can_overwrite": True,
    "board_def_file": 570,
    "bg_dir": 3,
    "pause_bg_dir": 5,
    "str": {
        "board_select": [
            [21, 30],
            [26, 17],
        ],
        "board_greeting": [24, 12],
        "board_greeting_duel": [24, 0],
        "board_names": [
            [49, 39],
            [83, 43],
            # [93, 23], This is the songs list, so we can leave it
        ],
    },
    "img": {
        "board_select_img": 72,
        "splash_logo_img": 22,
        "splash_logo_text_img": 28,
        "pause_logo_img": 125,
        "stats_logo_img": [19, 105],
        "gate_img": 354,  # dir 19
    },
    "scene_index": 0x48,
    "mainfs_event_file": [19, 618],
    "mainfs_board_file": [19, 619],
    "event_asm_start": 0x14AF0,  # 0x00330000 // ballpark, but this is wrong -> // 0x0031E814, // is this 0x8011A490 ?
    "event_asm_end": 0x16BEC,  # 0x003320FC, 0x8011C58C
    # spaceEventsStartAddr: 0x0011E718,
    # spaceEventsStartOffset: 0x00334288,
    # spaceEventsEndOffset: 0x18F18, // 0x00334428,
    "space_event_tables": [
        {"upper": 0x26A8, "lower": 0x26B0},  # 0x80108048, 0x80108050, table 0x8011E2CC
        {"upper": 0x26B4, "lower": 0x26BC},  # 0x80108054, 0x8010805C, table 0x8011E718
        # { upper: 0x31DBD0, lower: 0x31DBD8 }, // 0x80108060, 0x80108068 // This is not a table actually, it is related to the happening spaces
        {"upper": 0x26CC, "lower": 0x26D4},  # 0x8010806C, 0x80108074, table 0x8011E344
        # A table, but if we remove it Poison Shrooms break and probably other things
        # { upper: 0x31DBE8, lower: 0x31DBF0 }, // 0x80108078, 0x80108080, table 0x8011E4D8
    ],
    "star_space_arr_offset": [0x17910, 0x17980],  # [0x00332E20, 0x00332E90] // 0x8011D2B0, 0x8011D320
    "star_space_count": 8,
    "toad_space_arr_offset": [0x17920, 0x179DC],  # [0x00332E30, 0x00332EEC] // 0x8011D2C0, 0x8011D37C
    "bank_arr_offset": [0x17B64],  # [0x00333074] // 0x8011D504
    "bank_coin_arr_offset": [0x17A00],  # [0x00332F10] // 0x8011D3A0
    "bank_count": 2,
    "item_shop_arr_offset": [0x17B68],  # [0x00333078] // 0x8011D508
    "item_shop_count": 2,
    "boo_arr_offset": [0x179FC],  # [0x00332F0C] // 0x8011D39C
    "boo_count": 1,
    "gate_neighbors_offset": [0x179D4],  # [0x00332EE4] // 0x8011D374
    "gate_arr_offset": [0x17A7C],  # [0x00332F8C] // 0x8011D41C
    "gate_count": 2,
    "arrow_rot_start_offset": 0x2398,  # 0x0031D8A8 // 0x80107D38
    "arrow_rot_end_offset": 0x2440,  # 0x0031D950 // 0x80107DDC
    "audio_index_offset": 0x2682,  # 0x0031DB92 // 0x80108022

    "on_load": _make_on_load(lambda: MP3_CHILLY),
})

# Deep Bloober Sea - (U) ROM
MP3_BLOOBER = create_board_info("MP3_BLOOBER", {
    "name": "Deep Bloober Sea",
    "can_overwrite": True,
    "board_def_file": 571,
    "bg_dir": 6,
    "pause_bg_dir": 8,
    "str": {
        "board_select": [
            [21, 31],
            [26, 18],
        ],
        "board_greeting": [24, 13],
        "board_greeting_duel": [24, 2],
        "board_names": [
            [49, 40],
            [83, 44],
            # [93, 24], This is the songs list, so we can leave it
        ],
    },
    "img": {
        "board_select_img": 73,
        "splash_logo_img": 23,
        "splash_logo_text_img": 29,
        "pause_logo_img": 126,
        "stats_logo_img": [19, 106],
        "gate_img": 359,  # dir 19
    },
    "scene_index": 0x49,
    "mainfs_event_file": [19, 620],
    "mainfs_board_file": [19, 621],

    "on_load": _make_on_load(lambda: MP3_BLOOBER),
})
# Works, but needs other values to parse right:
# spaceEventTables = [
#   { upper: 0x003377C0, lower: 0x003377C8 }, // 0x80107B80, 0x80107B88, table 0x8011D688
#   { upper: 0x003377CC, lower: 0x003377D4 }, // 0x80107B8C, 0x80107B94, table 0x8011D9CC
#   // 0x800F8D48 call in between
#   { upper: 0x003377E4, lower: 0x003377EC }, // 0x80107BA4, 0x80107BAC, table 0x8011D700
#   { upper: 0x003377F0, lower: 0x003377F8 }, // 0x80107BB0, 0x80107BB8, table 0x8011D894
# ];

# Spiny Desert - (U) ROM
MP3_SPINY = create_board_info("MP3_SPINY", {
    "name": "Spiny Desert",
    "can_overwrite": True,
    "board_def_file": 572,
    "bg_dir": 9,
    "pause_bg_dir": 11,
    "str": {
        "board_select": [
            [21, 32],
            [26, 19],
        ],
        "board_greeting": [24, 14],
        "board_greeting_duel": [24, 4],
        "board_names": [
            [49, 41],
            [83, 45],
            # [93, 25], This is the songs list, so we can leave it
        ],
    },
    "img": {
        "board_select_img": 74,
        "splash_logo_img": 24,
        "splash_logo_text_img": 30,
        "pause_logo_img": 127,
        "stats_logo_img": [19, 107],
        "gate_img": 366,  # dir 19
    },

    "scene_index": 0x4A,
    "mainfs_event_file": [19, 622],
    "mainfs_board_file": [19, 623],

    "on_load": _make_on_load(lambda: MP3_SPINY),
})

# Woody Woods - (U) ROM
MP3_WOODY = create_board_info("MP3_WOODY", {
    "name": "Woody Woods",
    "can_overwrite": True,
    "board_def_file": 573,
    "bg_dir": 12,
    "pause_bg_dir": 14,
    "str": {
        "board_select": [
            [21, 33],
            [26, 20],
        ],
        "board_greeting": [24, 15],
        "board_greeting_duel": [24, 6],
        "board_names": [
            [49, 42],
            [83, 46],
            # [93, 26], This is the songs list, so we can leave it
        ],
    },
    "img": {
        "board_select_img": 75,
        "splash_logo_img": 25,
        "splash_logo_text_img": 31,
        "pause_logo_img": 128,
        "stats_logo_img": [19, 108],
        "gate_img": 373,  # dir 19
    },

    "scene_index": 0x4B,
    "mainfs_event_file": [19, 624],
    "mainfs_board_file": [19, 625],

    "on_load": _make_on_load(lambda: MP3_WOODY),
})

# Creepy Cavern - (U) ROM
MP3_CAVERN = create_board_info("MP3_CAVERN", {
    "name": "Creepy Cavern",
    "can_overwrite": True,
    "board_def_file": 574,
    "bg_dir": 15,
    "pause_bg_dir": 17,
    "str": {
        "board_select": [
            [21, 34],
            [26, 21],
        ],
        "board_greeting": [24, 16],
        "board_greeting_duel": [24, 8],
        "board_names": [
            [49, 43],
            [83, 47],
            # [93, 27], This is the songs list, so we can leave it
        ],
    },
    "img": {
        "board_select_img": 76,
        "splash_logo_img": 26,
        "splash_logo_text_img": 32,
        "pause_logo_img": 129,
        "stats_logo_img": [19, 109],
        "gate_img": 383,  # dir 19
    },

    "scene_index": 0x4C,
    "mainfs_event_file": [19, 626],
    "mainfs_board_file": [19, 627],

    "on_load": _make_on_load(lambda: MP3_CAVERN),
})

# Waluigi's Land - (U) ROM
MP3_WALUIGI = create_board_info("MP3_WALUIGI", {
    "name": "Waluigi's Land",
    "can_overwrite": True,
    "board_def_file": 575,
    "bg_dir": 18,
    "pause_bg_dir": 20,
    "str": {
        "board_select": [
            [21, 35],
            [26, 22],
        ],
        "board_greeting": [24, 17],
        "board_greeting_duel": [24, 10],
        "board_names": [
            [49, 44],
            [83, 48],
            # [93, 28], This is the songs list, so we can leave it
        ],
    },
    "img": {
        "board_select_img": 77,
        "splash_logo_img": 27,
        "splash_logo_text_img": 33,
        "pause_logo_img": 130,
        "stats_logo_img": [19, 110],
        "gate_img": 387,  # dir 19
    },

    "scene_index": 0x4D,
    "mainfs_event_file": [19, 628],
    "mainfs_board_file": [19, 629],

    "on_load": _make_on_load(lambda: MP3_WALUIGI),
})

# Gate Guy - (U) ROM
MP3U_GATEGUY = create_board_info("MP3U_GATEGUY")
MP3U_GATEGUY["name"] = "Gate Guy"
MP3U_GATEGUY["type"] = BoardType.DUEL
MP3U_GATEGUY["board_def_file"] = 577
MP3U_GATEGUY["bg_dir"] = 24
# MP3U_GATEGUY.str = {
#   boardSelect: [
#     [36, 21],
#     [41, 27],
#   ],
#   boardNames: [
#     [49, 45],
#     [39, 1],
#     [83, 49],
#   ],
# };
MP3U_GATEGUY["img"] = {
    "board_select_img": 81,
    "splash_logo_img": 34,
    "splash_logo_text_img": 40,
    "mini_map_with_bg": 279,  # dir 19
    "mini_map_dots": 280,
}
MP3U_GATEGUY["scene_index"] = 0x5B
# MP3U_GATEGUY.spaceEventsStartAddr = 0x00118914;
# MP3U_GATEGUY.spaceEventsStartOffset = 0x003EBA04;
MP3U_GATEGUY["space_event_tables"] = [
    # JAL 800EA46C
    {"upper": 0x811C, "lower": 0x8124},  # 0x8010DABC, 0x8010DAC4, table 0x80118914
    {"upper": 0x8128, "lower": 0x8130},  # 0x8010DAC8, 0x8010DAD0, table 0x80118DEC
]


def _gateguy_on_after_overwrite(board=None):
    # TODO Need this for duels?
    # This code (right inbetween 800EBA60 calls) sets up a function pointer for happening spaces.
    # Since we don't use any default events, we can overwrite it.
    # romView.setUint32(, 0);
    # romView.setUint32(, 0);
    # romView.setUint32(, 0);
    # TODO: Probably some stuff to NOP around 0x8010DA9C
    pass


MP3U_GATEGUY["on_after_overwrite"] = _gateguy_on_after_overwrite

# Arrowhead - (U) ROM
MP3U_ARROWHEAD = create_board_info("MP3U_ARROWHEAD")
MP3U_ARROWHEAD["name"] = "Arrowhead"
MP3U_ARROWHEAD["type"] = BoardType.DUEL
MP3U_ARROWHEAD["board_def_file"] = 578
MP3U_ARROWHEAD["bg_dir"] = 25
MP3U_ARROWHEAD["img"] = {
    "board_select_img": 82,
    "splash_logo_img": 35,
    "splash_logo_text_img": 41,
    "mini_map_with_bg": 310,  # dir 19
    "mini_map_dots": 311,
}

# Pipesqueak - (U) ROM
MP3U_PIPESQUEAK = create_board_info("MP3U_PIPESQUEAK")
MP3U_PIPESQUEAK["name"] = "Pipesqueak"
MP3U_PIPESQUEAK["type"] = BoardType.DUEL
MP3U_PIPESQUEAK["board_def_file"] = 579
MP3U_PIPESQUEAK["bg_dir"] = 26
MP3U_PIPESQUEAK["img"] = {
    "board_select_img": 83,
    "splash_logo_img": 36,
    "splash_logo_text_img": 42,
    "mini_map_with_bg": 312,  # dir 19
    "mini_map_dots": 313,
}

# Blowhard - (U) ROM
MP3U_BLOWHARD = create_board_info("MP3U_BLOWHARD")
MP3U_BLOWHARD["name"] = "Blowhard"
MP3U_BLOWHARD["type"] = BoardType.DUEL
MP3U_BLOWHARD["board_def_file"] = 580
MP3U_BLOWHARD["bg_dir"] = 27
MP3U_BLOWHARD["img"] = {
    "board_select_img": 84,
    "splash_logo_img": 37,
    "splash_logo_text_img": 43,
    "mini_map_with_bg": 315,  # dir 19
    "mini_map_dots": 316,
}

# Mr. Mover - (U) ROM
MP3U_MRMOVER = create_board_info("MP3U_MRMOVER")
MP3U_MRMOVER["name"] = "Mr. Mover"
MP3U_MRMOVER["type"] = BoardType.DUEL
MP3U_MRMOVER["board_def_file"] = 581
MP3U_MRMOVER["bg_dir"] = 28
MP3U_MRMOVER["img"] = {
    "board_select_img": 85,
    "splash_logo_img": 38,
    "splash_logo_text_img": 44,
    "mini_map_with_bg": 317,  # dir 19
    "mini_map_dots": 318,
}

# Backtrack - (U) ROM
MP3U_BACKTRACK = create_board_info("MP3U_BACKTRACK")
MP3U_BACKTRACK["name"] = "Backtrack"
MP3U_BACKTRACK["type"] = BoardType.DUEL
MP3U_BACKTRACK["board_def_file"] = 582
MP3U_BACKTRACK["bg_dir"] = 29
MP3U_BACKTRACK["img"] = {
    "board_select_img": 86,
    "splash_logo_img": 39,
    "splash_logo_text_img": 45,
    "mini_map_with_bg": 319,  # dir 19
    "mini_map_dots": 320,
}


def get_board_infos():
    return [
        MP3_CHILLY,
        MP3_BLOOBER,
        MP3_SPINY,
        MP3_WOODY,
        MP3_CAVERN,
        MP3_WALUIGI,

        MP3U_GATEGUY,
        MP3U_ARROWHEAD,
        MP3U_PIPESQUEAK,
        MP3U_BLOWHARD,
        MP3U_MRMOVER,
        MP3U_BACKTRACK,
    ]

# Other board defs (from the original):
#   Training?: fileNum 576, bgNum 21
#   mystery: fileNum 583, bgNum 30
