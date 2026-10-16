"""ChainSplit1: the "event" where the player decides between two paths (ChainSplit1.ts).

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
    from .....ai.aitrees import parse_decision_tree
    from .....boards import add_connection_internal
    from .....symbols.symbols import get_symbol
    from .....utils.mips import find_calls_in_function, get_reg_set_address

    hashes = {
        # From Mario Rainbow Castle / Luigi Engine Room:
        "METHOD_START": "597324F65BC9A4D0BCA9527477258625",  # +0x2C
        "METHOD_MID1": "E276F5BAE352AC662ADCA86793409B62",  # [0x30]+0x18
        "METHOD_MID2": "24FBEBD7FA3B256016D536690EF70AD8",  # [0x4C]+0x1C
        "METHOD_END": "F153076BBD19ECBB4967EFC92CD738DF",  # [0xE0]+0x28
    }

    offset = info["offset"]
    # Match a few sections to see if we match.
    if hash_equal([data_view.buffer, offset, 0x2C], hashes["METHOD_START"]) and \
            hash_equal([data_view.buffer, offset + 0x4C, 0x1C], hashes["METHOD_MID2"]) and \
            hash_equal([data_view.buffer, offset + 0xE0, 0x28], hashes["METHOD_END"]):
        # (METHOD_MID1 at [0x30]+0x18 is not checked.)
        # Read the chain indices.
        left_chain = data_view.get_uint16(offset + 0xDA)
        right_chain = data_view.get_uint16(offset + 0xDE)

        left_space = _at(info["chains"][left_chain], 0)  # Technically, we should check if A2 is really R0.
        right_space = _at(info["chains"][right_chain], 0)

        add_connection_internal(info["cur_space"], left_space, info["board"])
        add_connection_internal(info["cur_space"], right_space, info["board"])

        # Locate the AI decision tree.
        ai_symbol = get_symbol(info["game"], "RunDecisionTree")
        tree_calls = find_calls_in_function(data_view, offset, ai_symbol)
        if len(tree_calls):
            call_offset = tree_calls[0]
            tree_data_upper = data_view.get_uint16(call_offset - 6)
            tree_data_lower = data_view.get_uint16(call_offset - 2)
            tree_data_addr = get_reg_set_address(tree_data_upper, tree_data_lower)
            no_prefix_addr = info["addr"] & 0x7FFFFFFF
            addr_diff = tree_data_addr - no_prefix_addr
            tree_data_offset = offset + addr_diff
            addr_base = no_prefix_addr - offset
            tree = parse_decision_tree(data_view, tree_data_offset, addr_base, info["game_version"])
            # addDecisionTree(info.board, info.curSpaceIndex, tree);

        return True

    return False


def _write(data_view, event, info, temp):
    chains = event["parameterValues"]["chains"]
    return f"""@@TPL@@"""


ChainSplit1 = Event(
    id="CHAINSPLIT1",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    parameters=[
        {"name": "left_space", "type": EventParameterType.Space.value},
        {"name": "right_space", "type": EventParameterType.Space.value},
        {"name": "chains", "type": EventParameterType.NumberArray.value},
    ],
    fake_event=True,
    supported_games=[Game.MP1_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ChainSplit1)
