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
    return f"""
      ADDIU SP SP 0xFFE0
      SW RA 0x18(SP)
      SW S1 0x14(SP)
      SW S0 0x10(SP)
      ADDU S1 R0 R0
    loop:
      JAL GetPlayerStruct
      ADDU A0 S1 R0
      JAL GetCurrentPlayerIndex
      ADDU S0 V0 R0
      SLL V0 V0 0x10
      SRA V0 V0 0x10
      XOR V0 S1 V0
      SLTU V0 R0 V0
      SB V0 0(S0)
      ADDIU S1 S1 1
      SLTI V0 S1 4
      BNE V0 R0 loop
      ADDIU A0 R0 1
      ADDU A1 R0 R0
      ADDIU A2 R0 5
      JAL 0x800587BC
      ADDIU A3 R0 1
      LW RA 0x18(SP)
      LW S1 0x14(SP)
      LW S0 0x10(SP)
      JR RA
      ADDIU SP SP 0x20
    """


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
