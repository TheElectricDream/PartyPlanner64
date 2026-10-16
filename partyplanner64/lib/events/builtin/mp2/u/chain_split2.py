"""ChainSplit2: the "event" where the player decides between two paths (ChainSplit2.ts).

This won't be an actual event when exposed to the user.
"""

from .....types import EditorEventActivationType, EventExecutionType, EventParameterType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ....jsfmt import js_str
from ...hash_util import hash_equal


def _at(arr, i):
    if arr is not None and 0 <= i < len(arr):
        return arr[i]
    return None


def _parse(data_view, info):
    from .....boards import add_connection_internal

    hashes = {
        # From Western Land 0x80107C54 / 0x29CF24:
        "METHOD_START": "0C01A009C54E209652DA667F464FB7C0",  # +0x2C
        # METHOD_MID1: "", // [0x30]+0x18 // Not sure why this was hashed in MP1
        "METHOD_MID2": "FC606B8F8BD2C8D39BB9581B0E4D8398",  # [0x4C]+0x1C
        "METHOD_END": "2F3A0045D0AC927FF23ACD73B5B62E1C",  # [0xF0]+0x28
    }

    offset = info["offset"]
    # Match a few sections to see if we match.
    if hash_equal([data_view.buffer, offset, 0x2C], hashes["METHOD_START"]) and \
            hash_equal([data_view.buffer, offset + 0x4C, 0x1C], hashes["METHOD_MID2"]) and \
            hash_equal([data_view.buffer, offset + 0xF0, 0x28], hashes["METHOD_END"]):
        # Read the chain indices.
        left_chain = data_view.get_uint16(offset + 0xEA)
        right_chain = data_view.get_uint16(offset + 0xEE)

        left_space = _at(info["chains"][left_chain], 0)  # Technically, we should check if A2 is really R0.
        right_space = _at(info["chains"][right_chain], 0)

        add_connection_internal(info["cur_space"], left_space, info["board"])
        add_connection_internal(info["cur_space"], right_space, info["board"])
        return True

    return False


def _write(data_view, event, info, temp):
    # temp: {"helper1addr", "helper2addr"}
    chains = event["parameterValues"]["chains"]
    return f"""@@TPL@@"""


ChainSplit2 = Event(
    id="CHAINSPLIT2",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    parameters=[
        {"name": "left_space", "type": EventParameterType.Space.value},
        {"name": "right_space", "type": EventParameterType.Space.value},
        {"name": "chains", "type": EventParameterType.NumberArray.value},
    ],
    fake_event=True,
    supported_games=[Game.MP2_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ChainSplit2)
