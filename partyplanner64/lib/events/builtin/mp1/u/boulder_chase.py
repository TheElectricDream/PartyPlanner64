"""Boulder chase (BoulderChase.ts)."""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        "METHOD_START": "6E26BAB74BC8411901472C0A40E2FC1D",  # +0x74
    }

    if hash_equal([data_view.buffer, info["offset"], 0x74], hashes["METHOD_START"]):
        # TODO: Parse the boulder path arguments.
        return True

    return False


BoulderChase = Event(
    id="BOULDERCHASE",
    name="Boulder chase",
    activation_type=EditorEventActivationType.LANDON,
    execution_type=EventExecutionType.DIRECT,
    fake_event=True,
    supported_games=[Game.MP1_USA],
    parse=_parse,
)
add_event_to_library(BoulderChase)
