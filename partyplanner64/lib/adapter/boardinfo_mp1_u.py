"""MP1 (U) board infos (port of adapter/boardinfo.MP1.U.ts)."""

from .boardinfobase import create_board_info


def _rom():
    from ..romhandler import romhandler
    return romhandler.get_rom()


def _blank_pack(dir, file, width, height):
    """Replace an image pack's image with a transparent one."""
    from ..utils.img.img_pack import to_pack
    mainfs = _rom().get_main_fs()
    old_pack = mainfs.get(dir, file)
    img_info_arr = [
        {"src": bytearray(width * height * 4), "width": width, "height": height, "bpp": 32},
    ]
    new_pack = to_pack(img_info_arr, 16, 0, old_pack)
    mainfs.write(dir, file, new_pack)


# DK's Jungle Adventure - (U) ROM
def _dk_on_load(board):
    hvqfs = _rom().get_hvqfs()
    board["otherbg"]["largescene"] = hvqfs.read_background(MP1_USA_DK["bg_dir"] + 1)["src"]
    board["otherbg"]["conversation"] = hvqfs.read_background(MP1_USA_DK["bg_dir"] + 2)["src"]
    board["otherbg"]["splashscreen"] = hvqfs.read_background(MP1_USA_DK["bg_dir"] + 6)["src"]


def _dk_on_after_overwrite(board=None):
    from ..fs.strings import str_to_bytes
    from ..utils.arrays import array_to_array_buffer

    # Remove the "box" from the game start scenery.
    scenes = _rom().get_scenes()
    intro_scene_view = scenes.get_data_view(98)
    intro_scene_view.set_uint32(0x7098, 0xC57A0000)  # 0x2A9598 // Some random float to get it away
    intro_scene_view.set_uint32(0x709C, 0)  # 0x2A959C
    intro_scene_view.set_uint32(0x70A0, 0)  # 0x2A95A0

    # Make Bowser's event text a bit more generic.
    bytes_ = []
    strings = _rom().get_strings()
    bytes_ = bytes_ + str_to_bytes("You're looking for Stars?\nHow about this instead...")
    bytes_.append(0xFF)  # PAUSE
    bytes_.append(0x00)  # Null byte
    str_buffer = array_to_array_buffer(bytes_)
    strings.write(396, str_buffer)
    strings.write(399, str_buffer)
    strings.write(402, str_buffer)


MP1_USA_DK = create_board_info("MP1_USA_DK", {
    "name": "DK's Jungle Adventure",
    "can_overwrite": True,
    "board_def_file": 69,
    "bg_dir": 0,
    "pause_bg_dir": 4,
    "scene_index": 0x36,  # 54
    "mainfs_event_file": [10, 422],
    "mainfs_board_file": [10, 423],
    "koopa_space_inst": 0xD54,  # 0x002425F4, 0x800F7330
    "bowser_space_inst": 0xCB8,  # 0x00242558
    "boos_loop_fn_offset": 0x11D8,  # 0x00242A78
    "boos_readback_fn_offset": 0x10D0,  # 0x00242970
    "star_space_arr_offset": 0x3320,  # 0x00244BC0
    "star_space_count": 7,
    "toad_space_arr_offset": [0x3330, 0x3348],  # [0x00244BD0, 0x00244BE8]
    "audio_index_offset": 0xBBE,  # 0x0024245E
    "str": {
        "board_select": 652,
        "koopa_intro": 571,
        "star_comments": [286, 287, 288, 289, 290, 291, 292],
    },
    "img": {
        "board_select_img": 17,

        # gamemasterplc: overwrite ROM offset 0x25FA08 with 0x006B0226 to hide the comic sans board logo far off the bottom of the screen
        "pause_logo_img": 276,
        "intro_logo_img": [356, 357],
        "intro_logo_img_dimens": [272, 112],
        "title_screen_img": 385,
    },

    "on_load": _dk_on_load,
    "on_after_overwrite": _dk_on_after_overwrite,
})

# spaceEventTables: [
#   { upper: 0xBD0, lower: 0xBD8 }, // 0x800F71B0, 0x800F71B8
#   { upper: 0xBEC, lower: 0xBF4 }, // 0x800F71CC, 0x800F71D4
#   { upper: 0xC08, lower: 0xC10 }, // 0x800F71E8, 0x800F71F0
#   { upper: 0xC24, lower: 0xC2C }, // 0x800F7204, 0x800F720C
#   // tables: 0x800FA0CC
# ];


# Peach's Birthday Cake - (U) ROM
def _peach_on_load(board):
    hvqfs = _rom().get_hvqfs()
    board["otherbg"]["largescene"] = hvqfs.read_background(MP1_USA_PEACH["bg_dir"] + 1)["src"]
    board["otherbg"]["conversation"] = hvqfs.read_background(MP1_USA_PEACH["bg_dir"] + 2)["src"]
    board["otherbg"]["splashscreen"] = hvqfs.read_background(MP1_USA_PEACH["bg_dir"] + 10)["src"]


def _peach_on_after_overwrite(board=None):
    # Text banner that appears over the logo
    _blank_pack(10, 360, 250, 50)

    # TODO: There's some cake graphics in the end cutscenes that could be wiped.


MP1_USA_PEACH = create_board_info("MP1_USA_PEACH", {
    "name": "Peach's Birthday Cake",
    "can_overwrite": True,
    "board_def_file": 70,
    "bg_dir": 7,
    "pause_bg_dir": 14,
    "str": {
        "board_select": 653,
        "koopa_intro": 572,
    },
    "img": {
        "board_select_img": 20,
        "pause_logo_img": 277,
        "intro_logo_img": [359],
        "intro_logo_img_dimens": [284, 126],
        "title_screen_img": 382,
    },
    "scene_index": 0x37,  # 55
    "mainfs_event_file": [10, 424],
    "mainfs_board_file": [10, 425],
    "event_asm_start": 0x00,
    # spaceEventsStartAddr: 0x000F7C70
    # spaceEventsStartOffset: 0x00246C50
    # spaceEventsEndOffset: 0x00246D10
    "koopa_space_inst": 0x7C0,  # 0x00245D80
    "bowser_space_inst": 0x988,  # // 0x00245F48
    "goomba_space_inst": 0x900,  # 0x00245EC0

    "on_load": _peach_on_load,
    "on_after_overwrite": _peach_on_after_overwrite,
})


# Yoshi's Tropical Island - (U) ROM
def _yoshi_on_load(board):
    hvqfs = _rom().get_hvqfs()
    board["otherbg"]["largescene"] = hvqfs.read_background(MP1_USA_YOSHI["bg_dir"] + 1)["src"]
    board["otherbg"]["conversation"] = hvqfs.read_background(MP1_USA_YOSHI["bg_dir"] + 2)["src"]
    board["otherbg"]["splashscreen"] = hvqfs.read_background(MP1_USA_YOSHI["bg_dir"] + 8)["src"]


def _yoshi_on_after_overwrite(board=None):
    # Text banner that appears over the logo
    _blank_pack(10, 363, 208, 40)

    # TODO: Yoshis and whirlpools in the intro board showing
    # TODO: Koopa Troopa rides a shell into the intro


MP1_USA_YOSHI = create_board_info("MP1_USA_YOSHI", {
    "name": "Yoshi's Tropical Island",
    "can_overwrite": True,
    "board_def_file": 71,
    "bg_dir": 18,
    "pause_bg_dir": 25,
    "str": {
        "board_select": 654,
        "koopa_intro": 573,
    },
    "img": {
        "board_select_img": 18,
        "pause_logo_img": 278,
        "intro_logo_img": [362],
        "intro_logo_img_dimens": [270, 120],
        "title_screen_img": 383,
    },
    "scene_index": 0x38,  # 56
    "mainfs_event_file": [10, 426],
    "mainfs_board_file": [10, 427],
    # spaceEventsStartAddr: 0x000F861C;
    # spaceEventsStartOffset: 0x00248E2C;
    # spaceEventsEndOffset: 0x00248EE4;

    "on_load": _yoshi_on_load,
    "on_after_overwrite": _yoshi_on_after_overwrite,
})


# Wario's Battle Canyon = (U) ROM
def _wario_on_load(board):
    hvqfs = _rom().get_hvqfs()
    board["otherbg"]["largescene"] = hvqfs.read_background(MP1_USA_WARIO["bg_dir"] + 1)["src"]
    board["otherbg"]["conversation"] = hvqfs.read_background(MP1_USA_WARIO["bg_dir"] + 2)["src"]
    board["otherbg"]["splashscreen"] = hvqfs.read_background(MP1_USA_WARIO["bg_dir"] + 11)["src"]


def _wario_on_after_overwrite(board=None):
    # Text banner that appears over the logo
    _blank_pack(10, 366, 280, 76)


MP1_USA_WARIO = create_board_info("MP1_USA_WARIO", {
    "name": "Wario's Battle Canyon",
    "can_overwrite": True,
    "board_def_file": 72,
    "bg_dir": 27,
    "pause_bg_dir": 36,
    "str": {
        "board_select": 655,
        "koopa_intro": 574,
    },
    "img": {
        "board_select_img": 19,
        "pause_logo_img": 279,
        "intro_logo_img": [365],
        "intro_logo_img_dimens": [290, 114],
        "title_screen_img": 384,
    },
    "scene_index": 0x39,  # 57
    "mainfs_event_file": [10, 428],
    "mainfs_board_file": [10, 429],
    # spaceEventsStartAddr: 0x000F99C4,
    # spaceEventsStartOffset: 0x0024C2E4,
    # spaceEventsEndOffset: 0x0024C38C,
    "koopa_space_inst": 0xED0,  # 0x00249DD0,
    "bowser_space_inst": 0xDA8,  # 0x00249CA8,
    "boos_loop_fn_offset": 0x119C,  # 0x0024A09C,
    "boos_readback_fn_offset": 0x1094,  # 0x00249F94,
    "star_space_arr_offset": 0x3240,  # 0x0024C140,
    "star_space_count": 7,
    "toad_space_arr_offset": [0x3250, 0x3270],  # [0x0024C150, 0x0024C170]

    "on_load": _wario_on_load,
    "on_after_overwrite": _wario_on_after_overwrite,
})

# Luigi's Engine Room - (U) ROM
MP1_USA_LUIGI = create_board_info("MP1_USA_LUIGI")
MP1_USA_LUIGI["name"] = "Luigi's Engine Room"
MP1_USA_LUIGI["board_def_file"] = 73
MP1_USA_LUIGI["bg_dir"] = 39
MP1_USA_LUIGI["str"] = {
    "board_select": 656,
    "koopa_intro": 575,
}
MP1_USA_LUIGI["img"] = {
    "board_select_img": 21,
    "pause_logo_img": 280,
    "intro_logo_img": [368],
    "intro_logo_img_dimens": [276, 128],
    "title_screen_img": 381,
}
MP1_USA_LUIGI["scene_index"] = 0x3A  # 58
MP1_USA_LUIGI["event_asm_start"] = 0x00
# MP1_USA_LUIGI.spaceEventsStartAddr = 0x000F9B90;
# MP1_USA_LUIGI.spaceEventsStartOffset = 0x0024F940;
# MP1_USA_LUIGI.spaceEventsEndOffset = 0x0024FA70;
MP1_USA_LUIGI["star_space_arr_offset"] = 0x2F60  # 0x0024F2F0;
MP1_USA_LUIGI["star_space_count"] = 7
MP1_USA_LUIGI["toad_space_arr_offset"] = [0x2F70, 0x2FF4]  # [0x0024F300, 0x0024F384];

# Mario's Rainbow Castle - (U) ROM
MP1_USA_MARIO = create_board_info("MP1_USA_MARIO")
MP1_USA_MARIO["name"] = "Mario's Rainbow Castle"
MP1_USA_MARIO["board_def_file"] = 74
MP1_USA_MARIO["bg_dir"] = 47
MP1_USA_MARIO["str"] = {
    "board_select": 657,
    "koopa_intro": 576,
}
MP1_USA_MARIO["img"] = {
    "board_select_img": 22,
    "pause_logo_img": 281,
    "intro_logo_img": [371],
    "intro_logo_img_dimens": [270, 96],
    "title_screen_img": 380,
}
MP1_USA_MARIO["scene_index"] = 0x3B  # 59
MP1_USA_MARIO["event_asm_start"] = 0x00
# MP1_USA_MARIO.spaceEventsStartAddr = 0x000F8390;
# MP1_USA_MARIO.spaceEventsStartOffset = 0x00251830;
# MP1_USA_MARIO.spaceEventsEndOffset = 0x002518D0;

# Bowser's Magma Mountain - (U) ROM
MP1_USA_BOWSER = create_board_info("MP1_USA_BOWSER")
MP1_USA_BOWSER["name"] = "Bowser's Magma Mountain"
MP1_USA_BOWSER["board_def_file"] = 75
MP1_USA_BOWSER["bg_dir"] = 56
MP1_USA_BOWSER["str"] = {
    "board_select": 658,
    "koopa_intro": 577,
}
MP1_USA_BOWSER["img"] = {
    "board_select_img": 23,
    "pause_logo_img": 282,
    "intro_logo_img": [374],
    "intro_logo_img_dimens": [270, 106],
}
MP1_USA_BOWSER["scene_index"] = 0x3C  # 60
MP1_USA_BOWSER["event_asm_start"] = 0x00
# MP1_USA_BOWSER.spaceEventsStartAddr = 0x000F9080;
# MP1_USA_BOWSER.spaceEventsStartOffset = 0x00254370;
# MP1_USA_BOWSER.spaceEventsEndOffset = 0x00254450;
MP1_USA_BOWSER["star_space_arr_offset"] = 0x2298  # 0x00253B68;
MP1_USA_BOWSER["star_space_count"] = 7
MP1_USA_BOWSER["toad_space_arr_offset"] = [0x22A8, 0x22C8]  # [0x00253B78, 0x00253B98];

# Eternal Star - (U) ROM
MP1_USA_ETERNALSTAR = create_board_info("MP1_USA_ETERNALSTAR")
MP1_USA_ETERNALSTAR["name"] = "Eternal Star"
MP1_USA_ETERNALSTAR["board_def_file"] = 76
MP1_USA_ETERNALSTAR["bg_dir"] = 68
MP1_USA_ETERNALSTAR["str"] = {
    "board_select": [659, 660],
    "koopa_intro": 578,
}
MP1_USA_ETERNALSTAR["img"] = {
    "board_select_img": 24,
    "pause_logo_img": 283,
    "intro_logo_img": [378],
    # introLogoImgDimens: [276, 92], // The text  377
    # introLogoImgDimens: [252, 128], // The star  378
}
MP1_USA_ETERNALSTAR["scene_index"] = 0x3D  # 61
MP1_USA_ETERNALSTAR["event_asm_start"] = 0x00
# MP1_USA_ETERNALSTAR.spaceEventsStartAddr = 0x000F905C;
# MP1_USA_ETERNALSTAR.spaceEventsStartOffset = 0x00256ECC;
# MP1_USA_ETERNALSTAR.spaceEventsEndOffset = 0x00256FF0;
MP1_USA_ETERNALSTAR["bowser_space_inst"] = 0xDDC  # 0x0025522C;
MP1_USA_ETERNALSTAR["star_space_arr_offset"] = 0x25F0  # 0x00256A40;
MP1_USA_ETERNALSTAR["star_space_count"] = 7
MP1_USA_ETERNALSTAR["toad_space_arr_offset"] = 0x2600  # 0x00256A50;

# Training - (U) ROM
MP1_USA_TRAINING = create_board_info("MP1_USA_TRAINING")
MP1_USA_TRAINING["name"] = "Training"
MP1_USA_TRAINING["board_def_file"] = 77
MP1_USA_TRAINING["bg_dir"] = 77
MP1_USA_TRAINING["str"] = {}
MP1_USA_TRAINING["img"] = {}
MP1_USA_TRAINING["scene_index"] = 0x3E  # 62
MP1_USA_TRAINING["event_asm_start"] = 0x00
# MP1_USA_TRAINING.spaceEventsStartAddr = 0x000F87A8;
# MP1_USA_TRAINING.spaceEventsStartOffset = 0x002591B8;
# MP1_USA_TRAINING.spaceEventsEndOffset = 0x002591E8;
MP1_USA_TRAINING["bowser_space_inst"] = 0x32C  # 0x0025731C;
MP1_USA_TRAINING["toad_space_inst"] = 0x16C  # 0x0025715C;
MP1_USA_TRAINING["koopa_space_inst"] = 0x1F4  # 0x002571E4;
MP1_USA_TRAINING["boo_space_inst"] = 0x2A4  # 0x00257294;

# Mini-Game Stadium - (U) ROM
MP1_USA_STADIUM = create_board_info("MP1_USA_STADIUM")
MP1_USA_STADIUM["name"] = "Mini-Game Stadium"
MP1_USA_STADIUM["board_def_file"] = 83
MP1_USA_STADIUM["bg_dir"] = 99
MP1_USA_STADIUM["str"] = {}
MP1_USA_STADIUM["img"] = {}
# MP1_USA_STADIUM.sceneIndex = 0x3F; // 63

# Mini-Game Island - (U) ROM
MP1_USA_ISLAND = create_board_info("MP1_USA_ISLAND")
MP1_USA_ISLAND["name"] = "Mini-Game Island"
MP1_USA_ISLAND["board_def_file"] = 78
MP1_USA_ISLAND["bg_dir"] = 79
MP1_USA_ISLAND["str"] = {}
MP1_USA_ISLAND["img"] = {}
MP1_USA_ISLAND["scene_index"] = 0x72  # 114
MP1_USA_ISLAND["event_asm_start"] = 0x00
# MP1_USA_ISLAND.spaceEventsStartAddr = 0x000F8448;
# MP1_USA_ISLAND.spaceEventsStartOffset = 0x002F8EE8;
# MP1_USA_ISLAND.spaceEventsEndOffset = 0x002F9040;


def get_board_infos():
    return [
        MP1_USA_DK,
        MP1_USA_PEACH,
        MP1_USA_YOSHI,
        MP1_USA_WARIO,
        MP1_USA_LUIGI,
        MP1_USA_MARIO,
        MP1_USA_BOWSER,
        MP1_USA_ETERNALSTAR,
        MP1_USA_TRAINING,
        MP1_USA_ISLAND,
        MP1_USA_STADIUM,
    ]
