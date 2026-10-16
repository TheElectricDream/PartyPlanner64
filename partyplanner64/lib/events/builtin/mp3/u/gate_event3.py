"""Skeleton Key Gate, MP3 (GateEvent3.ts)."""

from .....types import (EditorEventActivationType, EventExecutionType, EventParameterType, Game,
                        SpaceSubtype)
from ....events import Event

# GateParameterNames (TypeScript interface): the parameterValues of a GATE3 event.
GATE_PARAMETER_NAMES = ("gateEntryIndex", "gateSpaceIndex", "gateExitIndex",
                        "gatePrevChain", "gateNextChain")


def _parse(data_view, info):
    # Chilly Waters 0x80109AD8 - 0x80109E84, enter 0x7B,0x79, exit 0x4C,0x3F, gates at 0x6D,0x93
    if info["board_index"] == 0:
        offset = info["offset"]
        if offset != 0x0031F648:
            return False

        # Marking the gate if we find the event on the entering space.
        if data_view.get_uint16(offset + 0x62) == info["cur_space_index"]:
            info["board"]["spaces"][data_view.get_uint16(offset + 0x106)]["subtype"] = \
                int(SpaceSubtype.GATE)
            return True
        elif data_view.get_uint16(offset + 0x6A) == info["cur_space_index"]:
            info["board"]["spaces"][data_view.get_uint16(offset + 0x10E)]["subtype"] = \
                int(SpaceSubtype.GATE)
            return True

    return False


def _write(data_view, event, info, temp):
    # const {
    #   gateEntryIndex,
    #   gateSpaceIndex,
    #   gateExitIndex,
    #   gatePrevChain,
    #   gateNextChain,
    # } = (event.parameterValues as any as GateParameterNames)!;

    # Most of the code lives in the overlay.
    return f"""
      J __PP64_INTERNAL_GATE_EVENT
      NOP
    """


Gate3 = Event(
    id="GATE3",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    parameters=[
        {"name": "gateEntryIndex", "type": EventParameterType.Number.value},
        {"name": "gateSpaceIndex", "type": EventParameterType.Number.value},
        {"name": "gateExitIndex", "type": EventParameterType.Number.value},
        {"name": "gatePrevChain", "type": EventParameterType.NumberArray.value},
        {"name": "gateNextChain", "type": EventParameterType.NumberArray.value},
    ],
    fake_event=True,
    supported_games=[Game.MP3_USA],
    parse=_parse,
    write=_write,
)
