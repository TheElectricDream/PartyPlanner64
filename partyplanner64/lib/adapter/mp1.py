"""The Mario Party 1 adapter (port of adapter/MP1.ts)."""

from ..types import Space, SpaceSubtype
from ..utils.debug import log
from ..utils.dataview import DataView
from ..utils import canvas
from ._js import at, count_occurrences, substring, to_bytes_array
from .adapter_base import AdapterBase, _append_difficulty, _rom


class MP1Adapter(AdapterBase):
    game_version = 1

    nintendo_logo_fs_entry = [9, 110]
    hudson_logo_fs_entry = [9, 111]
    board_def_directory = 10

    MAINFS_READ_ADDR = 0x000145B0
    HEAP_FREE_ADDR = 0x00014730
    TABLE_HYDRATE_ADDR = 0x0004C900

    def hydrate_space(self, space, board, event_library):
        """Gives a new space the default things it would need."""
        from ..boards import add_event_to_space_internal
        from ..events.events import create_event_instance
        from ..events.builtin.mp1.u.chance_time_event1 import ChanceTime

        if space["type"] == Space.STAR:
            space["star"] = True
        elif space["type"] == Space.CHANCE:
            add_event_to_space_internal(board, space, create_event_instance(ChanceTime), False,
                                        event_library)

    def on_load(self, board, board_info, board_was_stashed):
        if not board_was_stashed:
            self._extract_koopa(board, board_info)
            self._extract_bowser(board, board_info)
            self._extract_goomba(board, board_info)

    def on_create_board_overlay(self, board, board_info, board_index, audio_indices):
        from .mp1_u_boardoverlay import create_board_overlay
        return create_board_overlay(board, board_info, board_index, audio_indices)

    def on_after_overwrite(self, rom_view, board, board_info, board_index):
        from ..mips import assemble, parse as parse_inst

        # this._writeKoopa(board, boardInfo);
        # this._writeBowser(board, boardInfo);

        # Patch game to use all 8MB.
        rom_view.set_uint16(0x3BF62, 0x8040)  # Main heap now starts at 0x80400000
        rom_view.set_uint16(0x3BF6A, ((0x00400000 - self.EVENT_MEM_SIZE) & 0xFFFFFFFF) >> 16)  # ... and can fill up through the reserved event location
        rom_view.set_uint16(0x3BF76, 0x0020)  # Temp heap fills as much as 0x200000
        rom_view.set_uint16(0x5F3F6, 0x0020)

        # Patch HVQ decode RAM 0x4a3a4 to redirect to raw decode hook.
        rom_start_offset = 0xCBFD0
        asm_start_offset = 0xCB3D0
        rom_view.set_uint32(0x4AFD4, parse_inst("J %d" % asm_start_offset))

        # Patch over some debug strings with logic to handle raw images.
        hvq_asm = """
      .orga %d
      LW S5, 0x0(A0)
      LUI S6, 0x4856 // "HV"
      ADDIU S6, S6, 0x5120 // "Q "
      BEQ S5, S6, call_hvq_decode
      NOP
      ADDU S5, R0, A1
      ADDIU S6, S5, 0x1800 // (64 x 48 tile)
      ADDU S7, R0, A0
      LW GP, 0(S7)
      SW GP, 0(S5)
      ADDIU S5, S5, 4
      ADDIU S7, S7, 4
      BEQ S5, S6, ret_to_hook
      NOP
      J %d // J back to LW
      NOP
    call_hvq_decode:
      ADDU S5, R0, R0
      ADDU S6, R0, R0
      ADDU S7, R0, R0
      ADDU GP, R0, R0
      JAL 0x7F54C // JAL HVQDecode
      NOP
    ret_to_hook:
      ADDU S5, R0, R0
      ADDU S6, R0, R0
      ADDU S7, R0, R0
      ADDU GP, R0, R0
      J 0x4A3DC // J back into original function, skipping HVQDecode
      NOP
    """ % (rom_start_offset, asm_start_offset + 0x20)
        assemble(hvq_asm, buffer=rom_view.buffer)

    def on_overwrite_promises(self, board, board_info, board_index):
        bg_index = board_info["bg_dir"]
        otherbg = board.get("otherbg") or {}
        bg = board["bg"]
        writes = [
            lambda: self.on_write_board_select_img(board, board_info),  # The board select image/icon
            lambda: self.on_write_board_logo_img(board, board_info),  # Various board logos
            lambda: self._brand_boot_splashscreen(),
            lambda: self._write_background(bg_index, bg["src"], bg["width"], bg["height"]),
            lambda: self._write_background(board_info.get("pause_bg_dir"), bg["src"], 320, 240),  # Overview map
            lambda: self._write_additional_backgrounds(board),
        ]

        if board_index == 0:  # DK board
            writes += [
                lambda: self._write_background(bg_index + 1, otherbg.get("largescene"), 320, 240),  # Game start, end
                lambda: self._write_background(bg_index + 2, otherbg.get("conversation"), 320, 240),  # Conversation
                lambda: self._write_background(bg_index + 3, otherbg.get("conversation"), 320, 240),  # Treasure thing...
                # Pause bg
                lambda: self._write_background(bg_index + 5, bg["src"], 320, 240),  # End game overview map
                lambda: self._write_background(bg_index + 6, otherbg.get("splashscreen"), 320, 240),  # Splashscreen bg
            ]
        elif board_index == 1:  # Peach board
            writes += [
                lambda: self._write_background(bg_index + 1, otherbg.get("largescene"), 320, 240),  # Game start, end
                lambda: self._write_background(bg_index + 2, otherbg.get("conversation"), 320, 240),  # Mini-Game results, Boo?
                lambda: self._write_background(bg_index + 3, otherbg.get("conversation"), 320, 240),  # Conversation
                lambda: self._write_background(bg_index + 4, otherbg.get("conversation"), 320, 240),  # Visit Toad
                lambda: self._write_background(bg_index + 5, otherbg.get("conversation"), 320, 240),
                lambda: self._write_background(bg_index + 6, otherbg.get("largescene"), 320, 240),  # Third end game cutscene bg
                # Pause bg
                lambda: self._write_background(bg_index + 8, bg["src"], 320, 240),  # First end game cutscene bg
                lambda: self._write_background(bg_index + 9, bg["src"], 320, 240),  # Second end game cutscene bg
                lambda: self._write_background(bg_index + 10, otherbg.get("splashscreen"), 320, 240),  # Splashscreen
            ]
        elif board_index == 2:  # Yoshi board
            writes += [
                # 18: bgDir
                lambda: self._write_background(bg_index + 1, otherbg.get("largescene"), 320, 240),  # 19 Game start, end
                lambda: self._write_background(bg_index + 2, otherbg.get("conversation"), 320, 240),  # 20 Conversation, Boo, Koopa
                lambda: self._write_background(bg_index + 3, otherbg.get("conversation"), 320, 240),  # 21 Conversation
                lambda: self._write_background(bg_index + 4, otherbg.get("conversation"), 320, 240),  # 22 Conversation, Toad
                lambda: self._write_background(bg_index + 5, otherbg.get("conversation"), 320, 240),  # 23 Conversation, Bowser
                lambda: self._write_background(bg_index + 6, bg["src"], 320, 240),  # 24
                # 25: Pause bg
                lambda: self._write_background(bg_index + 8, otherbg.get("splashscreen"), 320, 240),  # 26 Splashscreen
            ]
        elif board_index == 3:  # Wario board
            writes += [
                # 27: bgDir
                lambda: self._write_background(bg_index + 1, otherbg.get("largescene"), 320, 240),  # 28 Game start, end
                lambda: self._write_background(bg_index + 2, otherbg.get("conversation"), 320, 240),  # 29 Conversation, Koopa
                lambda: self._write_background(bg_index + 3, otherbg.get("conversation"), 320, 240),  # 30 Conversation, Bowser, Boo
                lambda: self._write_background(bg_index + 4, otherbg.get("conversation"), 320, 240),  # 31
                lambda: self._write_background(bg_index + 5, otherbg.get("conversation"), 320, 240),  # 32 Conversation, Bowser, Toad
                lambda: self._write_background(bg_index + 6, bg["src"], 320, 240),  # 33
                lambda: self._write_background(bg_index + 7, otherbg.get("conversation"), 320, 240),  # 34
                lambda: self._write_background(bg_index + 8, otherbg.get("conversation"), 320, 240),  # 35
                # 36: Pause bg
                lambda: self._write_background(bg_index + 10, otherbg.get("conversation"), 320, 240),  # 37
                lambda: self._write_background(bg_index + 11, otherbg.get("splashscreen"), 320, 240),  # 38 Splashscreen
            ]

        for write in writes:
            write()

    def on_write_events(self, board):
        from ..boards import add_event_to_space_internal
        from ..events.events import create_event_instance
        from ..events.event_library import get_events_in_library
        from ..events.builtin.mp1.u.star_chance_event1 import StarChanceEvent

        # Right now the boards always put Chance time spaces where Stars were,
        # so we will just automate adding the post-star chance event.
        spaces = board["spaces"]
        for i in range(len(spaces)):
            space = board["spaces"][i]
            if not space or not space.get("star"):
                continue
            events = space.get("events") or []
            has_star_chance = any(e["id"] == "STARCHANCE" for e in events)  # Pretty unlikely
            if not has_star_chance:
                add_event_to_space_internal(board, space, create_event_instance(StarChanceEvent),
                                            False, get_events_in_library())

    def on_write_event_asm_hook(self, rom_view, board_info, board_index):
        pass

    def on_parse_strings(self, board, board_info):
        strs = board_info.get("str") or {}
        if strs.get("board_select"):
            idx = strs["board_select"]
            if isinstance(idx, list):
                idx = idx[0]

            strings = _rom().get_strings()
            text = strings.read(idx)
            lines = text.split("\n")

            # Read the board name and description.
            name_start = lines[0].find(">") + 1
            name_end = lines[0].find("<", name_start)
            board["name"] = substring(lines[0], name_start, name_end)
            board["description"] = "\n".join([at(lines, 1) or "", at(lines, 2) or ""])

            # Parse difficulty star level
            board["difficulty"] = count_occurrences(text, self.get_character_map()[0x2A])

    def on_write_strings(self, board, board_info):
        from ..fs.strings import str_to_bytes

        strs = board_info.get("str") or {}
        strings = _rom().get_strings()
        if strs.get("board_select"):
            bytes_ = []
            bytes_.append(0x0B)  # Clear?
            bytes_.append(0x05)  # Start GREEN
            bytes_ += str_to_bytes(board.get("name") or "")
            bytes_.append(0x02)  # Start DEFAULT
            bytes_.append(0x0A)  # \n
            bytes_ += str_to_bytes(board.get("description") or "")  # Assumes \n's are correct within.
            bytes_.append(0x0A)  # \n
            bytes_ += [0x10, 0x10, 0x10, 0x10, 0x10, 0x10]  # Spaces
            bytes_.append(0x06)  # Start BLUE
            bytes_ += str_to_bytes("Map Difficulty  ")
            star = 0x2A
            _append_difficulty(bytes_, board, star)
            bytes_.append(0x02)  # Start DEFAULT
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)

            idx = strs["board_select"]
            if isinstance(idx, list):
                for i in idx:
                    strings.write(i, str_buffer)
            else:
                strings.write(idx, str_buffer)

        # For now, just make Koopa's intro neutral.
        if strs.get("koopa_intro"):
            bytes_ = []
            bytes_ += str_to_bytes("Welcome, everybody!\nI am your guide,\nKoopa Troopa.")
            bytes_.append(0xFF)  # PAUSE
            bytes_.append(0x0B)  # Clear?
            bytes_ += str_to_bytes("Now then,\nlet's decide turn order.")
            bytes_.append(0xFF)  # PAUSE
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            strings.write(strs["koopa_intro"], str_buffer)

        # For now, just make a generic comment.
        if strs.get("star_comments"):
            bytes_ = []
            bytes_ += str_to_bytes("Good luck!\nWith enough stars, you\ncould be the superstar!")
            bytes_.append(0xFF)  # PAUSE
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            for idx in strs["star_comments"]:
                strings.write(idx, str_buffer)

    def on_change_board_space_types_from_game_space_types(self, board, chains):
        # Space types match MP1 exactly.
        pass

    def on_change_game_space_types_from_board_space_types(self, board):
        pass

    def _extract_koopa(self, board, board_info):
        if not board_info.get("koopa_space_inst") or not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        koopa_space = scene_view.get_uint16(board_info["koopa_space_inst"] + 2)
        if at(board["spaces"], koopa_space) is not None:
            board["spaces"][koopa_space]["subtype"] = int(SpaceSubtype.KOOPA)

    def _write_koopa(self, board, board_info):
        if not board_info.get("koopa_space_inst") or not board_info.get("scene_index"):
            return

        from ..boards import get_dead_space_index

        koopa_space = None
        for i in range(len(board["spaces"])):
            if board["spaces"][i].get("subtype") == SpaceSubtype.KOOPA:
                koopa_space = i
                break

        koopa_space = get_dead_space_index(board) if koopa_space is None else koopa_space
        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        scene_view.set_uint16(board_info["koopa_space_inst"] + 2, koopa_space)

    def _extract_bowser(self, board, board_info):
        if not board_info.get("bowser_space_inst") or not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        bowser_space = scene_view.get_uint16(board_info["bowser_space_inst"] + 2)
        if at(board["spaces"], bowser_space) is not None:
            board["spaces"][bowser_space]["subtype"] = int(SpaceSubtype.BOWSER)

    def _write_bowser(self, board, board_info):
        if not board_info.get("bowser_space_inst") or not board_info.get("scene_index"):
            return

        from ..boards import get_dead_space_index

        bowser_space = None
        for i in range(len(board["spaces"])):
            if board["spaces"][i].get("subtype") == SpaceSubtype.BOWSER:
                bowser_space = i
                break

        bowser_space = get_dead_space_index(board) if bowser_space is None else bowser_space
        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        scene_view.set_uint16(board_info["bowser_space_inst"] + 2, bowser_space)

    def _extract_goomba(self, board, board_info):
        if not board_info.get("goomba_space_inst") or not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        goomba_space = scene_view.get_uint16(board_info["goomba_space_inst"] + 2)
        if at(board["spaces"], goomba_space) is not None:
            board["spaces"][goomba_space]["subtype"] = int(SpaceSubtype.GOOMBA)

    def on_parse_board_select_img(self, board, board_info):
        if not board_info["img"].get("board_select_img"):
            return

        from ..models.form import FORM
        from ..utils.img.tiler import from_tiles

        mainfs = _rom().get_main_fs()
        board_select_form = mainfs.get(9, board_info["img"]["board_select_img"])
        board_select_unpacked = FORM.unpack(board_select_form)
        board_select_img_tiles = [
            DataView(_form_bmp_src(board_select_unpacked, 0)),
            DataView(_form_bmp_src(board_select_unpacked, 1)),
            DataView(_form_bmp_src(board_select_unpacked, 2)),
            DataView(_form_bmp_src(board_select_unpacked, 3)),
        ]
        board_select_img = from_tiles(board_select_img_tiles, 2, 2, 64 * 4, 32)
        board["otherbg"]["boardselect"] = canvas.rgba_to_data_url(board_select_img, 128, 64)
        # $$log(board.otherbg.boardselect);

    def on_write_board_select_img(self, board, board_info):
        board_select_index = board_info["img"].get("board_select_img")
        if not board_select_index:
            return

        from ..models.form import FORM
        from ..utils.img.bmp import bm_pfrom_rgba
        from ..utils.img.tiler import to_tiles

        # We need to write the image onto a canvas to get the RGBA32 values.
        width, height = 128, 64
        img_data = canvas.get_image_data(board["otherbg"].get("boardselect"), width, height)

        # First, turn the image back into 4 BMP tiles
        board_select_img_tiles = to_tiles(img_data.data, 2, 2, (width // 2) * 4, height // 2)
        board_select_bmps = [bm_pfrom_rgba(tile, 32, 8) for tile in board_select_img_tiles]

        # Now write the BMPs back into the FORM.
        mainfs = _rom().get_main_fs()
        board_select_form = mainfs.get(9, board_select_index)
        board_select_unpacked = FORM.unpack(board_select_form)
        for i in range(4):
            palette = board_select_bmps[i][1]

            # FIXME: This is padding the palette count a bit.
            # For some reason, the images get corrupt with very low palette count.
            while len(palette["colors"]) < 17:
                palette["colors"].append(0x00000000)
            FORM.replace_bmp(board_select_unpacked, i, board_select_bmps[i][0], palette)

        # Now write the FORM.
        board_select_packed = FORM.pack(board_select_unpacked)
        # saveAs(new Blob([boardSelectPacked]), "formPacked");
        mainfs.write(9, board_select_index, board_select_packed)

    def on_parse_board_logo_img(self, board, board_info):
        if not board_info["img"].get("pause_logo_img"):
            return

        board["otherbg"]["boardlogo"] = self._read_img_from_main_fs(10, board_info["img"]["pause_logo_img"], 0)

    def on_write_board_logo_img(self, board, board_info):
        from ..utils.img.img_pack import to_pack

        intro_logo_imgs = board_info["img"].get("intro_logo_img")
        pause_logo_img = board_info["img"].get("pause_logo_img")
        if not intro_logo_imgs and not pause_logo_img:
            return

        # We need to write the image onto a canvas to get the RGBA32 values.
        dimens = board_info["img"].get("intro_logo_img_dimens")
        if dimens is None:
            raise TypeError("introLogoImgDimens is not iterable (%s)" % board_info.get("name"))
        intro_width, intro_height = dimens[0], dimens[1]

        src_image = board["otherbg"].get("boardlogo")
        mainfs = _rom().get_main_fs()

        # Write the intro logo images.
        if intro_logo_imgs:
            img_buffer = canvas.get_image_data(src_image, intro_width, intro_height).data

            if not isinstance(intro_logo_imgs, list):
                intro_logo_imgs = [intro_logo_imgs]
            for logo_img_idx in intro_logo_imgs:
                # First, read the old image pack.
                old_pack = mainfs.get(10, logo_img_idx)

                # Then, pack the image and write it.
                img_info_arr = [
                    {
                        "src": img_buffer,
                        "width": intro_width,
                        "height": intro_height,
                        "bpp": 32,
                    },
                ]
                new_pack = to_pack(img_info_arr, 16, 0, old_pack)
                # saveAs(new Blob([newPack]), "imgpack");
                mainfs.write(10, logo_img_idx, new_pack)

        if pause_logo_img:
            # Always 200x82
            img_buffer = canvas.get_image_data(src_image, 200, 82).data

            # First, read the old image pack.
            old_pack = mainfs.get(10, pause_logo_img)
            # saveAs(new Blob([oldPack]), "oldpauseimgpack");
            # Then, pack the image and write it.
            img_info_arr = [
                {
                    "src": img_buffer,
                    "width": 200,
                    "height": 82,
                    "bpp": 32,
                },
            ]
            new_pack = to_pack(img_info_arr, 16, 0, old_pack)
            # saveAs(new Blob([newPack]), "newPack");
            mainfs.write(10, pause_logo_img, new_pack)

    def _clear_other_board_names(self, board_index):
        # There is an ugly comic-sansy board name graphic in the after-game results.
        # We will just make it totally transparent because it is not important.
        mainfs = _rom().get_main_fs()
        results_board_name_img_pack = mainfs.get(10, 406 + board_index)
        if not isinstance(results_board_name_img_pack, bytearray):
            results_board_name_img_pack = bytearray(results_board_name_img_pack)
        if len(results_board_name_img_pack) > 0x2C:
            results_board_name_img_pack[0x2C:] = bytes(len(results_board_name_img_pack) - 0x2C)  # To the end
        mainfs.write(10, 406 + board_index, results_board_name_img_pack)

    def get_audio_map(self, table_index):
        from .mp1_u_audio import get_audio_map_mp1
        return get_audio_map_mp1(table_index)

    def get_sound_effect_map(self, table):
        from .mp1_u_soundeffects import get_sound_effect_map_mp1
        return get_sound_effect_map_mp1(table)

    def get_character_map(self):
        return {
            0x00: "",  # NULL terminator
            0x01: "<BLACK>",  # Start black font
            0x02: "<DEFAULT>",  # Start default font
            0x03: "<RED>",  # Start red font
            0x04: "<PURPLE>",  # Start purple font
            0x05: "<GREEN>",  # Start green font
            0x06: "<BLUE>",  # Start blue font
            0x07: "<YELLOW>",  # Start yellow font
            0x08: "<WHITE>",  # Start white font
            0x09: "<SEIZURE>",  # Start flashing font
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


def _form_bmp_src(form_obj, index):
    """FORM.unpack(...).BMP1[index].parsed.src"""
    return form_obj["BMP1"][index]["parsed"]["src"]
