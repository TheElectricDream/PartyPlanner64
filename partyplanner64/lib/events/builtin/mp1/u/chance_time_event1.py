"""Chance Time (ChanceTimeEvent1.ts)."""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        # Peach hash, 0x24699C, 0x800F79BC
        "METHOD": "18F44B4AA1F4AAAA839C100E3B0FD863",  # +0x6C
    }

    if hash_equal([data_view.buffer, info["offset"], 0x6C], hashes["METHOD"]):
        return True

    return False


def _write(data_view, event, info, temp):
    return f"""@@TPL@@"""


ChanceTime = Event(
    id="CHANCETIME",
    name="Chance Time",
    activation_type=EditorEventActivationType.LANDON,
    execution_type=EventExecutionType.DIRECT,
    supported_games=[Game.MP1_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ChanceTime)
