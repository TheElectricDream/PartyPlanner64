"""The app's board functions (port of apps/partyplanner64/boards.ts).

They work on the editor store (store.py) as the TypeScript worked on the
Redux store, and clear the undo history where the TypeScript did (through
appControl's currentBoardChanged and loadBoardsFromROM).
"""

import base64
import copy
from pathlib import Path

from ..lib.types import BoardType, CostumeType, Space
from . import board_state as bs
from .store import store

THEMES_DIR = Path(__file__).resolve().parent.parent / "static" / "img" / "themes"

THEMES = [{"name": "Blank", "id": "default"}]     # newboard.tsx

_THEME_IMAGES = ("boardselect", "boardselecticon", "boardlogo", "boardlogotext",
                 "boardlogomedium", "boardlogosmall", "largescene", "conversation",
                 "splashscreen", "bg", "bg2")
_theme_cache = {}


class BoardAudioType:
    """Type of board audio (lib boards.ts)."""
    InGame = 0
    Custom = 1


def _theme(name="default"):
    """The theme's images as data URLs (Vite inlined these small PNGs)."""
    images = _theme_cache.get(name)
    if images is None:
        images = {}
        for key in _THEME_IMAGES:
            data = (THEMES_DIR / name / (key + ".png")).read_bytes()
            images[key] = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
        _theme_cache[name] = images
    return images


def _make_default_board(game_version=1, board_type=BoardType.NORMAL):
    """A new board with the game's defaults and the default theme."""
    board_type = getattr(board_type, "value", board_type)
    board = {
        "name": "Untitled",
        "description": "Use your Star Power to finish\nthis board.",
        "game": game_version,
        "type": board_type,
        "difficulty": 3,
        "spaces": [],
        "links": {},
        "events": {},
        "audioType": BoardAudioType.InGame,
    }
    if game_version == 1:
        board["bg"] = {
            "width": 960,
            "height": 720,
            "src": True,  # Replaced with theme url later.
            "fov": 17,
            "scaleFactor": 1,
            "cameraEyePosX": 0,
            "cameraEyePosY": 1355,
            "cameraEyePosZ": 1780,
            "lookatPointX": 0,
            "lookatPointY": 0,
            "lookatPointZ": 0,
        }
        board["otherbg"] = {
            "boardselect": True,  # Replaced with theme url later.
            "boardlogo": True,
            "largescene": True,
            "conversation": True,
            "splashscreen": True,
        }
        board["audioIndex"] = 0x18  # Mambo!
    elif game_version == 2:
        board["bg"] = {
            "width": 1152,
            "height": 864,
            "src": True,
            "fov": 3,
            "scaleFactor": 0.1,
            "cameraEyePosX": 0,
            "cameraEyePosY": 1570,
            "cameraEyePosZ": 1577,
            "lookatPointX": 0,
            "lookatPointY": 0,
            "lookatPointZ": 0,
        }
        board["animbg"] = []
        board["otherbg"] = {
            "boardselect": True,
            "boardselecticon": True,
            "boardlogo": True,
            "largescene": True,
        }
        board["audioIndex"] = 0x36  # Mini-Game Stadium
        board["costumeTypeIndex"] = int(CostumeType.NORMAL)
    elif game_version == 3:
        if board_type == BoardType.NORMAL:
            board["bg"] = {
                "width": 1152,
                "height": 864,
                "src": True,
                "fov": 15,
                "scaleFactor": 0.1,
                "cameraEyePosX": 0,
                "cameraEyePosY": 300,
                "cameraEyePosZ": 300,
                "lookatPointX": 0,
                "lookatPointY": 0,
                "lookatPointZ": 0,
            }
            board["audioIndex"] = 0x29  # VS Millenium Star!
        elif board_type == BoardType.DUEL:
            board["bg"] = {
                "width": 896,
                "height": 672,
                "src": True,
                "fov": 15,
                "scaleFactor": 0.1,
                "cameraEyePosX": 0,
                "cameraEyePosY": 210,
                "cameraEyePosZ": 210,
                "lookatPointX": 0,
                "lookatPointY": 0,
                "lookatPointZ": 0,
            }
            board["audioIndex"] = 0  # TODO

        board["otherbg"] = {
            "boardselect": True,
            "boardlogo": True,
            "boardlogotext": True,
            "boardlogomedium": True,
            "boardlogosmall": True,
            "largescene": True,
        }

    if board_type == BoardType.DUEL:
        board["spaces"].append({"x": 200, "y": 200, "type": int(Space.DUEL_START_BLUE)})
        board["spaces"].append({
            "x": board["bg"]["width"] - 200,
            "y": board["bg"]["height"] - 200,
            "type": int(Space.DUEL_START_RED),
        })
    else:
        board["spaces"].append({
            "x": board["bg"]["width"] - 200,
            "y": board["bg"]["height"] - 200,
            "type": int(Space.START),
        })
    apply_theme(board)
    return board


def apply_theme(board, name="default"):
    """Replaces the board's placeholder images with the theme's."""
    theme_images = _theme(name)
    otherbg = board["otherbg"]
    for key in ("boardselect", "boardselecticon", "boardlogo", "boardlogotext",
                "boardlogomedium", "boardlogosmall", "largescene", "conversation",
                "splashscreen"):
        if otherbg.get(key):
            otherbg[key] = theme_images[key]
    if board["game"] == 1:
        board["bg"]["src"] = theme_images["bg"]
    elif board["game"] in (2, 3):
        board["bg"]["src"] = theme_images["bg2"]


def _fix_potentially_old_board(board):
    from ..lib.boards import fix_potentially_old_board
    return fix_potentially_old_board(board)


def add_board(board=None, rom=False, game=None, type=None):
    """Adds a board to the board collection.

    Args:
        board: The board to add. If not passed, a default board is generated.
        rom: The board is from the ROM.
        type: Board type to use.
        game: Game version for the board.

    Returns:
        The index of the inserted board.
    """
    if not board:
        board = _make_default_board(game or 1, type or BoardType.NORMAL)

    if rom:
        board["_rom"] = True

    _fix_potentially_old_board(board)

    with store.lock:
        store.dispatch("addBoardAction", {"board": board, "rom": rom})
        collection = store.state.rom_boards if rom else store.state.boards
        return len(collection) - 1


def get_current_board():
    return bs.select_current_board(store.state)


def index_of_board(board):
    for i, b in enumerate(store.state.boards):
        if b is board:
            return i
    return -1


def current_board_changed():
    """appControl.currentBoardChanged: the undo history starts again."""
    store.clear_history()


def set_current_board(index, is_rom=False):
    with store.lock:
        store.dispatch("setCurrentBoardAction", {"index": index, "rom": bool(is_rom)})
        current_board_changed()


def board_is_rom(board):
    return bool(board.get("_rom"))


def add_event_to_board(event):
    """Adds an event to be executed during specific moments."""
    store.dispatch("addEventToBoardAction", {"event": event})


def remove_event_from_board(event_index):
    """Removes an event from `boardevents`."""
    store.dispatch("removeEventFromBoardAction", {"eventIndex": event_index})


def add_event_to_space(event, to_start=False):
    store.dispatch("addEventToSpaceAction", {"event": event, "toStart": to_start})


def add_event_to_spaces(event, space_indices):
    store.dispatch("addEventToSpacesAction", {"event": event, "spaceIndices": space_indices})


def remove_event_from_space(event_index):
    store.dispatch("removeEventFromSpaceAction", {"eventIndex": event_index})


def remove_events_from_spaces(event_indices, space_indices):
    store.dispatch("removeEventsFromSpacesAction",
                   {"eventIndices": event_indices, "spaceIndices": space_indices})


def include_event_in_board(event):
    """Includes an event in the collection of events kept within the board file."""
    store.dispatch("includeEventInBoardAction", {"event": event})


def exclude_event_from_board(event_id):
    """Removes an event from the collection of events stored in the board file."""
    store.dispatch("excludeEventFromBoardAction", {"eventId": event_id})


def set_additional_background_code(code, language):
    store.dispatch("setAdditionalBackgroundCodeAction", {"code": code, "language": language})


def set_audio_select_code(code, language):
    store.dispatch("setAudioSelectCodeAction", {"code": code, "language": language})


def get_current_board_index():
    return store.state.current_board_index


def current_board_is_rom():
    return store.state.current_board_is_rom


def get_board_count():
    return len(store.state.boards)


def get_boards():
    return store.state.boards


def get_rom_boards():
    return store.state.rom_boards


def set_bg(bg):
    store.dispatch("setBackgroundAction", {"bg": bg})


def add_anim_bg(bg):
    store.dispatch("addAnimationBackgroundAction", {"bg": bg})


def remove_anim_bg(index):
    store.dispatch("removeAnimationBackgroundAction", {"index": index})


def add_additional_bg(bg):
    store.dispatch("addAdditionalBackgroundAction", {"bg": bg})


def remove_additional_bg(index):
    store.dispatch("removeAdditionalBackgroundAction", {"index": index})


def delete_board(board_index):
    with store.lock:
        store.dispatch("deleteBoardAction", {"boardIndex": board_index})
        current_board_changed()


def copy_current_board(make_current=False):
    store.dispatch("copyCurrentBoardAction", {"makeCurrent": make_current})


def copy_board(index, rom=False, make_current=False):
    """Copies any board, not only the current one: "Copy of <name>" after it.

    The current board is copied as copyCurrentBoard did. For another board the
    current board stays current (unless make_current). Returns the copy's index.
    """
    rom = bool(rom)
    with store.lock:
        state = store.state
        current = (state.current_board_index, state.current_board_is_rom)
        collection = state.rom_boards if rom else state.boards
        if not isinstance(index, int) or isinstance(index, bool) \
                or not 0 <= index < len(collection):
            raise IndexError("There is no board %s." % (index,))
        insertion_index = len(state.boards) if rom else index + 1
        if (index, rom) == current:
            copy_current_board(make_current)
            return insertion_index
        actions = [("setCurrentBoardAction", {"index": index, "rom": rom}),
                   ("copyCurrentBoardAction", {"makeCurrent": make_current})]
        if not make_current:
            cur_index, cur_rom = current
            if not cur_rom and cur_index >= insertion_index:
                cur_index += 1
            actions.append(("setCurrentBoardAction", {"index": cur_index, "rom": cur_rom}))
        store.dispatch_many(actions)
        if make_current:
            current_board_changed()
        return insertion_index


def set_board_name(name):
    store.dispatch("setBoardNameAction", {"name": name})


def set_board_description(description):
    store.dispatch("setBoardDescriptionAction", {"description": description})


def set_board_difficulty(difficulty):
    store.dispatch("setBoardDifficultyAction", {"difficulty": difficulty})


def set_board_costume_type_index(costume_type):
    store.dispatch("setBoardCostumeTypeIndexAction", {"costumeType": costume_type})


def set_board_other_background(name, value):
    store.dispatch("setBoardOtherBgAction", {"name": name, "value": value})


def set_hosts_star(space_indices, hosts_star):
    store.dispatch("setSpaceHostsStarAction",
                   {"spaceIndices": space_indices, "hostsStar": hosts_star})


def set_board_audio(audio_changes):
    store.dispatch("setBoardAudioAction", {"audioChanges": audio_changes})


def add_space(x, y, type, subtype=None):
    with store.lock:
        new_index = len(get_current_board()["spaces"])
        store.dispatch("addSpaceAction", {"x": x, "y": y, "type": type, "subtype": subtype})
        return new_index


def remove_space(index):
    store.dispatch("removeSpaceAction", {"index": index})


def add_connection(start_space_index, end_space_index):
    store.dispatch("addConnectionAction",
                   {"startSpaceIndex": start_space_index, "endSpaceIndex": end_space_index})


def set_space_rotation(space_index, angle_y_axis_deg):
    store.dispatch("setSpaceRotationAction",
                   {"spaceIndex": space_index, "angleYAxisDeg": angle_y_axis_deg})


def load_boards_from_rom():
    """Adds the open ROM's boards (as ROM boards); the undo history starts again."""
    from ..lib.adapter.adapters import get_rom_adapter
    adapter = get_rom_adapter({})
    if not adapter:
        return

    game_boards = adapter.load_boards()
    with store.lock:
        actions = []
        for game_board in game_boards:
            game_board["_rom"] = True
            actions.append(("addBoardAction", {"board": game_board, "rom": True}))
        if actions:
            store.dispatch_many(actions)
        store.clear_history()


def clear_boards_from_rom():
    store.dispatch("clearBoardsFromROMAction")


def strip_private_props(obj):
    """A copy of a board without its _-prefixed properties (header.tsx)."""
    if isinstance(obj, dict):
        return {k: strip_private_props(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [strip_private_props(v) for v in obj]
    return copy.deepcopy(obj)
