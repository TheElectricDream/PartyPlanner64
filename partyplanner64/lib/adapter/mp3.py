"""The Mario Party 3 adapter (port of adapter/MP3.ts)."""

import os

from ..types import (
    BoardType,
    EditorEventActivationType,
    EventExecutionType,
    Space,
    SpaceSubtype,
    get_event_activation_type_from_editor_type,
)
from ..utils.debug import log
from ..utils import canvas
from ._js import at, count_occurrences, substring, to_bytes_array
from .adapter_base import (
    AdapterBase, _IMG_DIR, _add_event_by_index, _append_difficulty, _defined, _rom)

genericgate_image = os.path.join(_IMG_DIR, "genericgate.png")


class MP3Adapter(AdapterBase):
    game_version = 3

    nintendo_logo_fs_entry = [17, 1]
    hudson_logo_fs_entry = [17, 2]
    board_def_directory = 19

    MAINFS_READ_ADDR = 0x00009C10
    HEAP_FREE_ADDR = 0x00009E6C
    TABLE_HYDRATE_ADDR = 0x000EBA60

    def on_load(self, board, board_info, board_was_stashed):
        if not board_was_stashed:
            self._extract_banks(board, board_info)
            self._extract_item_shops(board, board_info)

    def on_create_board_overlay(self, board, board_info, board_index, audio_indices):
        from .mp3_u_boardoverlay import create_board_overlay
        return create_board_overlay(board, board_info, board_index, audio_indices)

    def on_after_overwrite(self, rom_view, board, board_info, board_index):
        # Patch game to use all 8MB.
        rom_view.set_uint16(0x360EE, 0x8040)  # Main heap now starts at 0x80400000
        rom_view.set_uint16(0x360F6, ((0x00400000 - self.EVENT_MEM_SIZE) & 0xFFFFFFFF) >> 16)  # ... and can fill up through reserved event space
        rom_view.set_uint16(0x36102, 0x001A)  # Temp heap fills as much as 0x1A8000 (8000 is ORed in)
        rom_view.set_uint16(0x495D6, 0x001A)

        # gamemasterplc: patch both ROM address 0x50DA60 and 0x50DA80 with the value 0x24020001 to fix character unlocks
        # gamemasterplc: aka MIPS Instruction ADDIU V0, R0, 0x1
        scenes = _rom().get_scenes()
        player_select_scene = scenes.get_data_view(120)
        player_select_scene.set_uint32(0xBE60, 0x24020001)  # 0x50DA60
        player_select_scene.set_uint32(0xBE80, 0x24020001)  # 0x50DA80

        # This generally fixes duels on happening spaces.
        # gamemasterplc: try making 0x00111F04 in ROM 0x10800009 for a temporary fix for question space duels until we figure out events better
        board_play_scene = scenes.get_data_view(128)
        # boardPlayScene.setUint32(0x27774, 0x10800009); // 800FE2E4

        # The game will soft hang on the first player's turn when the number of plain spaces
        # (red/blue) is less than a certain lowish number.
        # gamemasterplc says it is related to some save flag check.
        # TODO: Waste time figuring out the exact low space threshold or the detailed cause of the bug.
        # Hang around 0x800FC664
        blue_space_count = 0
        red_space_count = 0
        for space in board["spaces"]:
            if space["type"] == Space.BLUE:
                blue_space_count += 1
            if space["type"] == Space.RED:
                red_space_count += 1
        if blue_space_count < 14 or red_space_count < 1:
            # Fix low spaces issues
            # gamemasterplc: patch ROM offset 0x001101C4 with 0x10000085 to fix low space hangs
            board_play_scene.set_uint32(0x25A34, 0x10000085)  # Something like BEQ R0 R0 0x85, so it always branches
            log("Patching for low space count.")

    def on_overwrite_promises(self, board, board_info, board_index):
        bg_index = board_info["bg_dir"]
        bg = board["bg"]
        otherbg = board.get("otherbg") or {}
        writes = [
            lambda: self._write_background(bg_index, bg["src"], bg["width"], bg["height"]),
            lambda: self._write_background(bg_index + 1, otherbg.get("largescene"), 320, 240),  # Game start, end
            lambda: self._write_background(bg_index + 2, bg["src"], 320, 240),  # Overview map
            lambda: self._write_additional_backgrounds(board),
            lambda: self.on_write_board_select_img(board, board_info),
            lambda: self.on_write_board_logo_img(board, board_info),  # Various board logos
            lambda: self._on_write_gate_img(board, board_info),
            lambda: self._brand_boot_splashscreen(),
        ]
        for write in writes:
            write()

    def on_after_save(self, rom_view):
        # This patch makes it so the game will boot if the emulator is misconfigured
        # with something other than 16K EEPROM save type. Obviously users should
        # set the correct save type, but this will let them play at least (with broken saving)
        # gamemasterplc: @PartyPlanner64 the jump you had to overwrite at 8000C2C0 is due
        # to the game needing 16k eeprom and emulators not setting it for modded roms
        rom_view.set_uint32(0x0000CEC0, 0)

        # The release ROM has debugger checks in it, which can cause some
        # emulators (Nemu64) to be upset. This stops the debugger checks.
        rom_view.set_uint32(0x0007FC58, 0)  # Don't check if KMC worked...
        rom_view.set_uint32(0x0007FC60, 0)  # Don't do KMC success action...
        # The "return;" is just hit after this and the rest of the checks are skipped.

    def on_write_events(self, board):
        pass

    def on_add_default_board_events(self, editor_activation_type, lst):
        if editor_activation_type == EditorEventActivationType.BEFORE_DICE_ROLL:
            activation_type = get_event_activation_type_from_editor_type(editor_activation_type)

            # MP3 has two "Before Dice Roll" default events.
            lst.add(activation_type, EventExecutionType.DIRECT,
                    "__PP64_INTERNAL_CURSE_POISON_DICEROLL_EVENT")
            lst.add(activation_type, EventExecutionType.DIRECT,
                    "__PP64_INTERNAL_REVERSAL_DICEROLL_EVENT")

    def hydrate_space(self, space, board, event_library):
        from ..boards import add_event_to_space_internal
        from ..events.events import create_event_instance
        from ..events.builtin.events_common import BankEvent

        if space["type"] == Space.BANK:
            add_event_to_space_internal(board, space, create_event_instance(BankEvent), False,
                                        event_library)

    def on_change_board_space_types_from_game_space_types(self, board, chains):
        board_type = board.get("type")
        is_normal_board = not board_type or board_type == BoardType.NORMAL
        if is_normal_board:
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
                15: Space.GAMEGUY,
                16: Space.OTHER,  # Toad
                17: Space.OTHER,  # Baby Bowser the COHORT
            }
        elif board_type == BoardType.DUEL:
            type_map = {
                1: Space.OTHER,
                2: Space.HAPPENING,
                3: Space.GAMEGUY,
                4: Space.OTHER,  # seen on spaces that have events
                5: Space.DUEL_REVERSE,
                6: Space.DUEL_BASIC,
                7: Space.DUEL_START_RED,
                8: Space.MINIGAME,
                9: Space.DUEL_START_BLUE,
                10: Space.DUEL_POWERUP,
            }
        else:
            raise ValueError("Unrecongized board type: %s" % (board_type,))

        for space in board["spaces"]:
            new_type = type_map.get(space["type"])
            if new_type is not None:
                space["type"] = int(new_type)

        if is_normal_board:
            if chains:
                start_space_index = at(chains[0], 0)
                if start_space_index is not None:
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
            Space.GAMEGUY: 15,  # ?
            Space.BLACKSTAR: 0,  # N/A
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

    def on_create_chain_events(self, board, chains):
        """Creates the chain-based event objects that we abstract out in the UI.

        Override from base to also add reverse shroom events and special chain split.
        """
        from ..boards import get_connections
        from ..events.events import create_event_instance
        from ..events.event_library import get_events_in_library
        from ..events.builtin.chain_merge_event import ChainMerge
        from ..events.builtin.mp3.u.chain_merge_event3 import ChainMerge3
        from ..events.builtin.mp3.u.chain_split3 import ChainSplit3

        def _get_chain_with_space(space):
            for c in range(len(chains)):
                if space in chains[c]:
                    # Should really be 0 always - game does support supplied index other than 0 though.
                    return c
            return None

        def _get_spaces_pointing_to_space(space):
            pointing_spaces = []
            for s in range(len(board["spaces"])):
                space_links = get_connections(s, board)
                if space in space_links:
                    pointing_spaces.append(s)
            return pointing_spaces

        def _chain_has_gate(chain):
            """Returns space index with gate, or None."""
            for i in chain:
                if board["spaces"][i].get("subtype") == SpaceSubtype.GATE:
                    return i
            return None

        def _needs_gate_chain_split(chain_indices):
            """Returns index of chain with gate."""
            chain_index = None
            for index in chain_indices:
                chain = at(chains, index)
                if chain is None:
                    raise TypeError("Cannot read properties of undefined (reading 'find')")
                space_index_with_gate = _chain_has_gate(chain)
                if space_index_with_gate is not None:
                    chain_index = index
            return chain_index

        def _chain_length(chain_index):
            chain = at(chains, chain_index)
            if chain is None:
                raise TypeError("Cannot read properties of undefined (reading 'length')")
            return len(chain)

        # There is either a merge or a split at the end of each chain.
        for i in range(len(chains)):
            chain = chains[i]
            # if (chain.length < 2) {
            #   throw new Error("MP3 onCreateChainEvents assertion failed: chain.length < 2");
            # }

            first_space = at(chain, 0)
            second_space = at(chain, 1)
            last_space = at(chain, len(chain) - 1)
            prev_space = at(chain, len(chain) - 2)  # For MP3
            end_links = get_connections(last_space, board)
            event = None
            if len(end_links) > 1:
                # A split, figure out the end points.

                if len(end_links) > 2:
                    raise ValueError("MP3 cannot support more than 2 split directions")

                chain_indices = []
                for link in end_links:
                    chain_indices.append(_get_chain_with_space(link))

                # Create the args, which are more sophisticated / declarative in MP3 (yay)
                # The args consist of the space indices and chain indices of the two directions,
                # as well as a couple variations of each when they are used with reverse shroom.
                space_index_args = []
                space_index_args.append(end_links[0])  # First two space indices
                space_index_args.append(end_links[1])
                space_index_args.append(0xFFFF)

                space_index_args.append(prev_space)  # As if returning from first link direction
                space_index_args.append(end_links[1])
                space_index_args.append(0xFFFF)

                space_index_args.append(prev_space)  # As if returning from 2nd link direction
                space_index_args.append(end_links[0])
                space_index_args.append(0xFFFF)
                space_index_args.append(0x0000)

                chain_args = []
                chain_args.append(chain_indices[0])  # Now the two chain indices and the "indices into the chains"
                chain_args.append(0x0000)  # We know these two are always 0 because of how we generate chains.
                chain_args.append(0x0000)  # mystery
                chain_args.append(chain_indices[1])
                chain_args.append(0x0000)
                chain_args.append(0x0000)  # mystery

                chain_args.append(i)
                chain_args.append(len(chain) - 2)  # Return to _near_ end of entering chain
                chain_args.append(0x0001)  # mystery
                chain_args.append(chain_indices[1])  # ...yes they flip, for confusion
                chain_args.append(0x0000)
                chain_args.append(0x0000)

                chain_args.append(i)
                chain_args.append(len(chain) - 2)  # Return to _near_ end of entering chain
                chain_args.append(0x0001)
                chain_args.append(chain_indices[0])
                chain_args.append(0x0000)
                chain_args.append(0x0000)

                chain_with_gate = _needs_gate_chain_split(chain_indices)
                if chain_with_gate is not None:
                    alt_chain_index = next((c for c in chain_indices if c != chain_with_gate), None)
                    event = create_event_instance(ChainSplit3, {
                        "parameterValues": {
                            "spaceIndexArgs": space_index_args,
                            "chainArgs": chain_args,
                            "hasgate": True,
                            "prevSpace": chains[chain_with_gate][0],
                            "altChain": [
                                alt_chain_index,  # Chain index
                                0,  # Index in chain
                            ],
                        },
                    })
                else:
                    event = create_event_instance(ChainSplit3, {
                        "parameterValues": {
                            "spaceIndexArgs": space_index_args,
                            "chainArgs": chain_args,
                        },
                    })
                _add_event_by_index(board, last_space, event, True, get_events_in_library())
            elif len(end_links) > 0:
                event = create_event_instance(ChainMerge3, {
                    "parameterValues": _defined({
                        "chain": _get_chain_with_space(end_links[0]),
                        "prevSpace": prev_space,  # For MP3
                    }),
                })
                _add_event_by_index(board, last_space, event, True, get_events_in_library())

            # See if we need a reverse split event, reverse chain merge, or safety chain merge.
            pointing_spaces = _get_spaces_pointing_to_space(first_space)
            if pointing_spaces:
                chain_indices = []
                for link in pointing_spaces:
                    chain_indices.append(_get_chain_with_space(link))

                if len(pointing_spaces) >= 2:
                    # Build a reverse split.
                    # FIXME: This obviously only deals with === 2, but rather than
                    # restrict boards, we can just arbitrarily not allow going backwards
                    # in some particular direction(s) for now.

                    # The reverse args are basically the same, except the 1 bit is placed differently.
                    space_index_args = []
                    space_index_args.append(second_space)
                    space_index_args.append(pointing_spaces[0])
                    space_index_args.append(0xFFFF)

                    space_index_args.append(pointing_spaces[1])  # Probably the only indices that matter
                    space_index_args.append(pointing_spaces[0])
                    space_index_args.append(0xFFFF)

                    space_index_args.append(pointing_spaces[1])
                    space_index_args.append(second_space)
                    space_index_args.append(0xFFFF)
                    space_index_args.append(0x0000)

                    # Now the chain indices and the "indices into the chains"
                    chain_args = []
                    chain_args.append(i)
                    chain_args.append(0x0001)  # Second space index
                    chain_args.append(0x0000)
                    chain_args.append(chain_indices[0])
                    chain_args.append(_chain_length(chain_indices[0]) - 1)  # Return to end of entering chain
                    chain_args.append(0x0001)

                    chain_args.append(chain_indices[1])
                    chain_args.append(_chain_length(chain_indices[1]) - 1)
                    chain_args.append(0x0001)
                    chain_args.append(chain_indices[0])
                    chain_args.append(_chain_length(chain_indices[0]) - 1)
                    chain_args.append(0x0001)

                    chain_args.append(chain_indices[1])
                    chain_args.append(_chain_length(chain_indices[1]) - 1)
                    chain_args.append(0x0001)
                    chain_args.append(i)
                    chain_args.append(0x0001)  # Second space index
                    chain_args.append(0x0000)

                    event = create_event_instance(ChainSplit3, {
                        "parameterValues": {
                            "spaceIndexArgs": space_index_args,
                            "chainArgs": chain_args,
                            "reverse": True,
                        },
                        "executionType": int(EventExecutionType.DIRECT),  # Notable difference
                    })
                    _add_event_by_index(board, first_space, event, True, get_events_in_library())
                elif len(pointing_spaces) == 1:
                    # Build a reverse merge
                    event = create_event_instance(ChainMerge3, {
                        "parameterValues": _defined({
                            "chain": chain_indices[0],  # Go to pointing chain
                            "spaceIndex": _chain_length(chain_indices[0]) - 1,  # Go to last space of pointing chain
                            "prevSpace": second_space,  # The 2nd space of this chain, which would have been previous when going reverse.
                        }),
                    })
                    _add_event_by_index(board, first_space, event, True, get_events_in_library())
            else:
                # If nothing points to this chain, the player could still reverse their
                # way towards the beginning of the chain (start space for example).
                # At the start of these chains, we put a type 8 event to spin them around.
                # It is redundant when going forward on the chain but doesn't hurt.
                first_links = get_connections(first_space, board)
                if len(first_links) > 1:
                    log("FIXME: branching isolated chain?")
                elif len(first_links) > 0:
                    # This doesn't crash, but it creates a back forth loop at a dead end.
                    # This probably will yield issues if the loop is over invisible spaces.
                    # Only do this if `firstLinks.length > 0`; if this is false, this is a single decorative space.
                    event = create_event_instance(ChainMerge, {
                        # Not CHAINMERGE3
                        "parameterValues": {
                            "chain": i,
                            "spaceIndex": 1,  # Because of chain padding, this should be safe
                        },
                    })
                    event["activationType"] = int(EditorEventActivationType.BEGINORWALKOVER)
                    _add_event_by_index(board, first_space, event, True, get_events_in_library())

    def on_parse_strings(self, board, board_info):
        strs = board_info.get("str") or {}
        if strs.get("board_select"):
            if not isinstance(strs["board_select"], list):
                raise ValueError("Expected number[][]")
            idx = strs["board_select"][0]
            strings3 = _rom().get_strings3()
            text = strings3.read("en", idx[0], idx[1])
            lines = text.split("\n")

            # Read the board name and description.
            name_start = lines[0].find(">") + 2
            name_end = lines[0].find("{", name_start)
            board["name"] = substring(lines[0], name_start, name_end)
            board["description"] = "\n".join([at(lines, 1) or "", at(lines, 2) or ""])

            # Parse difficulty star level
            board["difficulty"] = count_occurrences(text, self.get_character_map()[0x3B])

    def on_write_strings(self, board, board_info):
        from ..fs.strings import str_to_bytes

        strs = board_info.get("str") or {}
        strings3 = _rom().get_strings3()
        board_select = strs.get("board_select")
        if board_select:
            bytes_ = []
            bytes_.append(0x0B)  # Clear?
            bytes_.append(0x05)  # Start GREEN
            bytes_.append(0x0F)  # ?
            bytes_ += str_to_bytes(board.get("name") or "")
            bytes_.append(0x16)
            bytes_.append(0x19)
            bytes_.append(0x0F)
            bytes_ += [0x20, 0x20, 0x20, 0x20]  # Spaces
            bytes_.append(0x16)
            bytes_.append(0x03)
            bytes_.append(0x0F)
            bytes_ += str_to_bytes("Difficulty: ")
            star = 0x3B
            _append_difficulty(bytes_, board, star)
            bytes_.append(0x16)
            bytes_.append(0x19)
            bytes_.append(0x0A)  # \n
            bytes_ += str_to_bytes(board.get("description") or "")  # Assumes \n's are correct within.
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)

            idx = board_select[0]
            strings3.write("en", idx[0], idx[1], str_buffer)

            # The second copy is mostly the same, but add a couple more bytes at the end.
            bytes_.pop()  # Null byte
            bytes_.append(0x19)
            bytes_.append(0xFF)
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)

            idx = board_select[1]
            strings3.write("en", idx[0], idx[1], str_buffer)

        if strs.get("board_greeting"):
            bytes_ = []
            bytes_.append(0x0B)
            bytes_ += str_to_bytes("You're all here!")
            bytes_.append(0x0A)  # \n
            bytes_ += self._create_board_greeting_base(board.get("name"))
            bytes_.append(0x0B)  # ?
            bytes_ += str_to_bytes("Now, before we begin, we need\nto determine the turn order.")
            bytes_.append(0x19)  # ?
            bytes_.append(0xFF)  # ?
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            strings3.write("en", strs["board_greeting"][0], strs["board_greeting"][1], str_buffer)

        if strs.get("board_greeting_duel"):
            bytes_ = []
            bytes_.append(0x0B)
            bytes_ += str_to_bytes("I've been waiting for you, ")
            bytes_.append(0x11)  # ?
            bytes_.append(0xC2)  # ?
            bytes_.append(0x0A)  # \n
            bytes_ += self._create_board_greeting_base(board.get("name"))
            bytes_.append(0x0B)  # ?
            bytes_ += str_to_bytes("And just as promised, if you win here...")
            bytes_.append(0x19)  # ?
            bytes_.append(0xFF)  # ?
            bytes_.append(0x00)  # Null byte

            str_buffer = to_bytes_array(bytes_)
            strings3.write("en", strs["board_greeting_duel"][0], strs["board_greeting_duel"][1],
                           str_buffer)

        if strs.get("board_names"):
            bytes_ = []
            bytes_.append(0x0B)
            bytes_ += str_to_bytes(board.get("name"))
            bytes_.append(0x00)  # Null byte
            str_buffer = to_bytes_array(bytes_)

            for idx in strs["board_names"]:
                strings3.write("en", idx[0], idx[1], str_buffer)

    def _create_board_greeting_base(self, board_name):
        from ..fs.strings import str_to_bytes

        bytes_ = list(str_to_bytes("Welcome to the legendary "))
        bytes_.append(0x05)  # Start GREEN
        bytes_.append(0x0F)  # ?
        bytes_ += str_to_bytes(board_name)
        bytes_.append(0x16)  # ?
        bytes_.append(0x19)  # ?
        bytes_.append(0xC2)  # ?
        bytes_.append(0x19)  # ?
        bytes_.append(0xFF)  # ?
        bytes_.append(0x0B)  # ?
        bytes_ += str_to_bytes("Here, you'll battle to become\nthe Superstar.")
        bytes_.append(0x19)  # ?
        bytes_.append(0xFF)  # ?
        return bytes_

    def on_parse_board_select_img(self, board, board_info):
        if not board_info.get("img") or not board_info["img"].get("board_select_img"):
            return

        board["otherbg"]["boardselect"] = self._read_img_from_main_fs(
            20, board_info["img"]["board_select_img"], 0)

    def on_write_board_select_img(self, board, board_info):
        board_select_img = board_info.get("img") and board_info["img"].get("board_select_img")
        if not board_select_img:
            return

        from ..utils.img.img_pack import to_pack

        img_buffer = canvas.get_image_data(board["otherbg"].get("boardselect"), 64, 64).data

        # First, read the old image pack.
        mainfs = _rom().get_main_fs()
        old_pack = mainfs.get(20, board_select_img)

        # Then, pack the image and write it.
        img_info_arr = [
            {
                "src": img_buffer,
                "width": 64,
                "height": 64,
                "bpp": 32,
            },
        ]
        new_pack = to_pack(img_info_arr, 16, 0, old_pack)
        # saveAs(new Blob([newPack]), "imgpack");
        mainfs.write(20, board_select_img, new_pack)

    def on_parse_board_logo_img(self, board, board_info):
        if not board_info.get("img") or not board_info["img"].get("splash_logo_img"):
            return

        board["otherbg"]["boardlogo"] = self._read_img_from_main_fs(
            19, board_info["img"]["splash_logo_img"], 0)
        board["otherbg"]["boardlogotext"] = self._read_img_from_main_fs(
            19, board_info["img"].get("splash_logo_text_img"), 0)

    def on_write_board_logo_img(self, board, board_info):
        self._write_board_logo_large(board, board_info)
        self._write_board_logo_text_img(board, board_info)
        self._write_board_logo_medium(board, board_info)
        self._write_board_logo_small(board, board_info)

    def _write_logo_pack(self, src, width, height, dir, file):
        from ..utils.img.img_pack import to_pack

        img_data = (canvas.get_image_data(src, width, height).data if src
                    else bytearray(width * height * 4))

        # First, read the old image pack.
        mainfs = _rom().get_main_fs()
        old_pack = mainfs.get(dir, file)

        # Then, pack the image and write it.
        img_info_arr = [
            {
                "src": img_data,
                "width": width,
                "height": height,
                "bpp": 32,
            },
        ]
        new_pack = to_pack(img_info_arr, 16, 0, old_pack)
        # saveAs(new Blob([newPack]), "imgpack");
        mainfs.write(dir, file, new_pack)

    def _write_board_logo_large(self, board, board_info):
        splash_logo_img = board_info.get("img") and board_info["img"].get("splash_logo_img")
        if not splash_logo_img:
            return

        width, height = 226, 110
        self._write_logo_pack(board["otherbg"].get("boardlogo"), width, height, 19, splash_logo_img)

    def _write_board_logo_text_img(self, board, board_info):
        """Write the intro logo text image."""
        splash_logo_text_img = board_info.get("img") and board_info["img"].get("splash_logo_text_img")
        if not splash_logo_text_img:
            return

        width, height = 226, 36
        self._write_logo_pack(board["otherbg"].get("boardlogotext"), width, height, 19,
                              splash_logo_text_img)

    def _write_board_logo_medium(self, board, board_info):
        """Replace the medium board logo. This is shown on the board pause screen."""
        pause_logo_img = board_info["img"].get("pause_logo_img")
        if not pause_logo_img:
            return

        width, height = 150, 50
        self._write_logo_pack(board["otherbg"].get("boardlogomedium"), width, height, 19,
                              pause_logo_img)

    def _write_board_logo_small(self, board, board_info):
        """Replace the small board logo. This is shown on the game end details viewer."""
        stats_logo_img = board_info["img"].get("stats_logo_img")
        if not stats_logo_img:
            return

        width, height = 100, 46
        self._write_logo_pack(board["otherbg"].get("boardlogosmall"), width, height,
                              stats_logo_img[0], stats_logo_img[1])

    def _on_write_gate_img(self, board, board_info):
        """Create generic skeleton key gate."""
        gate_index = board_info.get("img") and board_info["img"].get("gate_img")
        if not gate_index:
            return

        from ..models.form import FORM
        from ..utils.img.bmp import bm_pfrom_rgba

        # We need to write the image onto a canvas to get the RGBA32 values.
        width, height = 64, 64

        img_data = canvas.get_image_data(genericgate_image, width, height)

        # First create a BMP
        gate_bmp = bm_pfrom_rgba(img_data.data, 32, 8)

        # Now write the BMP back into the FORM.
        mainfs = _rom().get_main_fs()
        gate_form = mainfs.get(19, 366)  # Always use gate 3 as a base.
        gate_unpacked = FORM.unpack(gate_form)
        FORM.replace_bmp(gate_unpacked, 0, gate_bmp[0], gate_bmp[1])

        # Now write the FORM.
        gate_packed = FORM.pack(gate_unpacked)
        # saveAs(new Blob([gatePacked]), "gatePacked");
        mainfs.write(19, gate_index, gate_packed)

    # Writes to 0x800A1904, break 0x8004a520 (JAL 0C012948)
    def get_audio_map(self, table_index):
        return [
            "Opening",  # 0x00
            "Opening Demo",
            "Title Screen",
            "Select File",
            "Castle Grounds",
            "",  # Two Beeps
            "Staff Roll",
            "Inside the Castle",
            "Free-Play Room",
            "Star Lift",
            "Preparations",
            "Rules Map",
            "",  # Two Beeps
            "The Adventure Begins",
            "",  # Two Beeps
            "The Adventure Ends",
            "Begin Mini-Game",  # 0x10
            "",  # Two Beeps
            "Here's the Star",
            "Still Going",
            "Mini-Game End 1",
            "Mini-Game End 2",
            "Mini-Game End 3",
            "Commence Attack!",
            "Chilly Waters",
            "Deep Bloober Sea",
            "Spiny Desert",
            "Woody Woods",
            "Creepy Cavern",
            "Waluigi",
            "Good Luck!",
            "The Winner is... Me!",
            "A Winner is ME!",  # 0x20
            "Foolish Bowser",
            "",  # Two Beeps
            "",  # Two Beeps
            "Bowser Event",
            "",  # Two Beeps
            "Bring it On!",
            "",  # Two Beeps
            "Waluigi Appears!",
            "VS Millennium Star!",
            "Peaceful song, bells",
            "",  # Two Beeps
            "Defeat...",
            "Aim",
            "Don't Hurry",
            "Panic!",
            "Fighting Spirit",  # 0x30
            "Got It?",
            "Let's Get a Move On",
            "Looking Ahead",
            "Big Trouble!",
            "What To Do!?!",
            "Mustn't Panic",
            "Nice and Easy",
            "On Your Toes",
            "Prologue 1",
            "Prologue 2",
            "Prologue 3",
            "Genie's Theme",
            "Jeanie's Theme",
            "Start Battle",
            "Bang Out a Drum Intro",
            "Bang Out a Drum Fill",  # 0x40
            "Stardust Battle",
            "Chance Time",
            "Game Guy Mini-Game",
            "Item Mini-Game",
            "Mushroom Power-Up!",
            "Game Guy Winner!",
            "Game Guy Loser!",
            "Game Guy Dance",
            "Drum Roll",
            "Sound Config",
            "",  # Two Beeps
            "Battle Room",
            "Gamble Room",
            "Murmur",
            "Tension Drums",
            "",  # Two Beeps // 0x50
            "",  # "Chilly Waters splashscreen fanfare" // 0x6E
            "",  # "Quick fanfare" // 0x70
            "",  # "Sad fanfare" // 0x71
            "",  # "Medium fanfare" // 0x72
            "",  # "Fanfare" // 0x73
        ]

    def get_sound_effect_map(self, table):
        from .mp3_u_soundeffects import get_sound_effect_map_mp3
        return get_sound_effect_map_mp3(table)

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
            # 0x10: " ", works but not used?
            0x11: "{0}",  # These are format params that get replaced with various things
            0x12: "{1}",
            0x13: "{2}",
            0x14: "{3}",
            0x15: "{4}",
            0x16: "{5}",
            # Theoretically there may be more up through 0x20?
            # 0x18 - nothing
            0x20: " ",
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
            0x7E: "&",  # ~
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
