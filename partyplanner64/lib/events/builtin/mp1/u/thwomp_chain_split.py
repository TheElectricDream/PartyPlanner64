"""Thwomp chain split (ThwompChainSplit.ts).

Right now, we don't even parse this event onto the board, but we need
it to grab some helper functions for plain ChainMerge (not usually present in DK)
"""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        # One particular thwomp event from DK:
        "METHOD_START": "A45C16B1E285427C790C6FAD1EC78394",  # +0x40
    }
    if hash_equal([data_view.buffer, info["offset"], 0x40], hashes["METHOD_START"]):
        return True
    return False


ThwompChainSplit = Event(
    id="THWOMPCHAINSPLIT",
    name="Thwomp Chain Split",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,  # Unconfirmed
    fake_event=True,
    supported_games=[Game.MP1_USA],
    parse=_parse,
)
add_event_to_library(ThwompChainSplit)
