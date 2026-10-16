"""Pass start (PassStartEvent1.ts)."""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        # DK hash:
        "METHOD_START": "D87057256E3E3CA9A6878AA03EF4C486",  # +0x16
        "METHOD_END": "9AB28DCC38CFBE9AE8FEA4515E86D7B2",  # [0x1C]+0x18
    }

    offset = info["offset"]
    if hash_equal([data_view.buffer, offset, 0x16], hashes["METHOD_START"]) and \
            hash_equal([data_view.buffer, offset + 0x1C, 0x18], hashes["METHOD_END"]):
        return True

    return False


def _write(data_view, event, info, temp):
    return f"""@@TPL@@"""


PassStart = Event(
    id="PASSSTART",
    name="Pass start",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    supported_games=[Game.MP1_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(PassStart)
