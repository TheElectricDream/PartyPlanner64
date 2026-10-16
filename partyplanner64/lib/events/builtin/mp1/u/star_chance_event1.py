"""Chance Time from old star space (StarChanceEvent1.ts).

This pseudo-event handles when the player lands on a previously visited star space.
The space had turned into a Chance Time space.
"""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        # DK  0x2449CC, 0x800F970C
        "METHOD": "7E32BF9C855085A03CF3A8D208A6AB94",  # +0x8C
    }

    if hash_equal([data_view.buffer, info["offset"], 0x8C], hashes["METHOD"]):
        return True

    return False


def _write(data_view, event, info, temp):
    return f"""@@TPL@@"""


StarChanceEvent = Event(
    id="STARCHANCE",
    name="Chance Time from old star space",
    activation_type=EditorEventActivationType.LANDON,
    execution_type=EventExecutionType.DIRECT,
    fake_event=True,
    supported_games=[Game.MP1_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(StarChanceEvent)
