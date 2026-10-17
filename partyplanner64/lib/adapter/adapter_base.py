"""The base of the game adapters (port of adapter/AdapterBase.ts).

An adapter reads the boards of a game out of a ROM (load_boards) and writes
a board over one of the game's boards (overwrite_board). MP1Adapter,
MP2Adapter and MP3Adapter fill in the game specifics.

Everything here is synchronous; the TypeScript's promises are plain calls.
Other modules (boards, events, file systems) are imported inside the
functions that use them: boards imports the adapters, which import those.
"""

import json
import os

from ..types import (
    BoardType,
    EditorEventActivationType,
    EventActivationType,
    SpaceSubtype,
    get_event_activation_type_from_editor_type,
)
from ..debug import is_debug
from ..utils.debug import log, hexstr, assert_
from ..utils.number import distance
from ..utils.obj import copy_object
from ..utils.dataview import DataView
from ..utils import canvas
from ..utils.three_math import PerspectiveCamera, Vector3
from ._js import at, is_number, js_keys, js_number_str, js_round, json_stringify
from .boardinfo import get_board_infos, get_board_info_by_index
from .boarddef import (
    determine_chains,
    pad_chains,
    create as create_board_def,
    parse as parse_board_def,
)
from .eventtable import SpaceEventTable
from .eventlist import SpaceEventList

_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img")

bootsplash_image = os.path.join(_IMG_DIR, "bootsplash.png")


def _romhandler():
    from ..romhandler import romhandler
    return romhandler


def _rom():
    return _romhandler().get_rom()


def _value(enum_or_value):
    """The plain value of an enum member (as board JSON holds it)."""
    return getattr(enum_or_value, "value", enum_or_value)


def _space(board, index):
    """board.spaces[index], or None (undefined) when there is no such space."""
    return at(board["spaces"], index)


def _add_event_by_index(board, space_idx, event, to_start, event_library):
    """boards.add_event_by_index, failing like JavaScript on a missing space."""
    from ..boards import add_event_by_index
    if _space(board, space_idx) is None:
        raise TypeError("Cannot set properties of undefined (space %s)" % (space_idx,))
    add_event_by_index(board, space_idx, event, to_start, event_library)


class AdapterBase:
    # The arbitrary upper bound size of the events ASM blob.
    EVENT_MEM_SIZE = 0x50000

    # Location that custom ASM will be placed in RAM.
    # 0x807B0000 right now
    EVENT_RAM_LOC = (0x80000000 | (0x800000 - EVENT_MEM_SIZE)) & 0xFFFFFFFF

    # We reserve a 16 byte header, mainly to allow the ASM hook to be flexible
    # in where it transfers this blob to in RAM.
    EVENT_HEADER_SIZE = 16

    # Set by each game's adapter.
    game_version = None
    board_def_directory = None
    nintendo_logo_fs_entry = None
    hudson_logo_fs_entry = None
    MAINFS_READ_ADDR = None
    TABLE_HYDRATE_ADDR = None
    HEAP_FREE_ADDR = None

    # Optional hooks (methods in the game adapters), as in the TypeScript:
    # on_load(board, board_info, board_was_stashed)
    # on_after_overwrite(rom_view, board_copy, board_info, board_index)
    # on_write_events(board)
    on_load = None
    on_after_overwrite = None
    on_write_events = None

    def __init__(self, options=None):
        """Args:
            options: IAdapterOptions dict: {"write_branding": bool}.
        """
        self.options = options if options is not None else {}

        # Defaults
        if "write_branding" not in self.options:
            self.options["write_branding"] = True

    def load_boards(self):
        """Read the boards of the loaded ROM. Returns a list of boards."""
        boards = []
        rom = _rom()
        game = rom.get_game()
        board_infos = get_board_infos(game)
        if board_infos is None:
            log("Game %s has no board infos defined in PP64" % (game,))
            return []

        for i in range(len(board_infos)):
            if is_debug():
                log("Board %d" % i)

            board_info = board_infos[i]
            bg_dir = board_info["bg_dir"]
            hvqfs = rom.get_hvqfs()
            background = hvqfs.read_background(bg_dir)

            board_from_rom = self._pull_board_from_rom(board_info)
            if board_from_rom is not None:
                new_board = board_from_rom
                new_board["bg"] = background
                new_board["otherbg"] = {}
            else:
                partial_board = {
                    "game": self.game_version,
                    "type": _value(board_info.get("type") or BoardType.NORMAL),
                    "bg": background,
                    "otherbg": {},
                    "events": {},
                }
                mainfs = rom.get_main_fs()
                board_buffer = mainfs.get(self.board_def_directory, board_info["board_def_file"])
                new_board = parse_board_def(board_buffer, partial_board)
                chains = new_board.pop("_chains")
                log("Board %d chains: " % i, chains)

                self.on_change_board_space_types_from_game_space_types(new_board, chains)
                self._apply_perspective(new_board)
                self._clean_loaded_board(new_board)

                self._parse_audio(new_board, board_info)

                self._find_event_table_locations(board_info)
                self._extract_events(board_info, new_board, i, chains)
                self._extract_star_guardians(new_board, board_info)
                self._extract_boos(new_board, board_info)

            self.on_parse_strings(new_board, board_info)
            if not new_board.get("name"):
                new_board["name"] = board_info.get("name") or ""

            self.on_parse_board_select_img(new_board, board_info)
            self.on_parse_board_logo_img(new_board, board_info)

            if board_info.get("on_load"):
                board_info["on_load"](new_board)

            if self.on_load:
                self.on_load(new_board, board_info, board_from_rom is not None)

            # (Python port) The editor says why the background is black.
            if hvqfs.is_hvq_compressed(bg_dir):
                new_board["_bgHvq"] = True

            boards.append(new_board)

        if is_debug():
            # Debug if audio offsets are right.
            audio = rom.get_audio()
            audio_section_count = len(audio.get_patch_info())
            for i in range(audio_section_count):
                audio.get_rom_offset(i)

        return boards

    def overwrite_board(self, board_index, board):
        """Write a board over the ROM's board at board_index. Returns when done."""
        romhandler = _romhandler()
        board_copy = copy_object(board)
        board_info = get_board_info_by_index(romhandler.get_rom_game(), board_index)

        chains = determine_chains(board_copy)
        pad_chains(board_copy, chains)

        # If the user didn't place enough 3d characters, banish them to this dead space off screen.
        from ..boards import get_dead_space
        get_dead_space(board_copy)  # Trigger creation before boarddef is created.

        self.on_change_game_space_types_from_board_space_types(board_copy)
        self._reverse_perspective(board_copy)

        boarddef = create_board_def(board_copy, chains)
        mainfs = romhandler.get_rom().get_main_fs()
        mainfs.write(self.board_def_directory, board_info["board_def_file"], boarddef)

        self._create_gate_events(board_copy, board_info, chains)
        audio_indices = self.on_write_audio(board_copy, board_info, board_index)

        event_syms = self._write_new_board_overlay(board_copy, board_info, board_index, audio_indices)

        self.on_write_strings(board_copy, board_info)

        # Write out the board events to ROM.
        self.on_create_chain_events(board_copy, chains)
        self._create_star_events(board_copy)
        if board_info.get("on_write_events"):
            board_info["on_write_events"](board_copy)
        if self.on_write_events:
            self.on_write_events(board_copy)
        self._write_events(board_copy, board_info, board_index, chains, event_syms, audio_indices)

        self._clear_other_board_names(board_index)
        self._stash_board_into_rom(board, board_info)  # Don't use the boardCopy here

        hvqfs = romhandler.get_rom().get_hvqfs()
        hvqfs.update_metadata(board_info["bg_dir"], board_copy["bg"])

        if board_info.get("on_after_overwrite"):
            board_info["on_after_overwrite"](board_copy)

        rom_view = romhandler.get_data_view()
        if self.on_after_overwrite:
            self.on_after_overwrite(rom_view, board_copy, board_info, board_index)

        self.on_overwrite_promises(board, board_info, board_index)

    def _write_new_board_overlay(self, board, board_info, board_index, audio_indices):
        from ..events.prep_asm import make_game_symbol_labels, make_generic_symbols_for_addresses
        from ..mips import assemble

        romhandler = _romhandler()
        overlay_asm = self.on_create_board_overlay(board, board_info, board_index, audio_indices)
        game = romhandler.get_rom_game()
        asm = ("\n        " + "\n".join(make_game_symbol_labels(game, True))
               + "\n        " + "\n".join(make_generic_symbols_for_addresses(overlay_asm))
               + "\n\n        " + overlay_asm
               + "\n      ")
        log(asm)
        out_syms = {}
        buffer = assemble(asm, symbol_output_map=out_syms)

        # TODO if (buffer.byteLength > some max) {
        #   throw new Error(``);
        # }

        scenes = romhandler.get_rom().get_scenes()
        scene_info = scenes.get_info(board_info["scene_index"])
        event_syms = self._make_symbols_for_event_assembly(out_syms, scene_info)

        # Replace the overlay. We actually have enough info to accurately define
        # the code/rodata/bss regions.
        # (An overlay without rodata/bss labels gives NaN values in the TypeScript,
        # which Scenes.replace ignores, and keeps the whole buffer: None does the same.)
        rodata = out_syms.get("rodata")
        bss = out_syms.get("bss")
        code_start = scene_info["code_start"]
        scenes.replace(board_info["scene_index"], bytearray(buffer[0:bss]), {
            "code_end": None if rodata is None else code_start + rodata,
            "rodata_start": None if rodata is None else code_start + rodata,
            "rodata_end": None if bss is None else code_start + bss,
            "bss_start": None if bss is None else code_start + bss,
            "bss_end": code_start + len(buffer),
        })
        return event_syms

    def on_create_board_overlay(self, board, board_info, board_index, audio_indices):
        raise NotImplementedError("Adapter does not implement onCreateBoardOverlay")

    def on_after_save(self, rom_view):
        pass

    def on_overwrite_promises(self, board, board_info, board_index):
        raise NotImplementedError("Adapter does not implement onOverwritePromises")

    def hydrate_space(self, space, board, event_library):
        """Gives a new space the default things it would need."""
        raise NotImplementedError("hydrateSpace not implemented")

    def on_parse_strings(self, board, board_info):
        log("Adapter does not implement onParseStrings")

    def on_write_strings(self, board, board_info):
        log("Adapter does not implement onWriteStrings")

    def _make_camera(self, board):
        bg = board["bg"]
        width, height = bg["width"], bg["height"]
        camera = PerspectiveCamera(bg["fov"], width / height, 1, 10000)
        if board.get("game") == 1:
            camera.position.set(bg["cameraEyePosX"], bg["cameraEyePosY"], bg["cameraEyePosZ"])
        else:
            # gamemasterplc says don't divide anything by 1.2 if bg.cameraEyePosY === 1000,
            # according to game logic.
            # Observation: 18 / 15 == 1.2, this relates to tile count
            camera.position.set(
                bg["cameraEyePosX"] / 1.2,
                bg["cameraEyePosY"] / 1.2,
                bg["cameraEyePosZ"] / 1.2,
            )
        camera.look_at(Vector3(bg["lookatPointX"], bg["lookatPointY"], bg["lookatPointZ"]))
        camera.scale.y = -1
        camera.update_matrix()
        camera.update_matrix_world(True)
        camera.update_projection_matrix()
        return camera

    def _apply_perspective(self, board):
        """Convert game (3d) space coordinates to board image coordinates."""
        bg = board["bg"]
        width, height = bg["width"], bg["height"]
        camera = self._make_camera(board)

        for space in board["spaces"]:
            space_point = Vector3(space["x"], space["y"], space.get("z") or 0)
            if board.get("game") in (2, 3):
                space_point.x *= bg["scaleFactor"] / 1.2
                space_point.y *= bg["scaleFactor"] / 1.2
                space_point.z *= bg["scaleFactor"] / 1.2

            vector = space_point.project(camera)
            width_half = width / 2
            height_half = height / 2
            space["x"] = js_round(vector.x * width_half + width_half)
            space["y"] = js_round(-(vector.y * height_half) + height_half)
            space["z"] = 0

    def _reverse_perspective(self, board):
        """Convert board image coordinates to game (3d) space coordinates."""
        bg = board["bg"]
        width, height = bg["width"], bg["height"]
        camera = self._make_camera(board)

        for space in board["spaces"]:
            vec2d = Vector3(
                (space["x"] / width) * 2 - 1,
                -(space["y"] / height) * 2 + 1,
                0.5,
            )

            vec2d.unproject(camera)
            vec2d.sub(camera.position).normalize()
            dist = -camera.position.z / vec2d.z
            pos = Vector3()
            pos.copy(camera.position).add(vec2d.multiply_scalar(dist))

            if board.get("game") in (2, 3):
                pos.x /= bg["scaleFactor"] / 1.2
                pos.y /= bg["scaleFactor"] / 1.2
                pos.z /= bg["scaleFactor"] / 1.2

            space["x"] = pos.x
            space["y"] = pos.y
            space["z"] = pos.z

    def on_get_game_coords_from_board_coords(self, x, y, z, board):
        log("Adapter does not implement onGetGameCoordsFromBoardCoords")
        return [x, y, z]

    def on_change_board_space_types_from_game_space_types(self, board, chains):
        log("Adapter does not implement onChangeBoardSpaceTypesFromGameSpaceTypes")

    def on_change_game_space_types_from_board_space_types(self, board):
        log("Adapter does not implement onChangeGameSpaceTypesFromBoardSpaceTypes")

    def _offset_to_addr(self, offset, board_info):
        """Converts a ROM address to an in-game RAM offset.

        Assumes the offset is within the scene overlay for the given board.

        Args:
            offset: ROM offset to convert
            board_info: Board info related to the offset
        """
        scene_index = board_info.get("scene_index")
        if is_number(scene_index) and scene_index >= 0:
            scenes = _rom().get_scenes()
            scene_info = scenes.get_info(scene_index)
            if offset < scene_info["rom_start"]:
                # This is an offset that is already relative to the scene.
                return (scene_info["ram_start"] & 0x7FFFFFFF) + offset
            else:
                return (scene_info["ram_start"] & 0x7FFFFFFF) - (scene_info["rom_start"] - offset)

        raise ValueError("How do I _offsetToAddr?")

    def _offset_to_addr_base(self, offset, base):
        return (base + offset) & 0xFFFFFFFF

    def _addr_to_offset_base(self, addr, base):
        return ((addr & 0x7FFFFFFF) - (base & 0x7FFFFFFF)) & 0xFFFFFFFF

    def _stash_board_into_rom(self, board, board_info):
        if not board_info.get("mainfs_board_file"):
            return

        board_copy = copy_object(board)
        board_copy.pop("bg", None)
        board_copy.pop("otherbg", None)
        board_copy.pop("animbg", None)
        board_copy.pop("_bgHvq", None)  # (Python port) worked out again on load
        board_json_buffer = _string_to_array_buffer(_json_stringify(board_copy))

        dir, file = board_info["mainfs_board_file"]
        mainfs = _rom().get_main_fs()
        mainfs.write(dir, file, board_json_buffer)

    def _pull_board_from_rom(self, board_info):
        if not board_info.get("mainfs_board_file"):
            return None

        dir, file = board_info["mainfs_board_file"]
        mainfs = _rom().get_main_fs()
        if not mainfs.has(dir, file):
            return None

        board_json_buffer = mainfs.get(dir, file)
        board = json.loads(_string_from_array_buffer(board_json_buffer))
        return board

    def _clean_loaded_board(self, board):
        """Handles any _deadSpace we may have added in overwriteBoard."""
        last_idx = len(board["spaces"]) - 1
        last_space = at(board["spaces"], last_idx)
        if (last_space and last_space["x"] > board["bg"]["width"] + 50
                and last_space["y"] > board["bg"]["height"] + 50):
            log("Pruning dead space", last_space)
            del board["spaces"][last_idx]

    def _find_event_table_locations(self, board_info):
        scene_index = board_info.get("scene_index")
        if not is_number(scene_index) or scene_index < 0:
            return

        from ..symbols.symbols import get_symbol
        from ..utils.mips import find_calls, get_reg_set_address

        rom = _rom()
        game = rom.get_game()
        hydrate_event_table_addr = get_symbol(game, "EventTableHydrate")
        scenes = rom.get_scenes()
        scene_info = scenes.get_info(scene_index)
        board_code_data_view = scenes.get_code_data_view(scene_index)
        table_calls = find_calls(board_code_data_view, hydrate_event_table_addr)

        space_event_tables = []
        if board_info.get("space_event_tables") is None:
            board_info["space_event_tables"] = space_event_tables
        for call_offset in table_calls:
            upper = board_code_data_view.get_uint32(call_offset - 4)
            lower = board_code_data_view.get_uint32(call_offset + 4)
            table_addr = get_reg_set_address(upper, lower)
            table_offset = self._addr_to_offset_base(table_addr, scene_info["ram_start"])
            log("Found event table %s (ROM %s)" % (hexstr(table_addr), hexstr(table_offset)))
            space_event_tables.append({"table_offset": table_offset})

    def _extract_events(self, board_info, board, board_index, chains):
        # (An empty list of tables is truthy in JavaScript: go on then.)
        if board_info.get("space_event_tables") is None or not board_info.get("scene_index"):
            return

        from ..utils.mips import get_reg_set_address
        from ..events.events import parse as parse_event
        from ..events.event_library import get_events_in_library

        romhandler = _romhandler()
        scene_index = board_info["scene_index"]

        # PP64 sometimes stores board ASM in the main filesystem. We need to
        # be able to parse both that or the stock boards.
        buffer = None
        buffer_view = None
        event_table = SpaceEventTable()
        if board_info.get("mainfs_event_file"):
            main_fs_dir, main_fs_file = board_info["mainfs_event_file"]
            mainfs = romhandler.get_rom().get_main_fs()
            if mainfs.has(main_fs_dir, main_fs_file):
                buffer = mainfs.get(main_fs_dir, main_fs_file)
                buffer_view = DataView(buffer)

                event_table.parse(buffer, 0x10)  # TODO: Multi-table.

        scenes = romhandler.get_rom().get_scenes()
        scene_info = scenes.get_info(scene_index)
        if buffer is None:
            buffer_view = scenes.get_data_view(scene_index)
            buffer = buffer_view.buffer

            for table_deflate_call in board_info["space_event_tables"]:
                # Each board can have several event tables, which it "deflates" by
                # passing the table address to some function. We are parsing the table
                # addresses from those calls, because that gives us the flexibility
                # to reposition the tables and find them again later.
                if table_deflate_call.get("table_offset"):
                    table_offset = table_deflate_call["table_offset"]
                else:
                    upper = buffer_view.get_uint32(table_deflate_call["upper"])
                    lower = buffer_view.get_uint32(table_deflate_call["lower"])
                    if not upper and not lower:
                        continue
                    table_addr = get_reg_set_address(upper, lower)
                    table_offset = self._addr_to_offset_base(table_addr, scene_info["ram_start"])

                event_table.parse(buffer, table_offset)  # Build up all the events into one collection.

        for event_table_entry in event_table.entries():
            cur_space_index = event_table_entry["space_index"]
            if cur_space_index < 0:
                log("Space event on negative space %d" % cur_space_index)

            # Figure out the current info struct offset in the ROM.
            cur_info_addr = event_table_entry["address"] & 0x7FFFFFFF
            if cur_info_addr > (self.EVENT_RAM_LOC & 0x7FFFFFFF):
                cur_info_offset = self._addr_to_offset_base(cur_info_addr, self.EVENT_RAM_LOC)
            else:
                cur_info_offset = self._addr_to_offset_base(cur_info_addr, scene_info["ram_start"])
            board_list = SpaceEventList()
            board_list.parse(buffer, cur_info_offset)
            for list_entry in board_list.entries():
                # Figure out the event ASM info in ROM.
                asm_addr = list_entry.address & 0x7FFFFFFF
                if asm_addr > (self.EVENT_RAM_LOC & 0x7FFFFFFF):
                    asm_offset = self._addr_to_offset_base(asm_addr, self.EVENT_RAM_LOC)
                    code_view = buffer_view
                else:
                    # This event actually points back to the original ROM.
                    asm_offset = self._addr_to_offset_base(asm_addr, scene_info["ram_start"])
                    code_view = scenes.get_data_view(scene_index)

                event_info = parse_event(code_view, {
                    "addr": asm_addr,
                    "offset": asm_offset,
                    "board": board,
                    "board_index": board_index,
                    "cur_space": cur_space_index,  # TODO: Pass space or get rid of this
                    "cur_space_index": cur_space_index,
                    "chains": chains,
                    "game": romhandler.get_rom_game(),
                    "game_version": self.game_version,
                })

                # We parsed an actual event.
                if event_info and event_info is not True:
                    event_info["activationType"] = list_entry.activation_type
                    event_info["executionType"] = list_entry.execution_type
                    _add_event_by_index(board, cur_space_index, event_info, False,
                                        get_events_in_library())

                    # console.log(`Found event 0x${asmOffset.toString(16)} (${eventInfo.name})`);
                elif not event_info:
                    # console.log(`Unknown event 0x${asmOffset.toString(16)} on board ${boardIndex} (${boardInfo.name})`);
                    pass

                if is_debug():
                    if list_entry.activation_type not in [t.value for t in EventActivationType]:
                        log("Unknown event activation type %s, boardIndex: %d, spaceIndex: %s"
                            % (hexstr(list_entry.activation_type), board_index,
                               hexstr(cur_space_index)))

    def on_create_chain_events(self, board, chains):
        """Creates the chain-based event objects that we abstract out in the UI."""
        from ..boards import get_connections
        from ..events.events import create_event_instance
        from ..events.event_library import get_events_in_library
        from ..events.builtin.chain_merge_event import ChainMerge

        def _get_chain_with_space(space):
            for c in range(len(chains)):
                if space in chains[c]:
                    # Should really be 0 always - game does support supplied index other than 0 though.
                    return c
            return None

        # There is either a merge or a split at the end of each chain.
        for i in range(len(chains)):
            chain = chains[i]
            last_space = chain[-1] if chain else None
            links = get_connections(last_space, board)
            event = None
            if len(links) > 1:
                # A split, figure out the end points.
                endpoints = []
                for link in links:
                    endpoints.append(_get_chain_with_space(link))
                if len(links) > 2:
                    raise ValueError("Encountered branch with %d directions, only 2 are supported currently"
                                     % len(links))
                if self.game_version == 1:
                    from ..events.builtin.mp1.u.chain_split1 import ChainSplit1 as ChainSplit
                else:
                    from ..events.builtin.mp2.u.chain_split2 import ChainSplit2 as ChainSplit
                event = create_event_instance(ChainSplit, {
                    "parameterValues": {
                        "left_space": links[0],
                        "right_space": links[1],
                        "chains": endpoints,
                    },
                })
            elif len(links) > 0:
                event = create_event_instance(ChainMerge, {
                    "parameterValues": _defined({
                        "chain": _get_chain_with_space(links[0]),
                    }),
                })

            if event:
                _add_event_by_index(board, last_space, event, True, get_events_in_library())

    def _create_star_events(self, board):
        """Adds the star events we abstract in the UI."""
        from ..boards import add_event_to_space_internal
        from ..events.events import create_event_instance
        from ..events.event_library import get_events_in_library
        from ..events.builtin.events_common import StarEvent

        for space in board["spaces"]:
            if not space or not space.get("star"):
                continue
            events = space.get("events") or []
            has_star_event = any(e["id"] == "STAR" for e in events)  # Pretty unlikely
            if not has_star_event:
                add_event_to_space_internal(board, space, create_event_instance(StarEvent),
                                            False, get_events_in_library())

    def _create_gate_events(self, board, board_info, chains):
        """Adds the gate events we abstract in the UI."""
        from ..boards import add_event_to_space_internal, get_connections
        from ..events.events import create_event_instance
        from ..events.event_library import get_events_in_library
        from ..events.builtin.events_common import Gate, GateClose

        def _get_pointing_space_index(pointed_at_index):
            for start_idx in js_keys(board.get("links") or {}):
                ends = get_connections(int(start_idx), board)
                for end in ends:
                    if end == pointed_at_index:
                        return int(start_idx)
            return -1

        def _get_next_space_index(space_index):
            ends = get_connections(space_index, board)
            return at(ends, 0) if ends is not None else None

        def _get_chain_with_space(space_index):
            for c in range(len(chains)):
                if space_index in chains[c]:
                    return c
            return None

        def _index_in_chain(chain_index, space_index):
            chain = at(chains, chain_index)
            if chain is None:
                raise TypeError("Cannot read properties of undefined (reading 'indexOf')")
            return chain.index(space_index) if space_index in chain else -1

        gate_index = 0
        for i in range(len(board["spaces"])):
            space = board["spaces"][i]
            if not space or space.get("subtype") != SpaceSubtype.GATE:
                continue

            # We actually put an event before and after the gate, not actually on it.
            entry_space_index = _get_pointing_space_index(i)
            entry_space = _space(board, entry_space_index)
            if entry_space is None:
                raise ValueError("Gate did not have entry space")

            prev_space_index = _get_pointing_space_index(entry_space_index)
            prev_space = _space(board, prev_space_index)
            if prev_space is None:
                raise ValueError("Gate did not have previous space")

            prev_chain_index = _get_chain_with_space(prev_space_index)
            prev_chain_space_index = _index_in_chain(prev_chain_index, prev_space_index)

            exit_space_index = _get_next_space_index(i)
            exit_space = _space(board, exit_space_index)
            if exit_space is None:
                raise ValueError("Gate did not have exit space")

            next_space_index = _get_next_space_index(exit_space_index)
            next_space = _space(board, next_space_index)
            if next_space is None:
                raise ValueError("Gate did not have next space")

            next_chain_index = _get_chain_with_space(next_space_index)
            next_chain_space_index = _index_in_chain(next_chain_index, next_space_index)

            # Redundant to write event twice, except we need it attached to both spaces.
            gate_event = create_event_instance(Gate, {
                "parameterValues": {
                    "gatePrevChain": [prev_chain_index, prev_chain_space_index],
                    "gateEntryIndex": entry_space_index,
                    "gateSpaceIndex": i,
                    "gateExitIndex": exit_space_index,
                    "gateNextChain": [next_chain_index, next_chain_space_index],
                },
            })
            add_event_to_space_internal(board, entry_space, gate_event, False, get_events_in_library())
            add_event_to_space_internal(board, exit_space, gate_event, False, get_events_in_library())

            # Need an additional event to close the gate.
            add_event_to_space_internal(
                board,
                space,
                create_event_instance(GateClose, {
                    "parameterValues": {
                        "gateIndex": gate_index,
                    },
                }),
                False,
                get_events_in_library(),
            )

            # There is also a listing of the entry/exit spaces, probably used by the gate animation.
            # if (boardInfo.gateNeighborsOffset) {
            #   const sceneView = scenes.getDataView(boardInfo.sceneIndex!);
            #   for (let gateAddrIndex = 0; gateAddrIndex < boardInfo.gateNeighborsOffset.length; gateAddrIndex++) {
            #     let gateAddr = boardInfo.gateNeighborsOffset[gateAddrIndex];
            #     gateAddr += (gateIndex * 4);

            #     sceneView.setUint16(gateAddr, entrySpaceIndex);
            #     sceneView.setUint16(gateAddr + 2, exitSpaceIndex);
            #   }
            # }

            gate_index += 1

    def _write_events(self, board, board_info, board_index, chains, event_syms, audio_indices):
        """Write out all of the events ASM."""
        if board_info.get("mainfs_event_file"):
            self._write_events_new2(board, board_info, board_index, chains, event_syms, audio_indices)

    def _write_events_new2(self, board, board_info, board_index, chains, event_syms, audio_indices):
        if not board_info.get("mainfs_event_file"):
            raise ValueError("No MainFS file specified to place board ASM for board %d." % board_index)

        from ..mips import assemble

        asm = self._create_events_asm(board, board_info, board_index, chains, event_syms, audio_indices)

        log(asm)

        symbol_map = {}
        try:
            buffer = assemble(asm, symbol_output_map=symbol_map)
        except Exception as e:
            full_error = "Error during board assembly: %s\nContext: %s" % (e, asm)
            raise RuntimeError(full_error) from e

        log("Overlay symbols: ", symbol_map)

        buffer = bytearray(buffer)
        buffer_view = DataView(buffer)

        if len(buffer) > self.EVENT_MEM_SIZE:
            raise ValueError("Event code exceeded available memory space (%d/%d)"
                             % (len(buffer), self.EVENT_MEM_SIZE))

        # We can write the size of the event buffer to the header now, for the hook to use.
        buffer_view.set_uint32(8, len(buffer))

        # We write list blob of ASM/structures into the MainFS, in a location
        # that is not used by the game.
        main_fs_dir, main_fs_file = board_info["mainfs_event_file"]
        mainfs = _rom().get_main_fs()
        mainfs.write(main_fs_dir, main_fs_file, buffer)

        # saveAs(new Blob([buffer]), "eventBuffer");

    def _create_events_asm(self, board, board_info, board_index, chains, event_syms, audio_indices):
        """Build the assembly of the board's events (the first half of _writeEventsNew2)."""
        from ..events.events import get_event, write as write_event
        from ..events.event_library import get_events_in_library
        from ..events.prep_asm import (
            make_game_symbol_labels, make_generic_symbols_for_addresses, prep_single_event_asm)
        from ..events.additionalbg import get_board_additional_bg_hvq_indices, make_bg_symbol_labels
        from ..events.getaudiochoice import make_audio_symbol_labels

        game = _romhandler().get_rom_game()
        event_table = SpaceEventTable()
        event_lists = []
        event_asms = []
        event_temp = {}
        statics_written = {}
        for i in range(len(board["spaces"])):
            space = board["spaces"][i]
            if not space.get("events"):
                continue
            event_table.add(i, 0)

            event_list = SpaceEventList(i)
            for e in range(len(space["events"])):
                event_instance = space["events"][e]
                activation_type = get_event_activation_type_from_editor_type(
                    event_instance["activationType"])
                event_list.add(
                    activation_type,
                    event_instance.get("executionType") or event_instance.get("mystery"),
                    0,
                )

                temp = event_temp.get(event_instance["id"])
                if temp is None:
                    temp = {}
                info = {
                    "board_index": board_index,
                    "board": board,
                    "board_info": board_info,
                    "audio_indices": audio_indices,
                    "cur_space_index": i,
                    "cur_space": space,
                    "chains": chains,
                    "game": game,
                    "game_version": self.game_version,
                }

                event_asm = write_event(bytearray(0), event_instance, info, temp)
                event_temp[event_instance["id"]] = temp

                if not isinstance(event_asm, str):
                    raise ValueError("Event %s did not return a string to assemble" % event_instance["id"])

                event = get_event(event_instance["id"], board, get_events_in_library())
                assert_(bool(event))
                event_asms.append(prep_single_event_asm(
                    event_asm,
                    event,
                    event_instance,
                    info,
                    not statics_written.get(event_instance["id"]),
                    e,
                ))

                statics_written[event_instance["id"]] = True
            event_lists.append(event_list)

        # Write any board events
        type5 = SpaceEventList(-5)
        type4 = SpaceEventList(-4)
        type3 = SpaceEventList(-3)
        type2 = SpaceEventList(-2)
        board_event_type_infos = [
            {"index": -5, "list": type5, "type": EditorEventActivationType.BEFORE_DICE_ROLL},
            {"index": -4, "list": type4, "type": EditorEventActivationType.BEFORE_PLAYER_TURN},
            {"index": -3, "list": type3, "type": EditorEventActivationType.AFTER_TURN},
            {"index": -2, "list": type2, "type": EditorEventActivationType.BEFORE_TURN},
        ]
        for type_info in board_event_type_infos:
            index, lst, type_ = type_info["index"], type_info["list"], type_info["type"]
            events = _get_events_with_activation_type(board.get("boardevents") or [], type_)
            activation_type = get_event_activation_type_from_editor_type(type_)  # Always SPECIAL
            for e in range(len(events)):
                event_instance = events[e]
                lst.add(activation_type, event_instance.get("executionType"), 0)

                temp = event_temp.get(event_instance["id"])
                if temp is None:
                    temp = {}
                info = {
                    "board_index": board_index,
                    "board": board,
                    "board_info": board_info,
                    "audio_indices": audio_indices,
                    "cur_space_index": index,
                    "cur_space": None,
                    "chains": chains,
                    "game": game,
                    "game_version": self.game_version,
                }

                event_asm = write_event(bytearray(0), event_instance, info, temp)
                event_temp[event_instance["id"]] = temp

                if not isinstance(event_asm, str):
                    raise ValueError("Event %s did not return a string to assemble" % event_instance["id"])

                event = get_event(event_instance["id"], board, get_events_in_library())
                assert_(bool(event))
                event_asms.append(prep_single_event_asm(
                    event_asm,
                    event,
                    event_instance,
                    info,
                    not statics_written.get(event_instance["id"]),
                    e,
                ))

                statics_written[event_instance["id"]] = True

            self.on_add_default_board_events(type_, lst)

            if lst.count() > 0:
                event_table.add(index, 0)
                event_lists.append(lst)

        event_asm_combined_string = "\n".join(event_asms)
        generic_addr_symbols = make_generic_symbols_for_addresses(event_asm_combined_string)

        asm = (
            "\n"
            ".org " + hexstr(self.EVENT_RAM_LOC) + "\n"
            ".ascii \"PP64\"\n"
            ".word " + hexstr(self.EVENT_RAM_LOC) + "\n"
            ".word 0 // Populated with buffer size later\n"
            ".align 16\n"
            "\n"
            + event_syms + "\n"
            "\n"
            + "\n".join(make_game_symbol_labels(game, False)) + "\n"
            + "\n".join(make_bg_symbol_labels(
                board_info["bg_dir"], get_board_additional_bg_hvq_indices(board))) + "\n"
            + "\n".join(make_audio_symbol_labels(audio_indices)) + "\n"
            + "\n".join(generic_addr_symbols) + "\n"
            "\n"
            + event_table.get_assembly() + "\n"
            + "\n".join(event_list.get_assembly() for event_list in event_lists) + "\n"
            + event_asm_combined_string + "\n"
        )
        return asm

    def _make_symbols_for_event_assembly(self, syms, scene_info):
        result = ""
        for sym_name in js_keys(syms):
            if sym_name.startswith("__PP64_INTERNAL_VAL_"):
                result += ".definelabel %s,%s\n" % (sym_name, hexstr(syms[sym_name]))
            elif sym_name.startswith("__PP64_INTERNAL"):
                result += ".definelabel %s,%s\n" % (
                    sym_name, hexstr(scene_info["ram_start"] + syms[sym_name]))
        return result

    def on_write_event_asm_hook(self, rom_view, board_info, board_index):
        raise NotImplementedError("Adapter does not implement onWriteEventAsmHook")

    def on_add_default_board_events(self, editor_activation_type, lst):
        """Overwritten per game to add any default board events.

        All board events need to be in the same list, so we need to merge
        defaults with any custom ones.
        """
        pass

    def _extract_star_guardians(self, board, board_info):
        # AKA Toads or Baby Bowsers lol
        if not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])

        # Training writes the toad directly.
        if board_info.get("toad_space_inst"):
            toad_space = scene_view.get_uint16(board_info["toad_space_inst"] + 2)
            if _space(board, toad_space) is not None:
                board["spaces"][toad_space]["subtype"] = int(SpaceSubtype.TOAD)

        if board_info.get("star_space_count"):
            # Parse the spaces that can be considered for star placement.
            star_spaces_offset = board_info["star_space_arr_offset"]
            if isinstance(star_spaces_offset, list):
                star_spaces_offset = star_spaces_offset[0]
            for i in range(board_info["star_space_count"]):
                star_space = scene_view.get_uint16(star_spaces_offset + i * 2)
                if _space(board, star_space) is not None:
                    board["spaces"][star_space]["star"] = True

            # Parse the associated toads
            for i in range(board_info["star_space_count"]):
                toad_spaces_offset = board_info["toad_space_arr_offset"]
                if isinstance(toad_spaces_offset, list):
                    toad_spaces_offset = toad_spaces_offset[0]
                toad_space = scene_view.get_uint16(toad_spaces_offset + i * 2)
                if _space(board, toad_space) is not None:
                    board["spaces"][toad_space]["subtype"] = int(SpaceSubtype.TOAD)

    def _write_star_info(self, board, board_info):
        from ..boards import get_spaces_of_sub_type

        star_count = board_info.get("star_space_count")
        if star_count:
            scenes = _rom().get_scenes()
            scene_view = scenes.get_data_view(board_info["scene_index"])

            star_indices = []
            for i in range(len(board["spaces"])):
                if board["spaces"][i].get("star"):
                    star_indices.append(i)

            star_spaces_offsets = board_info["star_space_arr_offset"]
            if not isinstance(star_spaces_offsets, list):
                star_spaces_offsets = [star_spaces_offsets]
            for offset in star_spaces_offsets:
                for j in range(star_count):
                    star_idx = j if j < len(star_indices) else len(star_indices) - 1  # Keep writing last space to fill
                    scene_view.set_uint16(offset + j * 2, at(star_indices, star_idx))

            toad_spaces = get_spaces_of_sub_type(SpaceSubtype.TOAD, board)

            # Write the toad spaces, using distance formula for now.
            toad_spaces_offsets = board_info["toad_space_arr_offset"]
            if not isinstance(toad_spaces_offsets, list):
                toad_spaces_offsets = [toad_spaces_offsets]
            for offset in toad_spaces_offsets:
                for j in range(star_count):
                    star_idx = j if j < len(star_indices) else len(star_indices) - 1
                    star_space = _space(board, at(star_indices, star_idx))
                    best_distance = 1.7976931348623157e308  # Number.MAX_VALUE
                    # By default, no toad spaces = put toad on star space for now.
                    best_toad_idx = at(star_indices, star_idx)
                    for toad_idx in toad_spaces:
                        toad_space = board["spaces"][toad_idx]
                        if star_space is None:
                            raise TypeError("Cannot read properties of undefined (reading 'x')")
                        dist = distance(star_space["x"], star_space["y"], toad_space["x"], toad_space["y"])
                        if dist < best_distance:
                            best_distance = dist
                            best_toad_idx = toad_idx

                    scene_view.set_uint16(offset + j * 2, best_toad_idx)

    def _extract_boos(self, board, board_info):
        if not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        if board_info.get("boos_loop_fn_offset"):
            boo_fn_offset = board_info["boos_loop_fn_offset"]

            # Read the Boo count.
            boo_count = scene_view.get_uint16(boo_fn_offset + 0x2A)
            if scene_view.get_uint32(boo_fn_offset + 0x28) == 0x1A00FFFC:
                # BNEZ when a single boo is made (Wario)
                boo_count = 1
            if boo_count == 0:
                return

            boo_fn_offset = board_info["boos_readback_fn_offset"]
            boo_relative_addr = scene_view.get_int16(boo_fn_offset + 0xD2)
            boo_relative_addr = 0x00100000 + boo_relative_addr  # Going to be a subtraction.

            scene_info = scenes.get_info(board_info["scene_index"])
            boo_spaces_offset = self._addr_to_offset_base(boo_relative_addr, scene_info["ram_start"])
            for i in range(boo_count):
                boo_space = scene_view.get_uint16(boo_spaces_offset + 2 * i)
                if _space(board, boo_space) is not None:
                    board["spaces"][boo_space]["subtype"] = int(SpaceSubtype.BOO)
        elif board_info.get("boo_space_inst"):
            # Just one Boo
            boo_space = scene_view.get_uint16(board_info["boo_space_inst"] + 2)
            if _space(board, boo_space) is not None:
                board["spaces"][boo_space]["subtype"] = int(SpaceSubtype.BOO)
        elif board_info.get("boo_count"):
            boo_arr_offset = board_info["boo_arr_offset"]
            for cur_boo_space_index_offset in boo_arr_offset:
                for _ in range(board_info["boo_count"]):
                    boo_space = scene_view.get_uint16(cur_boo_space_index_offset)
                    if _space(board, boo_space) is not None:
                        board["spaces"][boo_space]["subtype"] = int(SpaceSubtype.BOO)
                    cur_boo_space_index_offset += 2

    def _write_boos(self, board, board_info):
        if not board_info.get("scene_index"):
            return

        from ..boards import get_dead_space_index, get_spaces_of_sub_type

        # Find the boo spaces
        boo_spaces = get_spaces_of_sub_type(SpaceSubtype.BOO, board)

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        if board_info.get("boos_loop_fn_offset"):
            boo_fn_offset = board_info["boos_loop_fn_offset"]

            # Read the Boo count.
            boo_count = scene_view.get_uint16(boo_fn_offset + 0x2A)
            if scene_view.get_uint32(boo_fn_offset + 0x28) == 0x1A00FFFC:
                # BNEZ when a single boo is made (Wario)
                boo_count = 1
            elif boo_spaces and boo_count > len(boo_spaces):
                # Basically lower the boo count if we only have 1 boo instead of 2.
                scene_view.set_uint16(boo_fn_offset + 0x2A, len(boo_spaces))
            if boo_count == 0:
                return

            boo_fn_offset = board_info["boos_readback_fn_offset"]
            boo_relative_addr = scene_view.get_int16(boo_fn_offset + 0xD2)
            boo_relative_addr = 0x00100000 + boo_relative_addr  # Going to be a subtraction.

            scene_info = scenes.get_info(board_info["scene_index"])
            boo_spaces_offset = self._addr_to_offset_base(boo_relative_addr, scene_info["ram_start"])

            for i in range(boo_count):
                boo_space = at(boo_spaces, i)
                if boo_space is None:
                    boo_space = get_dead_space_index(board)
                scene_view.set_uint16(boo_spaces_offset + 2 * i, boo_space)
        elif board_info.get("boo_space_inst"):
            # Just one Boo
            boo_space = at(boo_spaces, 0)
            if boo_space is None:
                boo_space = get_dead_space_index(board)
            scene_view.set_uint16(board_info["boo_space_inst"] + 2, boo_space)
        elif board_info.get("boo_count"):
            boo_arr_offset = board_info["boo_arr_offset"]
            for cur_boo_space_index_offset in boo_arr_offset:
                for i in range(board_info["boo_count"]):
                    boo_space = at(boo_spaces, i)
                    if boo_space is None:
                        boo_space = get_dead_space_index(board)
                    scene_view.set_uint16(cur_boo_space_index_offset, boo_space)
                    cur_boo_space_index_offset += 2

    def _extract_banks(self, board, board_info):
        if not board_info.get("bank_count") or not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        bank_arr_offset = board_info["bank_arr_offset"]
        for cur_bank_space_index_offset in bank_arr_offset:
            for _ in range(board_info["bank_count"]):
                bank_space = scene_view.get_uint16(cur_bank_space_index_offset)
                if _space(board, bank_space) is not None:
                    board["spaces"][bank_space]["subtype"] = int(SpaceSubtype.BANK)
                cur_bank_space_index_offset += 2
        for cur_bank_coin_space_index_offset in board_info["bank_coin_arr_offset"]:
            for _ in range(board_info["bank_count"]):
                bank_coin_space = scene_view.get_uint16(cur_bank_coin_space_index_offset)
                if _space(board, bank_coin_space) is not None:
                    board["spaces"][bank_coin_space]["subtype"] = int(SpaceSubtype.BANKCOIN)
                cur_bank_coin_space_index_offset += 2

    def _write_banks(self, board, board_info):
        if not board_info.get("bank_count") or not board_info.get("scene_index"):
            return

        from ..boards import get_dead_space_index, get_spaces_of_sub_type

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        bank_spaces = get_spaces_of_sub_type(SpaceSubtype.BANK, board)
        bank_arr_offset = board_info["bank_arr_offset"]
        for cur_bank_space_index_offset in bank_arr_offset:
            for i in range(board_info["bank_count"]):
                bank_space = at(bank_spaces, i)
                if bank_space is None:
                    bank_space = get_dead_space_index(board)
                scene_view.set_uint16(cur_bank_space_index_offset, bank_space)
                cur_bank_space_index_offset += 2

        bank_coin_spaces = get_spaces_of_sub_type(SpaceSubtype.BANKCOIN, board)
        for cur_bank_coin_space_index_offset in board_info["bank_coin_arr_offset"]:
            for i in range(board_info["bank_count"]):
                bank_coin_space = at(bank_coin_spaces, i)
                if bank_coin_space is None:
                    bank_coin_space = get_dead_space_index(board)
                scene_view.set_uint16(cur_bank_coin_space_index_offset, bank_coin_space)
                cur_bank_coin_space_index_offset += 2

    def _extract_item_shops(self, board, board_info):
        if not board_info.get("item_shop_count") or not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        for cur_item_shop_space_index_offset in board_info["item_shop_arr_offset"]:
            for _ in range(board_info["item_shop_count"]):
                item_shop_space = scene_view.get_uint16(cur_item_shop_space_index_offset)
                if _space(board, item_shop_space) is not None:
                    board["spaces"][item_shop_space]["subtype"] = int(SpaceSubtype.ITEMSHOP)
                cur_item_shop_space_index_offset += 2

    def _write_item_shops(self, board, board_info):
        if not board_info.get("item_shop_count") or not board_info.get("scene_index"):
            return

        from ..boards import get_dead_space_index, get_spaces_of_sub_type

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        item_shop_spaces = get_spaces_of_sub_type(SpaceSubtype.ITEMSHOP, board)
        for cur_item_shop_space_index_offset in board_info["item_shop_arr_offset"]:
            for i in range(board_info["item_shop_count"]):
                item_shop_space = at(item_shop_spaces, i)
                if item_shop_space is None:
                    item_shop_space = get_dead_space_index(board)
                scene_view.set_uint16(cur_item_shop_space_index_offset, item_shop_space)
                cur_item_shop_space_index_offset += 2

    def _write_gates(self, board, board_info):
        """Unused, unless MP2 goes old school."""
        if not board_info.get("gate_count") or not board_info.get("scene_index"):
            return

        from ..boards import get_dead_space_index

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        gate_spaces = []
        for i in range(len(board["spaces"])):
            if board["spaces"][i].get("subtype") == SpaceSubtype.GATE:
                gate_spaces.append(i)

        gate_arr_offset = board_info["gate_arr_offset"]
        for cur_gate_space_index_offset in gate_arr_offset:
            for i in range(board_info["gate_count"]):
                gate_space = at(gate_spaces, i)
                if gate_space is None:
                    gate_space = get_dead_space_index(board)
                scene_view.set_uint16(cur_gate_space_index_offset, gate_space)
                cur_gate_space_index_offset += 2

    def _write_background(self, bg_index, src, width, height):
        img_data = canvas.get_image_data(src, width, height)
        hvqfs = _rom().get_hvqfs()
        hvqfs.write_background(bg_index, img_data, width, height)

    def _write_additional_backgrounds(self, board):
        additional_bgs = board.get("additionalbg")
        if not additional_bgs:
            return

        width, height = board["bg"]["width"], board["bg"]["height"]
        bg_img_data = [canvas.get_image_data(src, width, height) for src in additional_bgs]

        hvqfs = _rom().get_hvqfs()
        for img_data in bg_img_data:
            # Append each one to the end of the hvq fs.
            hvqfs.write_background(
                hvqfs.get_directory_count(),
                img_data,
                width,
                height,
                board["bg"],
            )

    def on_parse_board_select_img(self, board, board_info):
        log("Adapter does not implement onParseBoardSelectImg")

    def on_write_board_select_img(self, board, board_info):
        log("Adapter does not implement onWriteBoardSelectImg")

    def on_parse_board_logo_img(self, board, board_info):
        log("Adapter does not implement onParseBoardLogoImg")

    def on_write_board_logo_img(self, board, board_info):
        log("Adapter does not implement onWriteBoardLogoImg")

    def _brand_boot_splashscreen(self):
        if not self.options.get("write_branding"):
            return

        if not self.nintendo_logo_fs_entry or not self.hudson_logo_fs_entry:
            log("Adapter cannot write branding")
            return

        from ..utils.img.rgba5551 import rgba5551from_rgba32
        from ..utils.img.img_pack import to_pack

        self._combine_splashcreen_logos()

        pp64_splash32_buffer = canvas.get_image_data(bootsplash_image, 320, 240).data
        pp64_splash16_buffer = rgba5551from_rgba32(pp64_splash32_buffer, 320, 240)

        # Then, pack the image and write it.
        img_info_arr = [
            {
                "src": pp64_splash16_buffer,
                "width": 320,
                "height": 240,
                "bpp": 16,
            },
        ]
        new_pack = to_pack(img_info_arr, 16, 8)
        # saveAs(new Blob([newPack]));
        mainfs = _rom().get_main_fs()
        mainfs.write(self.hudson_logo_fs_entry[0], self.hudson_logo_fs_entry[1], new_pack)

    def _combine_splashcreen_logos(self):
        from ..utils.img.rgba5551 import rgba5551from_rgba32
        from ..utils.img.img_pack import from_pack, to_pack, img_info_src_to_array_buffer

        mainfs = _rom().get_main_fs()
        nintendo_pack = mainfs.get(self.nintendo_logo_fs_entry[0], self.nintendo_logo_fs_entry[1])  # (NINTENDO) logo
        if nintendo_pack[0x1A] != 0x20:
            return  # We already replaced the splashscreen.

        hudson_pack = mainfs.get(self.hudson_logo_fs_entry[0], self.hudson_logo_fs_entry[1])  # Hudson logo

        nintendo_img_info = from_pack(nintendo_pack)[0]
        hudson_img_info = from_pack(hudson_pack)[0]

        nintendo_arr = img_info_src_to_array_buffer(nintendo_img_info["src"])
        hudson_arr = img_info_src_to_array_buffer(hudson_img_info["src"])

        combo_image_data = combine_splashscreen_logo_pixels(nintendo_arr, hudson_arr)

        combo16_buffer = rgba5551from_rgba32(combo_image_data, 320, 240)
        img_info_arr = [
            {
                "src": combo16_buffer,
                "width": 320,
                "height": 240,
                "bpp": 16,
            },
        ]
        new_pack = to_pack(img_info_arr, 16, 8)
        # saveAs(new Blob([newPack]));
        mainfs.write(self.nintendo_logo_fs_entry[0], self.nintendo_logo_fs_entry[1], new_pack)

    def _clear_other_board_names(self, board_index):
        log("Adapter does not implement _clearOtherBoardNames")

    def _read_packed_from_main_fs(self, dir, file):
        from ..utils.img.img_pack import from_pack, img_info_src_to_data_view

        mainfs = _rom().get_main_fs()
        img_pack_buffer = mainfs.get(dir, file)
        img_arr = from_pack(img_pack_buffer)
        if not img_arr:
            return None

        return [img_info_src_to_data_view(img_info["src"]) for img_info in img_arr]

    def _read_imgs_from_main_fs(self, dir, file):
        from ..utils.img.img_pack import from_pack

        mainfs = _rom().get_main_fs()
        img_pack_buffer = mainfs.get(dir, file)
        img_arr = from_pack(img_pack_buffer)
        if not img_arr:
            return None

        return img_arr

    def _read_img_info_from_main_fs(self, dir, file, img_arr_index=0):
        img_arr = self._read_imgs_from_main_fs(dir, file)
        return img_arr[img_arr_index or 0]

    def _read_img_from_main_fs(self, dir, file, img_arr_index=0):
        from ..utils.img.img_pack import img_info_src_to_array_buffer

        img_info = self._read_img_info_from_main_fs(dir, file, img_arr_index)
        array_buffer = img_info_src_to_array_buffer(img_info["src"])
        return canvas.rgba_to_data_url(array_buffer, img_info["width"], img_info["height"])

    def _parse_audio(self, board, board_info):
        if not board_info.get("audio_index_offset") or not board_info.get("scene_index"):
            return

        scenes = _rom().get_scenes()
        scene_view = scenes.get_data_view(board_info["scene_index"])
        board["audioIndex"] = scene_view.get_uint16(board_info["audio_index_offset"])

    def on_write_audio(self, board, board_info, board_index):
        """Called to apply the background music choice to the ROM.

        Returns:
            Effective audio indices to use.
        """
        audio_indices = []
        if board.get("audioType") == 1:  # BoardAudioType.Custom
            from ..audio.midi import create_game_midi

            audio = _rom().get_audio()
            seq_table = audio.get_sequence_table(0)
            assert_(bool(seq_table))
            for audio_entry in board["audioData"]:
                audio_indices.append(len(seq_table.midis))
                seq_table.midis.append({
                    "buffer": create_game_midi(
                        bytearray(canvas.data_url_to_bytes(audio_entry["data"])), {"loop": True}),
                    "soundbank_index": audio_entry["soundbankIndex"],
                })
        else:
            # BoardAudioType.InGame, default
            audio_indices = [board.get("audioIndex") or 0]

        return audio_indices

    def get_audio_map(self, table):
        log("Adapter does not implement getAudioMap")
        return []

    def get_sound_effect_map(self, table):
        log("Adapter does not implement getSoundEffectMap")
        return []

    def get_character_map(self):
        log("Adapter does not implement getCharacterMap")
        return {}


def _get_events_with_activation_type(events, activation_type):
    return [e for e in events if e.get("activationType") == activation_type]


def combine_splashscreen_logo_pixels(nintendo_arr, hudson_arr):
    """The RGBA32 pixels of the combined Nintendo + Hudson boot logo.

    Both logos are 320x240 RGBA32; their middle bands are stacked on black.
    """
    # comboCanvasCtx.fillStyle = "black"; fillRect(0, 0, 320, 240)
    combo = bytearray(b"\x00\x00\x00\xFF" * (320 * 240))

    start, end = 320 * 88 * 4, 320 * 154 * 4
    nintendo_band = bytes(nintendo_arr[start:end]).ljust(end - start, b"\x00")
    hudson_band = bytes(hudson_arr[start:end]).ljust(end - start, b"\x00")
    shift_up = 320 * 40 * 4
    shift_down = 320 * 50 * 4
    combo[start - shift_up:end - shift_up] = nintendo_band
    combo[start + shift_down:end + shift_down] = hudson_band

    # comboCanvasCtx.putImageData(comboImageData, 0, 0);
    # $$log(comboCanvasCtx.canvas.toDataURL());
    return combo


def _defined(values):
    """Drop None (undefined) values, as JSON.stringify would."""
    return {k: v for k, v in values.items() if v is not None}


def _json_stringify(obj):
    """JSON.stringify(obj)."""
    return json_stringify(obj)


def _string_to_array_buffer(text):
    from ..utils.string import string_to_array_buffer
    return string_to_array_buffer(text)


def _string_from_array_buffer(buffer):
    from ..utils.string import string_from_array_buffer
    return string_from_array_buffer(buffer)


def _append_difficulty(bytes_, board, star):
    """The difficulty stars of the board select strings (shared by the games)."""
    from ..fs.strings import str_to_bytes

    difficulty = board.get("difficulty")
    if is_number(difficulty) and (difficulty > 5 or difficulty < 1):
        # Hackers!
        bytes_.append(star)
        bytes_ += str_to_bytes(" ")
        bytes_.append(0x3E)  # Little x
        bytes_ += str_to_bytes(" " + js_number_str(difficulty))
    else:
        i = 0
        while is_number(difficulty) and i < difficulty:
            bytes_.append(star)
            i += 1
    return bytes_
