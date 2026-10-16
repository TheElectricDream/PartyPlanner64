"""Buy star, MP1 (StarEvent1.ts). Not registered in the library itself."""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        # DK, Wario, Luigi
        "METHOD_START": "14A3FD0F13B034F8C90659FF589A17DB",  # +0x14
        # Skip a method call (two possibilities [DK, Wario, Luigi], [Bowser, Eternal])
        "METHOD_MID": "B48ABB1B1FDBF7B5EF9765FD61C3940E",  # [0x18]+0x10
        # Skip a relative branch
        # Skip A0, R0, Event# (44, 5E)
        "METHOD_END": "5FEE3364FDCA8B0E9247BFB37A391358",  # [0x30]+0x34
    }

    offset = info["offset"]
    if hash_equal([data_view.buffer, offset, 0x14], hashes["METHOD_START"]) and \
            hash_equal([data_view.buffer, offset + 0x18, 0x10], hashes["METHOD_MID"]) and \
            hash_equal([data_view.buffer, offset + 0x30, 0x34], hashes["METHOD_END"]):
        return True

    return False


def _write(data_view, event, info, temp):
    return f"""@@TPL@@"""


StarEvent1 = Event(
    id="STAR1",
    name="Buy star",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    fake_event=True,
    supported_games=[Game.MP1_USA],
    parse=_parse,
    write=_write,
)
