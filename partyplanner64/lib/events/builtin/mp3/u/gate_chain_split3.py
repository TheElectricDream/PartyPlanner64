"""GateChainSplit (GateChainSplit3.ts).

Oh look, more ChainSplits!
This is a ChainSplit where one path leads to a gate.
The difference is that it has logic to just send the player in the non-gate
direction automatically if they are coming back from the gate.
"""

from .....types import EditorEventActivationType, EventExecutionType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    # Chilly waters 0x8D space, 0x80108DD0, 0x31E940
    hashes = {
        "GATE_FILTER": "A99A70CBC4A1F9509AAB966831FC584E",
    }

    if not hash_equal([data_view.buffer, info["offset"], 0x44], hashes["GATE_FILTER"]):
        return False

    # TODO: This crashes when parsing something in Spiny, not important so nop-ing for now.
    return False

    # (Unreachable in the TypeScript too.)
    # We need to parse the chain split I suppose, can't really reuse code
    # right now but it's the same idea, only different offsets.
    # const upperAddr = dataView.getUint16(info.offset + 0x7e) << 16;
    # const lowerAddr = dataView.getUint16(info.offset + 0x82);
    # let spacesAddr = (upperAddr | lowerAddr) & 0x7fffffff;
    # if (spacesAddr & 0x00008000) spacesAddr = spacesAddr - 0x00010000;
    # let spacesOffset = info.offset - (info.addr - spacesAddr);
    # let destinationSpace = dataView.getUint16(spacesOffset);
    # while (destinationSpace !== 0xffff) {
    #   addConnectionInternal(info.curSpace, destinationSpace, info.board);
    #   spacesOffset += 2;
    #   destinationSpace = dataView.getUint16(spacesOffset);
    # }
    # return true;


def _write(data_view, event, info, temp):
    # It's all in ChainSplit3.
    raise ValueError(f"{GateChainSplit.id} not implemented")


GateChainSplit = Event(
    id="GATECHAINSPLIT",
    name="",
    fake_event=True,
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    supported_games=[Game.MP3_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(GateChainSplit)
