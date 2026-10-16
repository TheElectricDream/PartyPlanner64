"""Skeleton Key Gate close, MP3 (GateCloseEvent3.ts)."""

from .....types import EditorEventActivationType, EventExecutionType, EventParameterType, Game
from ....events import Event
from ....jsfmt import js_str


def _parse(data_view, info):
    from .....utils.mips import get_function_length

    fn_len = get_function_length(data_view, info["offset"])
    if fn_len != 0x1C:
        return False

    gate_close_jals = [
        0x0C0422BA,  # JAL 0x80108AE8
    ]

    # Chilly Waters 0x8010F050 - 0x8010F06C
    board_index = info["board_index"]
    expected = gate_close_jals[board_index] if 0 <= board_index < len(gate_close_jals) else None
    if data_view.get_uint32(info["offset"] + 8) != expected:
        return False

    return True


def _write(data_view, event, info, temp):
    # Most of the code still lives in the overlay.
    gate_index = event["parameterValues"].get("gateIndex")
    return f"""
      addiu SP, SP, -0x18
      sw    RA, 0x10(SP)
      jal   __PP64_INTERNAL_GATE_CLOSE_EVENT
       li    A0, {js_str(gate_index)}
      lw    RA, 0x10(SP)
      jr    RA
       addiu SP, SP, 0x18
    """


GateClose3 = Event(
    id="GATECLOSE3",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    parameters=[{"name": "gateIndex", "type": EventParameterType.Number.value}],
    fake_event=True,
    supported_games=[Game.MP3_USA],
    parse=_parse,
    write=_write,
)
