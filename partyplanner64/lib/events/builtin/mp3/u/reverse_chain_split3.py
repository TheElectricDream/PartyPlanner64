"""ReverseChainSplit (ReverseChainSplit3.ts).

When going in reverse, there can be splits where there otherwise was only
chain merges going forward. The game basically wraps a chain split with a
small function that checks if the player is going in reverse.
"""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        "REVERSE_FILTER": "0909C95D982B8A9B1F096AC54FFFB816",
    }

    if not hash_equal([data_view.buffer, info["offset"], 0x30], hashes["REVERSE_FILTER"]):
        return False

    return True


def _write(data_view, event, info, temp):
    # It's all in ChainSplit3.
    raise ValueError(f"{ReverseChainSplit.id} not implemented")


ReverseChainSplit = Event(
    id="REVERSECHAINSPLIT",
    name="",
    fake_event=True,
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,  # Notable difference
    supported_games=[Game.MP3_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ReverseChainSplit)
