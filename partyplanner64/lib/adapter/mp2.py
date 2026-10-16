"""The Mario Party 2 adapter (port of adapter/MP2.ts)."""

import os

from PIL import Image

from ..types import CostumeType, Space
from ..utils.debug import log
from ..utils.dataview import DataView
from ..utils import canvas
from ._js import at, count_occurrences, is_number, substring, to_bytes_array
from .adapter_base import AdapterBase, _append_difficulty, _rom, _IMG_DIR

mp2boardselectblank1_image = os.path.join(_IMG_DIR, "detail", "mp2boardselectblank1.png")


class MP2Adapter(AdapterBase):
    game_version = 2

    nintendo_logo_fs_entry = [9, 1]
    hudson_logo_fs_entry = [9, 2]
    board_def_directory = 10

    MAINFS_READ_ADDR = 0x00017680
    HEAP_FREE_ADDR = 0x00017800
    TABLE_HYDRATE_ADDR = 0x0005568C

    def on_load(self, board, board_info, board_was_stashed):
        if not board_was_stashed:
            self._extract_costume_type(board, board_info)
            self._extract_banks(board, board_info)
            self._extract_item_shops(board, board_info)

        self._parse_board_select_icon(board, board_info)
        self._read_animation_backgrounds(board, board_info)

    def on_create_board_overlay(self, board, board_info, board_index, audio_indices):
        from .mp2_u_boardoverlay import create_board_overlay
        return create_board_overlay(board, board_info, board_index, audio_indices)

    def on_after_overwrite(self, rom_view, board, board_info, board_index):
        # Patch game to use all 8MB.
        rom_view.set_uint16(0x41602, 0x8040)  # Main heap now starts at 0x80400000
        rom_view.set_uint16(0x4160A, ((0x00400000 - self.EVENT_MEM_SIZE) & 0xFFFFFFFF) >> 16)  # ... and can fill up through reserved event space
        rom_view.set_uint16(0x41616, 0x001A)  # Temp heap fills as much as 0x1A8000 (8000 is ORed in)
        rom_view.set_uint16(0x7869E, 0x001A)

        self._write_costume_type(rom_view, board, board_index)

        # Remove the animations (we might add our own after this though).
        if is_number(board_info.get("anim_bg_set")):
            animationfs = _rom().get_animation_fs()
            animationfs.set_set_entry_count(board_info["anim_bg_set"], 0)

    def on_overwrite_promises(self, board, board_info, board_index):
        bg_index = board_info["bg_dir"]
        bg = board["bg"]
        otherbg = board.get("otherbg") or {}
        writes = [
            lambda: self._write_background(bg_index, bg["src"], bg["width"], bg["height"]),
            lambda: self._write_animation_backgrounds(
                board_info.get("anim_bg_set"),
                bg["width"],
                bg["height"],
                bg["src"],
                board.get("animbg"),
            ),
            lambda: self._write_background(bg_index + 2, otherbg.get("largescene"), 320, 240),  # Game start, end
            lambda: self._write_overview_background(bg_index + 6, bg["src"]),  # Overview map
            lambda: self.on_write_board_select_img(board, board_info),  # The board select image
            lambda: self._write_board_select_icon(board, board_info),  # The board select icon
            lambda: self.on_write_board_logo_img(board, board_info),  # Various board logos
            lambda: self._brand_boot_splashscreen(),
        ]
        for write in writes:
            write()

    def on_write_events(self, board):
        pass

    def hydrate_space(self, space, board, event_library):
        from ..boards import add_event_to_space_internal
        from ..events.events import create_event_instance
        from ..events.builtin.events_common import BankEvent

        if space["type"] == Space.BANK:
            add_event_to_space_internal(board, space, create_event_instance(BankEvent), False,
                                        event_library)

    def on_parse_strings(self, board, board_info):
        strs = board_info.get("str") or {}
        if strs.get("board_select"):
            idx = strs["board_select"]
            # if (Array.isArray(idx))
            #   idx = idx[0];

            strings = _rom().get_strings()
            text = strings.read(idx)
            lines = text.split("\n")

            # Read the board name and description.
            name_start = lines[0].find(">") + 1
            name_end = lines[0].find("\u0019", name_start)
            board["name"] = substring(lines[0], name_start, name_end)
            board["description"] = "\n".join([at(lines, 1) or "", at(lines, 2) or ""])

            # Parse difficulty star level
            board["difficulty"] = count_occurrences(text, self.get_character_map()[0x3B])

    def on_write_strings(self, board, board_info):
        from ..fs.strings import str_to_bytes

        strs = board_info.get("str") or {}
        strings = _rom().get_strings()

        # Various details about the board when selecting it
        if strs.get("board_select"):
            bytes_ = []
            bytes_.append(0x0B)  # Clear?
            bytes_.append(0x06)  # Start BLUE
            bytes_ += str_to_bytes(board.get("name") or "")
            bytes_.append(0x19)
            bytes_.append(0x04)  # Start Purple?
            bytes_ += [0x0E, 0x0E]  # Tabs
            bytes_ += str_to_bytes("Difficulty")
            bytes_.append(0x19)
            bytes_ += str_to_bytes(" : ")
            star = 0x3B
            _append_difficulty(bytes_, board, star)
            bytes_.append(0x0A)  # \n
            bytes_ += str_to_bytes(board.get("description") or "")  # Assumes \n's are correct within.
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)

            idx = strs["board_select"]
            strings.write(idx, str_buffer)

        # Simple strings that just have the board name
        if strs.get("board_names"):
            bytes_ = []
            bytes_.append(0x0B)
            bytes_.append(0x06)
            bytes_ += str_to_bytes(board.get("name") or "")
            bytes_.append(0x19)
            bytes_.append(0x00)  # Null byte
            str_buffer = to_bytes_array(bytes_)

            for idx in strs["board_names"]:
                strings.write(idx, str_buffer)

        # Toad's greeting to players at start
        # One piece is pre-bowser sign, one is after
        if strs.get("board_greeting"):
            bytes_ = []
            bytes_.append(0x0B)
            bytes_ += str_to_bytes("We're here, everyone!")
            bytes_.append(0x0A)  # \n
            bytes_ += str_to_bytes("This is ")
            bytes_.append(0x06)  # Blue
            bytes_.append(0x0F)
            bytes_ += str_to_bytes((board.get("name") or "") + "!!!")
            bytes_.append(0x16)
            bytes_.append(0x19)
            bytes_.append(0xFF)
            # bytes.push(0x0B);
            # bytes = bytes.concat(strToBytes("Your objective this time,"));
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            strings.write(strs["board_greeting"][0], str_buffer)

            bytes_ = []
            bytes_.append(0x0B)
            bytes_ += str_to_bytes("Now, before this adventure begins,")
            bytes_.append(0x0A)  # \n
            bytes_ += str_to_bytes("we must decide turn order.")
            bytes_.append(0xFF)
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            strings.write(strs["board_greeting"][1], str_buffer)

        # String congratulating a player for winning
        if strs.get("board_winner"):
            bytes_ = []
            bytes_.append(0x0B)
            bytes_ += str_to_bytes("Well done, ")
            bytes_.append(0x11)  # Player
            bytes_ += str_to_bytes("!")
            bytes_.append(0x0A)  # \n
            bytes_ += str_to_bytes("You are the ")
            bytes_.append(0x07)  # Yellow
            bytes_.append(0x0F)
            bytes_ += str_to_bytes("Super Star")
            bytes_.append(0x16)
            bytes_.append(0x19)
            bytes_.append(0x0A)  # \n
            bytes_ += str_to_bytes("of ")
            bytes_.append(0x06)  # Blue
            bytes_.append(0x0F)
            bytes_ += str_to_bytes((board.get("name") or "") + "!!!")
            bytes_.append(0x16)
            bytes_.append(0x19)
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            strings.write(strs["board_winner"], str_buffer)

        # "board name   {0} Time(s)"
        if strs.get("board_play_count"):
            bytes_ = []
            bytes_.append(0x0B)
            bytes_ += str_to_bytes(board.get("name") or "")
            bytes_ += [0x0E, 0x0E, 0x0E, 0x0E, 0x0E, 0x0E]  # Tabs
            bytes_.append(0x11)  # Play count
            bytes_ += str_to_bytes(" Time(s)")
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            strings.write(strs["board_play_count"], str_buffer)

    def on_change_board_space_types_from_game_space_types(self, board, chains):
        type_map = {
            0: Space.OTHER,  # Sometimes START
            3: Space.OTHER,
            5: Space.CHANCE,
            6: Space.ITEM,
            7: Space.BANK,
            8: Space.OTHER,
            9: Space.BATTLE,
            12: Space.BOWSER,
            14: Space.STAR,
            15: Space.BLACKSTAR,
            16: Space.OTHER,  # Toad
            17: Space.OTHER,  # Baby Bowser the COHORT
        }
        for space in board["spaces"]:
            old_type = space["type"]
            new_type = type_map.get(old_type)
            if new_type is not None:
                space["type"] = int(new_type)

        if chains:
            start_space_index = at(chains[0], 0)
            if is_number(start_space_index):
                board["spaces"][start_space_index]["type"] = int(Space.START)

    def on_change_game_space_types_from_board_space_types(self, board):
        type_map = {
            Space.OTHER: 0,
            Space.BLUE: 1,
            Space.RED: 2,
            Space.MINIGAME: 0,  # N/A
            Space.HAPPENING: 4,
            Space.STAR: 14,
            Space.CHANCE: 5,
            Space.START: 0,  # N/A
            Space.SHROOM: 0,  # N/A
            Space.BOWSER: 12,
            Space.ITEM: 6,
            Space.BATTLE: 9,
            Space.BANK: 7,
            Space.ARROW: 13,
            Space.BLACKSTAR: 15,
            Space.GAMEGUY: 0,  # N/A
            Space.DUEL_BASIC: 0,  # N/A
            Space.DUEL_START_BLUE: 0,  # N/A
            Space.DUEL_START_RED: 0,  # N/A
            Space.DUEL_POWERUP: 0,  # N/A
            Space.DUEL_REVERSE: 0,  # N/A
        }
        for space in board["spaces"]:
            new_type = type_map.get(space["type"])
            if new_type is not None:
                space["type"] = new_type

    def _extract_costume_type(self, board, board_info):
        costume_type = board_info.get("costume_type")
        if costume_type is None:
            board.pop("costumeTypeIndex", None)  # (undefined)
        else:
            board["costumeTypeIndex"] = int(costume_type)

    def _write_costume_type(self, rom_view, board, board_index):
        """Overwrite character costumes."""
        costume_model_map = {
            CostumeType.NORMAL: {
                "small": 0xD3,  # 211
                "big": 0xD1,  # 209
                "toad": 0x00080000,
                "player2d": [
                    0x000A0282,  # 10/642
                    0x000A0283,
                    0x000A0285,
                    0x000A0286,
                    0x000A0284,
                    0x000A0287,
                ],
                "bowser2d": [
                    0x000A029A,  # 10/666
                    0x000A029B,
                    0x000A029D,
                    0x000A029E,
                    0x000A029C,
                    0x000A029F,
                ],
            },
            CostumeType.WESTERN: {
                "small": 0xD4,  # 212
                "big": 0xD5,  # 213
                "toad": 0x0008000E,
                "player2d": [
                    0x000A0264,  # 10/612
                    0x000A0265,
                    0x000A0267,
                    0x000A0268,
                    0x000A0266,
                    0x000A0269,
                ],
                "bowser2d": [
                    0x000A0288,  # 10/648
                    0x000A0289,
                    0x000A028B,
                    0x000A028C,
                    0x000A028A,
                    0x000A028D,
                ],
            },
            CostumeType.PIRATE: {
                "small": 0xD6,  # 214
                "big": 0xD7,  # 215,
                "toad": 0x00080016,
                "player2d": [
                    0x000A026A,  # 10/618
                    0x000A026B,
                    0x000A026D,
                    0x000A026E,
                    0x000A026C,
                    0x000A026F,
                ],
                "bowser2d": [
                    0x000A028E, 0x000A028F, 0x000A0291, 0x000A0292, 0x000A0290,
                    0x000A0293,
                ],
            },
            CostumeType.HORROR: {
                "small": 0xD8,  # 216
                "big": 0xD9,  # 217
                "toad": 0x00080028,
                "player2d": [
                    0x000A0270, 0x000A0271, 0x000A0273, 0x000A0274, 0x000A0272,
                    0x000A0275,
                ],
                "bowser2d": [
                    0x000A0294, 0x000A0295, 0x000A0297, 0x000A0298, 0x000A0296,
                    0x000A0299,
                ],
            },
            CostumeType.SPACE: {
                "small": 0xDA,  # 218
                "big": 0xDB,  # 219
                "toad": 0x0008001C,
                "player2d": [
                    0x000A0276, 0x000A0277, 0x000A0279, 0x000A027A, 0x000A0278,
                    0x000A027B,
                ],
                "bowser2d": [
                    0x000A029A,  # same as normal
                    0x000A029B,
                    0x000A029D,
                    0x000A029E,
                    0x000A029C,
                    0x000A029F,
                ],
            },
            CostumeType.MYSTERY: {
                "small": 0xDC,  # 220
                "big": 0xDD,  # 221
                "toad": 0x00080023,
                "player2d": [
                    0x000A027C,  # 10/636
                    0x000A027D,
                    0x000A027F,
                    0x000A0280,
                    0x000A027E,
                    0x000A0281,
                ],
                "bowser2d": [
                    0x000A02A0, 0x000A02A1, 0x000A02A3, 0x000A02A4, 0x000A02A2,
                    0x000A02A5,
                ],
            },
        }

        costume_type_index = board.get("costumeTypeIndex")
        if costume_type_index is None:
            costume_type_index = CostumeType.NORMAL
        costume_info = costume_model_map[costume_type_index]

        board_model_rows_index = 0xCBF40 + board_index * (16 * 12)  # 16 bytes per model entry * 12 rows (6 big, 6 small models)
        CHARACTER_COUNT = 6

        for i in range(CHARACTER_COUNT):
            # Table at ROM 0xCBF40 has the "small/big" models for each character.
            # Ex: 2/D4 is Western small, 2/D5 is western big, 2/D6 pirate small, 2/D7 pirate big.
            rom_view.set_uint16(board_model_rows_index + i * 16 + 2, costume_info["small"])
            rom_view.set_uint16(board_model_rows_index + 96 + i * 16 + 2, costume_info["big"])

            # Table at ROM 0xCC4C0 has costumed toads.

            # Table at ROM 0xCDA28 has list of 2d model renders of themed characters.
            rom_view.set_uint32(0xCDA28 + board_index * 6 * 4 + i * 4, costume_info["player2d"][i])

            # Table at ROM 0xCDAE8 has list of themed bowser suits.
            rom_view.set_uint32(0xCDAE8 + board_index * 6 * 4 + i * 4, costume_info["bowser2d"][i])

        # The following somewhat replaces the toad models, but animations aren't yet replaced.

        # if (boardIndex < 5) { // Not bowser land
        #   // Table at ROM 0xCC4C0 has costumed toads. None for Bowser Land.
        #   romView.setUint32(0xCC4C0 + (boardIndex * 16), costumeInfo.toad);
        # }

        # // 0x35CF64 also has the toad models.
        # let sceneView = scenes.getDataView(82);
        # sceneView.setUint32(0x4184 + (boardIndex * 4), costumeInfo.toad);

        # // And animations following?

        # // 0x37EA64 also has the toad models, used when selecting board.
        # // RAM: 80113364
        # // Overlay 88 (0x58) offset +68452 (+0x10B64)
        # sceneView = scenes.getDataView(88);
        # sceneView.setUint32(0x10B64 + (boardIndex * 4), costumeInfo.toad);

        # // And animations following?

        # // 0x3900F4 also has the toad models
        # // RAM: 80113444
        # // Overlay 91 (0x5B) offset +68676 (+0x10C44)
        # sceneView = scenes.getDataView(91);
        # sceneView.setUint32(0x10C44 + (boardIndex * 4), costumeInfo.toad);

        # // And animations following?

    def _read_animation_backgrounds(self, board, board_info):
        if not is_number(board_info.get("anim_bg_set")) or not board_info.get("bg_dir"):
            return

        # Perf: This is a bit redundant because we read the data URI previously.
        hvqfs = _rom().get_hvqfs()
        main_bg_img_data = hvqfs.read_background_img_data(board_info["bg_dir"])

        animationfs = _rom().get_animation_fs()
        anim_bgs = animationfs.read_animation_backgrounds(
            board_info["anim_bg_set"],
            main_bg_img_data,
            board["bg"]["width"],
            board["bg"]["height"],
        )
        if anim_bgs:
            board["animbg"] = anim_bgs

    def _write_animation_backgrounds(self, set_index, width, height, main_bg_src, anim_sources=None):
        if not is_number(set_index) or set_index != set_index or not anim_sources:
            return

        main_bg_img_data = canvas.get_image_data(main_bg_src, width, height)
        anim_img_data = [canvas.get_image_data(src, width, height) for src in anim_sources]

        animationfs = _rom().get_animation_fs()
        for i in range(len(anim_img_data)):
            animationfs.write_animation_background(
                set_index,
                i,
                main_bg_img_data,
                anim_img_data[i],
                width,
                height,
            )
        log("Wrote animations")

    def on_parse_board_select_img(self, board, board_info):
        if not board_info["img"].get("board_select_img"):
            return

        board["otherbg"]["boardselect"] = self._read_img_from_main_fs(
            9, board_info["img"]["board_select_img"], 0)

    def on_write_board_select_img(self, board, board_info):
        board_select_img = board_info["img"].get("board_select_img")
        if not board_select_img:
            return

        from ..utils.img.img_pack import to_pack

        img_buffer = canvas.get_image_data(board["otherbg"].get("boardselect"), 64, 48).data

        # First, read the old image pack.
        mainfs = _rom().get_main_fs()
        old_pack = mainfs.get(9, board_select_img)

        # Then, pack the image and write it.
        img_info_arr = [
            {
                "src": img_buffer,
                "width": 64,
                "height": 48,
                "bpp": 32,
            },
        ]
        new_pack = to_pack(img_info_arr, 16, 0, old_pack)
        mainfs.write(9, board_select_img, new_pack)

    def _parse_board_select_icon(self, board, board_info):
        if not board_info["img"].get("board_select_icon_coords"):
            return

        from ..utils.image import cut_from_whole
        from ..utils.img.img_pack import img_info_src_to_array_buffer

        bg_info = self._read_img_info_from_main_fs(9, 15, 0)
        x, y = board_info["img"]["board_select_icon_coords"]
        icon = cut_from_whole(
            img_info_src_to_array_buffer(bg_info["src"]),
            bg_info["width"],
            bg_info["height"],
            32,
            x,
            y,
            32,
            32,
        )
        data_url = canvas.rgba_to_data_url(icon, 32, 32)
        board["otherbg"]["boardselecticon"] = data_url

    def _write_board_select_icon(self, board, board_info):
        if not board_info["img"].get("board_select_icon_coords"):
            return
        board_select_icon_src = board["otherbg"].get("boardselecticon")
        if not board_select_icon_src:
            return

        from ..utils.img.img_pack import img_info_src_to_array_buffer, to_pack

        blank_back_image = canvas.open_image(mp2boardselectblank1_image)
        new_board_select_icon_image = canvas.open_image(board_select_icon_src)

        bg_info = self._read_img_info_from_main_fs(9, 15, 0)  # Read the existing icon select thing

        # Draw the original onto a canvas
        orig_image_data = canvas.ImageData(
            bg_info["width"], bg_info["height"],
            bytearray(img_info_src_to_array_buffer(bg_info["src"])))
        icon_select = canvas.to_pil(orig_image_data)

        # Then draw the "clean slate" for the icon, and the given icon.
        x, y = board_info["img"]["board_select_icon_coords"]
        _draw_image(icon_select, blank_back_image, x, y, 32, 32)
        _draw_image(icon_select, new_board_select_icon_image, x, y, 32, 32)

        # Place edited icon select thing back into ROM
        final_icon_select_thing_buffer = canvas.from_pil(icon_select).data

        # Read the old image pack.
        mainfs = _rom().get_main_fs()
        old_pack = mainfs.get(9, 15)

        # Then, pack the image and write it.
        img_info_arr = [
            {
                "src": final_icon_select_thing_buffer,
                "width": bg_info["width"],
                "height": bg_info["height"],
                "bpp": 32,
            },
        ]
        new_pack = to_pack(img_info_arr, 16, 0, old_pack)
        mainfs.write(9, 15, new_pack)

        # Write the hover mask for the new image
        if board_info["img"].get("board_select_icon_mask"):
            mask = self._create_board_select_icon_hover_mask(board_select_icon_src)

            old_pack = mainfs.get(9, board_info["img"]["board_select_icon_mask"])

            # Then, pack the image and write it.
            img_info_arr = [
                {
                    "src": mask,
                    "width": 32,
                    "height": 32,
                    "bpp": 32,
                },
            ]
            new_pack = to_pack(img_info_arr, 16, 0, old_pack)
            mainfs.write(9, board_info["img"]["board_select_icon_mask"], new_pack)

        log("Wrote board select icon")

    def _create_board_select_icon_hover_mask(self, new_icon_image):
        """The mask for the rainbow hover effect over the board select icon.

        This creates the asset that is used to create the rainbow hover effect
        over the board select icon. The effect is a bit crude now; the original
        mask can have some semi-transparent edges, but this just either adds
        a #00000000 or #BBBBBBFF pixel based on the given icon.
        """
        new_icon_buffer = canvas.get_image_data(new_icon_image, 32, 32).data
        mask_buffer = bytearray(len(new_icon_buffer))

        new_icon_view = DataView(new_icon_buffer)
        mask_view = DataView(mask_buffer)

        has_transparency = False

        for i in range(0, len(mask_buffer), 4):
            if new_icon_view.get_uint32(i) == 0:
                mask_view.set_uint32(i, 0)
                has_transparency = True
            else:
                mask_view.set_uint32(i, 0xBBBBBBFF)

        # If someone gives a totally non-transparent image... well the mask won't
        # work very well. We will just clear out the mask, no hover effect then.
        if not has_transparency:
            return bytearray(len(new_icon_buffer))

        return mask_buffer

    def on_parse_board_logo_img(self, board, board_info):
        if not board_info["img"].get("intro_logo_img"):
            return

        board["otherbg"]["boardlogo"] = self._read_img_from_main_fs(
            10, board_info["img"]["intro_logo_img"], 0)

    def on_write_board_logo_img(self, board, board_info):
        intro_logo_img = board_info["img"].get("intro_logo_img")
        if not intro_logo_img:
            return

        from ..utils.img.img_pack import to_pack

        mainfs = _rom().get_main_fs()

        # Just blank out the pause logo, it is not worth replacing.
        # (The TypeScript did this while the logo image loaded.)
        pause_logo_img = board_info["img"].get("pause_logo_img")
        if pause_logo_img:
            old_pack = mainfs.get(10, pause_logo_img)
            img_info_arr = [
                {
                    "src": bytearray(130 * 60 * 4),
                    "width": 130,
                    "height": 60,
                    "bpp": 32,
                },
            ]
            new_pack = to_pack(img_info_arr, 16, 0, old_pack)
            mainfs.write(10, pause_logo_img, new_pack)

        # Write the intro logo images.
        img_buffer = canvas.get_image_data(board["otherbg"].get("boardlogo"), 260, 120).data

        # First, read the old image pack.
        old_pack = mainfs.get(10, intro_logo_img)

        # Then, pack the image and write it.
        img_info_arr = [
            {
                "src": img_buffer,
                "width": 260,
                "height": 120,
                "bpp": 32,
            },
        ]
        new_pack = to_pack(img_info_arr, 16, 0, old_pack)
        mainfs.write(10, intro_logo_img, new_pack)

    def _write_overview_background(self, bg_index, src):
        """Write the overview map background.

        Same as _writeBackground essentially, but for some reason MP2 overview background
        doesn't line up when just shrinking the background naively.
        If we shift it up by 1 tile's worth of height, it lines up better.
        """
        img_data = canvas.get_image_data(src, 320, 240)

        # canvasCtx.putImageData(imgData, 0, -10): shift up 10 rows, the rest stays transparent.
        row = 320 * 4
        shifted = bytearray(320 * 240 * 4)
        shifted[0:row * 230] = img_data.data[row * 10:row * 240]
        img_data_shifted = canvas.ImageData(320, 240, shifted)

        hvqfs = _rom().get_hvqfs()
        hvqfs.write_background(bg_index, img_data_shifted, 320, 240)

    # Writes to 0x800CD524, break 0x80079390
    def get_audio_map(self, table_index):
        return [
            "",  # 0x00 Two Beeps
            "Story One",
            "Go Lucky",
            "Welcome to Mario Land",
            "Laboratory",
            "Rules Land",
            "Credits",  # ?
            "In the Pipe",
            "Western Land",
            "Pirate Land",
            "Space Land",
            "Horror Land",
            "Mystery Land",
            "Bowser Land",  # ?
            "Adventure Begins",
            "The Adventure Ends",
            "Ending",  # 0x10
            "Star Spot",
            "Bowser's Theme",
            "A Ways to Go",
            "How Many",
            "Take the Coin",
            "Let the Game Begin",
            "",  # Two Beeps
            "",  # Two Beeps
            "",  # Two Beeps
            "",  # Two Beeps
            "Going for the Coins",
            "Not Gonna Lose",
            "Keepin' on the Path",
            "Couldn't be Better",
            "Know What I Mean?",
            "That's All of It",  # 0x20
            "Let's Have Some Fun",
            "The Blue Skies Yonder",
            "Chance Time",
            "Going Somewhere",
            "Duel!",
            "No Fright, No Fear",
            "Don't Look Back",
            "Got an Item",
            "This Way That",
            "Walking Underwater",
            "Spinning Polka",
            "Spinning Polka 2",  # ?
            "Spinning Polka 3",  # ?
            "",  # "Jamming Groove", // ?
            "",  # "Electronic Groove", // ? These two from visiting characters?
            "",  # 0x30 Two Beeps
            "",  # "Plays in 'facing' direction mini-game",
            "Mini-Game Land",
            "Woody",
            "Mini-Game Park",
            "Battle Start",
            "Mini-Game Stadium",
            "",  # Two Beeps
            "Coaster",
            "",  # "Anticipatory dingles",
            "The Way to Play",
            "The Star Appears",
            "Bowser Appears",
            "I Can Do It!",
            "Bowser's Parade",
            "Ending",  # "Finale song",
            "Story Intro 2",  # 0x40
            "Story Intro 3",
            "Mini-Game Coaster Results",
            "Drum Roll",
            "Win (One Winner)",
            "Lose",
            "",  # Two Beeps
            "Know What I Mean",
            "Instant Replay",
            "Coaster (Double Mix)",
            "Coaster (Single Mix)",
            "Coaster (Hip Hip Mix)",
            "Coaster (Duo Mix)",
            "Coaster (Hermit Mix)",
            "Coaster (Speed Mix)",
            "Coaster (Survival Mix)",
            # "", 0x50 Two Beeps
            # "Success Mini-Game Result",
            # "Success Mini-Game Result",
            # "Kind of Success Mini-Game Result",
            # "Mini-Game turned sour",
            # "Great fanfare",
            # "Failure fanfare",
            # "Disappointing result",
            # "Fanfare",
            # "Players run across screen intro fanfare",
            # "Silent",
            # "Intro To Mario Land - Bowser Land Appears",
            # "Fanfare",
            # "Anti-fanfare",
            # "Genie Theme",
            # "Silent",
            # "Fanfare", // 0x60
        ]

    # Mostly a MP1 copy for now.
    def get_character_map(self):
        return {
            0x00: "",  # NULL terminator
            0x01: "<BLACK>",
            0x02: "<DEFAULT>",
            0x03: "<RED>",
            0x04: "<PURPLE>",
            0x05: "<GREEN>",
            0x06: "<BLUE>",
            0x07: "<YELLOW>",
            0x08: "<WHITE>",
            0x09: "<SEIZURE>",
            0x0A: "\n",
            0x0B: "〔",  # FEED Carriage return / start of bubble?
            0x0C: "○",  # 2ND BYTE OF PLAYER CHOICE
            0x0D: "\t",  # UNCONFIRMED / WRONG
            0x0E: "\t",  # 1ST BYTE OF PLAYER CHOICE
            # 0x0F - nothing
            0x10: " ",
            0x11: "{0}",  # These are format params that get replaced with various things
            0x12: "{1}",
            0x13: "{2}",
            0x14: "{3}",
            0x15: "{4}",
            0x16: "{5}",
            # Theoretically there may be more up through 0x20?
            # 0x18 - nothing
            # 0x20 - nothing
            0x21: "　",  # ! A button
            0x22: "、",  # " B button
            0x23: "。",  #  C-up button
            0x24: "〃",  #  C-right button
            0x25: "〄",  #  C-left button
            0x26: "々",  # & C-down button
            0x27: "〆",  # ' Z button
            0x28: "〇",  # ( Analog stick
            0x29: "〈",  # ) (coin)
            0x2A: "〉",  # * Star
            0x2B: "【",  # , S button
            0x2C: "】",  # , R button
            # 0x2D - nothing
            # 0x2E - nothing
            # 0x2F - nothing
            # 0x30 - 0x39: 0-9 ascii
            0x3A: "〒",  # Hollow coin
            0x3B: "〓",  # Hollow star
            0x3C: "+",  # <
            0x3D: "-",  # =
            0x3E: "x",  # > Little x
            0x3F: "->",  # Little right ARROW
            # 0x40 - nothing
            # 0x41 - 0x5A: A-Z ascii
            0x5B: '"',  # [ End quotes
            0x5C: "'",  # \ Single quote
            0x5D: "(",  # ] Open parenthesis
            0x5E: ")",
            0x5F: "/",  # _
            # 0x60 - nothing
            # 0x61 - 0x7A: a-z ascii
            0x7B: ":",  # :
            0x80: '"',  # Double quote no angle
            0x81: "°",  # . Degree
            0x82: ",",  # ,
            0x83: "°",  # Low circle FIXME
            0x85: ".",  # … Period
            0xC0: "“",  # A`
            0xC1: "”",  # A'
            0xC2: "!",  # A^
            0xC3: "?",  # A~
            0xFF: "〕",  # PAUSE
        }


def _draw_image(dest, src, x, y, width, height):
    """canvasCtx.drawImage(src, x, y, width, height) onto a Pillow RGBA image (source-over)."""
    if src.size != (width, height):
        src = src.resize((width, height), Image.BILINEAR)
    dest.alpha_composite(src, (int(x), int(y)))
