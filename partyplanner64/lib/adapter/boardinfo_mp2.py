"""MP2 (U) board infos (port of adapter/boardinfo.MP2.ts)."""

from ..types import CostumeType
from ..utils.dataview import DataView
from .boardinfobase import create_board_info


def _rom():
    from ..romhandler import romhandler
    return romhandler.get_rom()


# Western Land - (U) ROM
def _western_on_load(board):
    hvqfs = _rom().get_hvqfs()
    board["otherbg"]["largescene"] = hvqfs.read_background(MP2_WESTERN["bg_dir"] + 2)["src"]


def _western_on_after_overwrite(board=None):
    from ..fs.strings import str_to_bytes
    from ..utils.arrays import array_to_array_buffer
    from ..utils.img.img_pack import to_pack

    # Skip Bowser the Brash fight scene
    # 0x004F is the Bowser scene, 0x0051 is the results scene.
    # To debug, end game early with 0x800F93AF (turn count)
    # Then watch scene change 0x800FA63C
    scenes = _rom().get_scenes()
    scene_end_view = scenes.get_data_view(82)
    scene_end_view.set_uint16(0x2E0E, 0x0051)  # 0x8010560C, 0x35BBEE

    # Then, make the scared Koopa's message at the endgame be more chill.
    strings = _rom().get_strings()
    bytes_ = []
    bytes_.append(0x0B)
    bytes_ = bytes_ + str_to_bytes("Don't listen to Toad!")
    bytes_.append(0x0A)  # \n
    bytes_ = bytes_ + str_to_bytes("I've got the results. Follow me!")
    bytes_.append(0x00)  # Null byte
    strings.write(697, array_to_array_buffer(bytes_))

    # Hide some intro scene graphics
    # Bowser sign
    mainfs = _rom().get_main_fs()
    old_pack = mainfs.get(10, 410)
    img_info_arr = [
        {"src": bytearray(144 * 128 * 4), "width": 144, "height": 128, "bpp": 32},
    ]
    new_pack = to_pack(img_info_arr, 16, 0, old_pack)
    mainfs.write(10, 410, new_pack)

    # Hole in ground that Bowser sign sticks into
    old_pack = mainfs.get(10, 411)
    img_info_arr = [
        {"src": bytearray(32 * 16 * 4), "width": 32, "height": 16, "bpp": 32},
    ]
    new_pack = to_pack(img_info_arr, 16, 0, old_pack)
    mainfs.write(10, 411, new_pack)

    # (unused) Dust in the wind or whatever it is called
    old_pack = mainfs.get(10, 412)
    img_info_arr = [
        {"src": bytearray(64 * 64 * 4), "width": 64, "height": 64, "bpp": 32},
    ]
    new_pack = to_pack(img_info_arr, 16, 0, old_pack)
    mainfs.write(10, 412, new_pack)

    # Train that rides across, model files can be blanked out
    # Cannot just blank model, does not work on console.
    # mainfs.write(10, 394, new ArrayBuffer(0x200));
    form = bytearray(mainfs.get(10, 394))
    form_view = DataView(form)
    form_view.set_uint16(0x1FC, 0)
    form_view.set_uint16(0x1106, 0)
    mainfs.write(10, 394, form)

    # mainfs.write(10, 395, new ArrayBuffer(0x200));
    form = bytearray(mainfs.get(10, 395))
    form_view = DataView(form)
    form_view.set_uint16(0x204, 0)
    form_view.set_uint16(0x616, 0)
    mainfs.write(10, 395, form)


MP2_WESTERN = create_board_info("MP2_WESTERN", {
    "name": "Western Land",
    "can_overwrite": True,
    "board_def_file": 64,
    "bg_dir": 2,
    "anim_bg_set": 0,
    "costume_type": CostumeType.WESTERN,
    "str": {
        "board_select": 197,
        "board_names": [190, 210],
        "board_greeting": [1248, 1249],
        "board_winner": 707,
        "board_play_count": 1327,
    },
    "img": {
        "intro_logo_img": 406,
        "pause_logo_img": 380,
        "board_select_img": 30,
        "board_select_icon_coords": [39, 20],
        "board_select_icon_mask": 20,
    },
    "mainfs_event_file": [10, 682],
    "mainfs_board_file": [10, 683],
    "scene_index": 0x3E,  # 62
    # First I tried 0x0029CF24 / 0x80107C54, but then I included the star event
    # at 0x0029E91C / 0x80?. But then, using items NOP sledded, and I found a mystery
    # table at 0x800DF720 that suggests I should use this actually:
    "event_asm_start": 0xD350,  # 0x8010FB50, 0x002A4E20
    "event_asm_end": 0xEAE4,  # 0x801112E4, 0x002A65B4
    # spaceEventsStartAddr: 0x0011280C,
    # spaceEventsStartOffset: 0x002A7ADC,
    # spaceEventsEndOffset: 0x002A7BE0,
    "space_event_tables": [
        {"upper": 0x33EC, "lower": 0x33F4},  # 0x80105BEC, 0x80105BF4, table 0x80112484
        {"upper": 0x33F8, "lower": 0x3400, "primary": True},  # 0x80105BF8, 0x80105C00, table 0x8011280C
        {"upper": 0x3404, "lower": 0x340C},  # 0x80105C04, 0x80105C0C, table 0x801124EC
    ],
    "star_space_arr_offset": [0xF184, 0xF1F4],  # [0x002A6C54, 0x002A6CC4], // 0x80111984, 0x801119F4
    "star_space_count": 7,
    "toad_space_arr_offset": [0xF194, 0xF244],  # [0x002A6C64, 0x002A6D14],
    "bank_arr_offset": [0xF388],  # [0x002A6E58], // 0x80111B88
    "bank_coin_arr_offset": [0xF26C],  # [0x002A6D3C], // 0x80111A6C
    "bank_count": 2,
    "item_shop_arr_offset": [0xF38C],  # [0x002A6E5C], // 0x80111B8C
    "item_shop_count": 1,
    "boo_arr_offset": [0xF268],  # [0x002A6D38], // 0x80111A68
    "boo_count": 2,
    "audio_index_offset": 0x33AA,  # 0x0029AE7A; // 0x80105BAA

    "on_load": _western_on_load,
    "on_after_overwrite": _western_on_after_overwrite,
})

# Pirate Land - (U) ROM
MP2_PIRATE = create_board_info("MP2_PIRATE")
MP2_PIRATE["name"] = "Pirate Land"
MP2_PIRATE["board_def_file"] = 65
MP2_PIRATE["bg_dir"] = 10
MP2_PIRATE["anim_bg_set"] = 1
MP2_PIRATE["costume_type"] = CostumeType.PIRATE
MP2_PIRATE["str"] = {
    "board_select": 198,
}
MP2_PIRATE["img"] = {
    "intro_logo_img": 422,
    "pause_logo_img": 381,
    "board_select_img": 31,
    "board_select_icon_coords": [35, 61],
}
# MP2_PIRATE.sceneIndex = 0x3F; // 63
MP2_PIRATE["arrow_rot_start_offset"] = 0x00  # 0x801059F0
MP2_PIRATE["arrow_rot_end_offset"] = 0x00  # 0x80105A30

# Horror Land - (U) ROM
MP2_HORROR = create_board_info("MP2_HORROR")
MP2_HORROR["name"] = "Horror Land"
MP2_HORROR["board_def_file"] = 66
MP2_HORROR["bg_dir"] = 21
MP2_HORROR["anim_bg_set"] = 2
MP2_HORROR["costume_type"] = CostumeType.HORROR
MP2_HORROR["str"] = {
    "board_select": 201,
}
MP2_HORROR["img"] = {
    "intro_logo_img": 581,
    "pause_logo_img": 382,
    "board_select_img": 32,
    "board_select_icon_coords": [133, 60],
}
MP2_HORROR["scene_index"] = 0x43  # 67
MP2_HORROR["event_asm_start"] = 0  # 0x80112248 ballpark for safe start
MP2_HORROR["event_asm_end"] = 0  # 0x80112C2C same, c2c is big boo event b2w
# MP2_HORROR.spaceEventsStartAddr = 0x0011466C; // There's more...
# MP2_HORROR.spaceEventsStartOffset = 0x002D9B5C;
# MP2_HORROR.spaceEventsEndOffset = 0x002D9CD4;
MP2_HORROR["space_event_tables"] = [
    # Tables around 0x80114xxx
    {"upper": 0x3854, "lower": 0x385C},  # 0x80106054, 0x8010605C
    {"upper": 0x3860, "lower": 0x3868},  # 0x80106060, 0x80106068
    {"upper": 0x3898, "lower": 0x38A0},  # 0x80106098, 0x801060A0
    {"upper": 0x38A4, "lower": 0x38A8},  # 0x801060A4, 0x801060A8 // Puts the JAL afterwards for some reason.
]

# Space Land - (U) ROM
MP2_SPACE = create_board_info("MP2_SPACE")
MP2_SPACE["name"] = "Space Land"
MP2_SPACE["board_def_file"] = 67
MP2_SPACE["bg_dir"] = 24
MP2_SPACE["anim_bg_set"] = 3
MP2_SPACE["costume_type"] = CostumeType.SPACE
MP2_SPACE["str"] = {
    "board_select": 199,
    "board_names": [193, 212],
}
MP2_SPACE["img"] = {
    "intro_logo_img": 500,
    "pause_logo_img": 383,
    "board_select_img": 33,
    "board_select_icon_coords": [93, 10],
}

# Mystery Land - (U) ROM
MP2_MYSTERY = create_board_info("MP2_MYSTERY")
MP2_MYSTERY["name"] = "Mystery Land"
MP2_MYSTERY["board_def_file"] = 68
MP2_MYSTERY["bg_dir"] = 16
MP2_MYSTERY["costume_type"] = CostumeType.MYSTERY
MP2_MYSTERY["str"] = {
    "board_select": 200,
}
MP2_MYSTERY["img"] = {
    "intro_logo_img": 502,
    "pause_logo_img": 384,
    "board_select_img": 34,
    "board_select_icon_coords": [139, 19],
}

# Bowser Land - (U) ROM
MP2_BOWSER = create_board_info("MP2_BOWSER")
MP2_BOWSER["name"] = "Bowser Land"
MP2_BOWSER["board_def_file"] = 69
MP2_BOWSER["bg_dir"] = 37
MP2_BOWSER["anim_bg_set"] = 4
MP2_BOWSER["costume_type"] = CostumeType.NORMAL
MP2_BOWSER["str"] = {
    "board_select": 202,
}
MP2_BOWSER["img"] = {
    "intro_logo_img": 547,
    "pause_logo_img": 385,
    "board_select_img": 35,
}

# The other MP2 board defs, not handled (from the original):
#   Mini-Game Stadium: fileNum 70, bgNum 37, titleImg 386
#   mystery: fileNum 71-79, bgNum 59, titleImg 387
#   Rules Land: fileNum 80, bgNum 43


def get_board_infos():
    return [
        MP2_WESTERN,
        MP2_PIRATE,
        MP2_HORROR,
        MP2_SPACE,
        MP2_MYSTERY,
        MP2_BOWSER,
    ]
