"""ChainSplit3: the "event" where the player decides between paths (ChainSplit3.ts).

This won't be an actual event when exposed to the user.
"""

from .....types import EditorEventActivationType, EventExecutionType, EventParameterType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ....jsfmt import js_join, js_or, js_str
from ...hash_util import hash_equal


def _at(arr, i):
    if arr is not None and 0 <= i < len(arr):
        return arr[i]
    return None


def _parse(data_view, info):
    from .....boards import add_connection_internal

    hashes = {
        # From Chilly Waters 0x80108D28 / 0x31E898:
        "METHOD_START": "16092DD153432852C141C78807ECCBF0",  # +0x08
        "METHOD_END": "6FF6DF70CDC85862F8F129303009A544",  # [0x24]+0x14
    }

    offset = info["offset"]
    # Match a few sections to see if we match.
    if hash_equal([data_view.buffer, offset, 0x08], hashes["METHOD_START"]) and \
            hash_equal([data_view.buffer, offset + 0x24, 0x14], hashes["METHOD_END"]):
        # Read the RAM offset of the space index arguments.
        upper_addr = data_view.get_uint16(offset + 0x0A) << 16
        lower_addr = data_view.get_uint16(offset + 0x0E)
        spaces_addr = (upper_addr | lower_addr) & 0x7FFFFFFF
        if spaces_addr & 0x00008000:
            spaces_addr = spaces_addr - 0x00010000
        spaces_offset = offset - (info["addr"] - spaces_addr)

        destination_space = data_view.get_uint16(spaces_offset)
        while destination_space != 0xFFFF:
            add_connection_internal(info["cur_space"], destination_space, info["board"])
            spaces_offset += 2
            destination_space = data_view.get_uint16(spaces_offset)

        return True

    return False


def _write(data_view, event, info, temp):
    pv = event["parameterValues"]
    space_index_args = pv["spaceIndexArgs"]
    chain_args = pv["chainArgs"]
    alt_chain = pv.get("altChain") or []
    return f"""
        addiu SP, SP, -0x18
        sw    RA, 0x14(SP)
        sw    S0, 0x10(SP)

    .if reverse
        jal   GetPlayerStruct
        li    A0, -1
        lbu   V0, 0x17(V0)
        andi  V0, V0, 0x80
        beq   V0, R0, exit_chain_split
        NOP
        lui   V0, hi(cur_player_spaces_remaining)
        lw    V0, lo(cur_player_spaces_remaining)(V0)
        beq   V0, R0, exit_chain_split
        NOP
        j   do_chain_split
        NOP
    .endif

    .if hasgate
      jal   GetPlayerStruct
      li    A0, -1
      move  S0, V0
      lbu   A0, 0x15(S0)
      lbu   A1, 0x16(S0)
      jal   GetAbsSpaceIndexFromChainSpaceIndex
      NOP
      sll   V0, V0, 0x10
      sra   V0, V0, 0x10
      ; Check for the previous space being the gate chain's first space.
      li    V1, {js_str(js_or(pv.get("prevSpace"), 0))}
      bne   V0, V1, do_chain_split
      NOP
      lbu   V0, 0x17(S0)
      andi  V0, V0, 0x80
      bnez  V0, do_chain_split
      ; Send player to other chain if coming from gate.
      li    A1, {js_str(js_or(_at(alt_chain, 0), 0))} ; Chain index
      li    A0, -1
      jal   SetNextChainAndSpace
      li   A2, {js_str(js_or(_at(alt_chain, 1), 0))} ; Index in chain
      lbu   V0, 0x17(S0)
      andi  V0, V0, 0xFE
      j     exit_chain_split
      sb    V0, 0x17(S0)
    .endif

    do_chain_split:
      lui   A0, hi(space_index_args)
      addiu A0, A0, lo(space_index_args)
      lui   A1, hi(chain_args)
      addiu A1, A1, lo(chain_args)
      lui   A2, hi(ai_logic)
      jal   chain_split_3_helper
       addiu A2, A2, lo(ai_logic)
    .if reverse
    exit_chain_split:
    .else
    exit_chain_split:
      jal   EndProcess
       move  A0, R0
    .endif

      lw    RA, 0x14(SP)
      lw    S0, 0x10(SP)
      jr    RA
       addiu SP, SP, 0x18

    space_index_args:
      .halfword {js_join(space_index_args, ", ")}

    chain_args:
      .halfword {js_join(chain_args, ", ")}

    ; Choose randomly
    ai_logic:
      .word ai_random_choice, ai_random_choice, ai_random_choice
    ai_random_choice:
      .word 0x00000000, 0x00000000, 0x064C9932

  .beginstatic
    chain_split_3_helper:
      addiu SP, SP, -0x38
      sw    RA, 0x30(SP)
      sw    S5, 0x2c(SP)
      sw    S4, 0x28(SP)
      sw    S3, 0x24(SP)
      sw    S2, 0x20(SP)
      sw    S1, 0x1c(SP)
      sw    S0, 0x18(SP)
      move  S2, A0
      move  S3, A1
      move  S5, A2
      li    A0, -1
      li    A1, -1
      jal   0x800F2304
       li    A2, 2
      jal   SleepVProcess
       move  S1, R0
      jal   chainsplit_setup_arrows
       NOP
      lui   A0, hi(current_player_index)
      jal   GetPlayerStruct
       lb    A0, lo(current_player_index)(A0)
      move  S4, V0
      lbu   A0, 0x15(S4)
      lbu   A1, 0x16(S4)
      jal   GetAbsSpaceIndexFromChainSpaceIndex
       NOP
      sll   V0, V0, 0x10
      sra   A1, V0, 0x10
      li    A2, 2
      move  V1, R0
    L80116514:
      sll   V0, S1, 1
      addu  V0, V0, S1
      sll   V0, V0, 1
      addu  A0, V0, S2
      sll   V0, V1, 1
    L80116528:
      addu  V0, V0, A0
      lh    V0, 0(V0)
      beq   V0, A1, L80116548
       NOP
      addiu V1, V1, 1
      slti  V0, V1, 2
      bnez  V0, L80116528
       sll   V0, V1, 1
    L80116548:
      beq   V1, A2, L80116564
       sll   V0, S1, 1
      addiu S1, S1, 1
      slti  V0, S1, 3
      bnez  V0, L80116514
       move  V1, R0
      sll   V0, S1, 1
    L80116564:
      addu  V0, V0, S1
      sll   A1, V0, 1
      sll   V0, V0, 2
      addu  S3, S3, V0
      lui   S0, hi(current_player_index)
      addiu S0, S0, lo(current_player_index)
      lb    A0, 0(S0)
      jal   0x800D76A0
       addu  A1, S2, A1
      move  S2, V0
      move  A0, S2
      lb    A1, 0(S0)
      jal   0x800D742C
       move  A2, R0
      jal   PlayerIsCPU
       li    A0, -1
      beq  V0, R0, L801165EC
       sll   V0, S1, 2
      addu  V0, V0, S5
      lw    A0, 0(V0)
      jal   0x800DA190
        move  S0, R0
      sll   V0, V0, 0x10
      sra   S1, V0, 0x10
      blez  S1, L801165E4
       move  A0, S2
    L801165CC:
      jal   0x800D7250
       li    A1, -2
      addiu S0, S0, 1
      slt   V0, S0, S1
      bnez  V0, L801165CC
        move  A0, S2
    L801165E4:
      jal   0x800D7250
        li    A1, -4
    L801165EC:
      jal   0x800D7518
       move  A0, S2
      move  S0, V0
      jal   0x800D6CA0
       move  A0, S2
      jal   chainsplit_hide_arrows
       NOP
      bnezl S0, L80116610
       addiu S3, S3, 6
    L80116610:
      lh    A1, 0(S3)
      lh    A2, 2(S3)
      jal   SetNextChainAndSpace
       li    A0, -1
      lh    A1, 4(S3)
      beq  A1, R0, L80116640
       NOP
      li    V0, 1
      beq   A1, V0, L8011664C
       NOP
      j     L80116658
       NOP
    L80116640:
      lbu   V0, 0x17(S4)
      j     L80116654
       andi  V0, V0, 0xfe
    L8011664C:
      lbu   V0, 0x17(S4)
      ori   V0, V0, 1
    L80116654:
      sb    V0, 0x17(S4)
    L80116658:
      lw    RA, 0x30(SP)
      lw    S5, 0x2c(SP)
      lw    S4, 0x28(SP)
      lw    S3, 0x24(SP)
      lw    S2, 0x20(SP)
      lw    S1, 0x1c(SP)
      lw    S0, 0x18(SP)
      jr    RA
       addiu SP, SP, 0x38

    .definelabel CORE_800CDD58,0x800CDD58
    .definelabel CORE_800D51F8,0x800D51F8

    chainsplit_setup_arrows:
      addiu SP, SP, -0x18
      sw    RA, 0x10(SP)
    L8010704C:
      jal   0x800E9AE0
       NOP
      beq  V0, R0, L8010706C
       NOP
      jal   SleepVProcess
       NOP
      j     L8010704C
       NOP
    L8010706C:
      jal   SleepVProcess
       NOP
      move  A0, R0
      li    A1, 146
      jal   0x800E210C
       li    A2, 1
      lui   AT, hi(chainsplit_arrow_memval1)
      sw    V0, lo(chainsplit_arrow_memval1)(AT)
      li    A0, 1
      li    A1, 160
      jal   0x800E210C
       li    A2, 1
      lui   AT, hi(chainsplit_arrow_memval2)
      sw    V0, lo(chainsplit_arrow_memval2)(AT)
      li    A0, 13
      li    A1, 174
      jal   0x800E210C
       li    A2, 1
      lui   AT, hi(chainsplit_arrow_memval3)
      sw    V0, lo(chainsplit_arrow_memval3)(AT)
      li    A0, 3
      li    A1, 188
      jal   0x800E210C
       li    A2, 1
      lui   AT, hi(chainsplit_arrow_memval4)
      sw    V0, lo(chainsplit_arrow_memval4)(AT)
      li    A0, 11
      li    A1, 202
      jal   0x800E210C
       li    A2, 1
      lui   AT, hi(chainsplit_arrow_memval5)
      sw    V0, lo(chainsplit_arrow_memval5)(AT)
      jal   SleepProcess
       li    A0, 3
      li    V0, 1
      lui   AT, hi(CORE_800CDD58)
      sh    V0, lo(CORE_800CDD58)(AT)
      lui   AT, hi(CORE_800D51F8)
      sh    V0, lo(CORE_800D51F8)(AT)
      lw    RA, 0x10(SP)
      jr    RA
       addiu SP, SP, 0x18

    chainsplit_hide_arrows:
      addiu SP, SP, -0x18
      sw    RA, 0x10(SP)
      lui   AT, hi(CORE_800CDD58)
      sh    R0, lo(CORE_800CDD58)(AT)
      lui   AT, hi(CORE_800D51F8)
      sh    R0, lo(CORE_800D51F8)(AT)
      lui   A0, hi(chainsplit_arrow_memval1)
      jal   0x800E21F4
       lw    A0, lo(chainsplit_arrow_memval1)(A0)
      lui   A0, hi(chainsplit_arrow_memval2)
      jal   0x800E21F4
       lw    A0, lo(chainsplit_arrow_memval2)(A0)
      lui   A0, hi(chainsplit_arrow_memval3)
      jal   0x800E21F4
       lw    A0, lo(chainsplit_arrow_memval3)(A0)
      lui   A0, hi(chainsplit_arrow_memval4)
      jal   0x800E21F4
       lw    A0, lo(chainsplit_arrow_memval4)(A0)
      lui   A0, hi(chainsplit_arrow_memval5)
      jal   0x800E21F4
       lw    A0, lo(chainsplit_arrow_memval5)(A0)
      lw    RA, 0x10(SP)
      jr    RA
       addiu SP, SP, 0x18

      .align 4
      chainsplit_arrow_memval1:
        .word 0
      chainsplit_arrow_memval2:
        .word 0
      chainsplit_arrow_memval3:
        .word 0
      chainsplit_arrow_memval4:
        .word 0
      chainsplit_arrow_memval5:
        .word 0
  .endstatic
    """


ChainSplit3 = Event(
    id="CHAINSPLIT3",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    parameters=[
        {"name": "spaceIndexArgs", "type": EventParameterType.NumberArray.value},
        {"name": "chainArgs", "type": EventParameterType.NumberArray.value},
        # For ReverseChainSplit
        {"name": "reverse", "type": EventParameterType.Boolean.value},
        # For GateChainSplit
        {"name": "hasgate", "type": EventParameterType.Boolean.value},
        {"name": "prevSpace", "type": EventParameterType.Number.value},
        {"name": "altChain", "type": EventParameterType.NumberArray.value},
    ],
    fake_event=True,
    supported_games=[Game.MP3_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ChainSplit3)
