"""Visit Bowser (BowserEvent1.ts)."""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ....jsfmt import js_str
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        "PLAYER_DIRECTION_CHANGE": "DAD5E635FE90ED982D02B3F1D5C0CE21",  # +0x14
        "METHOD_END": "8A835D982BE35F1804E9ABD65C5699F4",  # [0x1C]+0x1C
    }

    offset = info["offset"]
    if hash_equal([data_view.buffer, offset, 0x14], hashes["PLAYER_DIRECTION_CHANGE"]) and \
            hash_equal([data_view.buffer, offset + 0x1C, 0x1C], hashes["METHOD_END"]):
        # Check whether this points to any of the Bowser scenes.
        scene_num = data_view.get_uint16(offset + 0x1A)
        is_bowser_scene = scene_num in [0x48, 0x49, 0x4F, 0x53, 0x54, 0x5B, 0x5D]
        return is_bowser_scene

    return False


def _write(data_view, event, info, temp):
    # Any of these "work" but only the corresponding one has the right background.
    scenes = [0x48, 0x49, 0x4F, 0x53, 0x54, 0x5B, 0x5D]
    board_index = info.get("board_index")
    bowser_scene_num = scenes[board_index] if isinstance(board_index, int) and 0 <= board_index < len(scenes) else None

    return f"""@@TPL@@"""


Bowser = Event(
    id="BOWSER",
    name="Visit Bowser",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    supported_games=[Game.MP1_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(Bowser)
