"""ChainSplit1: the "event" where the player decides between two paths (ChainSplit1.ts).

This won't be an actual event when exposed to the user.
"""

from .....types import EditorEventActivationType, EventExecutionType, EventParameterType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ....jsfmt import js_str
from ...hash_util import hash_equal


def _at(arr, i):
    if arr is not None and 0 <= i < len(arr):
        return arr[i]
    return None


def _parse(data_view, info):
    from .....ai.aitrees import parse_decision_tree
    from .....boards import add_connection_internal
    from .....symbols.symbols import get_symbol
    from .....utils.mips import find_calls_in_function, get_reg_set_address

    hashes = {
        # From Mario Rainbow Castle / Luigi Engine Room:
        "METHOD_START": "597324F65BC9A4D0BCA9527477258625",  # +0x2C
        "METHOD_MID1": "E276F5BAE352AC662ADCA86793409B62",  # [0x30]+0x18
        "METHOD_MID2": "24FBEBD7FA3B256016D536690EF70AD8",  # [0x4C]+0x1C
        "METHOD_END": "F153076BBD19ECBB4967EFC92CD738DF",  # [0xE0]+0x28
    }

    offset = info["offset"]
    # Match a few sections to see if we match.
    if hash_equal([data_view.buffer, offset, 0x2C], hashes["METHOD_START"]) and \
            hash_equal([data_view.buffer, offset + 0x4C, 0x1C], hashes["METHOD_MID2"]) and \
            hash_equal([data_view.buffer, offset + 0xE0, 0x28], hashes["METHOD_END"]):
        # (METHOD_MID1 at [0x30]+0x18 is not checked.)
        # Read the chain indices.
        left_chain = data_view.get_uint16(offset + 0xDA)
        right_chain = data_view.get_uint16(offset + 0xDE)

        left_space = _at(info["chains"][left_chain], 0)  # Technically, we should check if A2 is really R0.
        right_space = _at(info["chains"][right_chain], 0)

        add_connection_internal(info["cur_space"], left_space, info["board"])
        add_connection_internal(info["cur_space"], right_space, info["board"])

        # Locate the AI decision tree.
        ai_symbol = get_symbol(info["game"], "RunDecisionTree")
        tree_calls = find_calls_in_function(data_view, offset, ai_symbol)
        if len(tree_calls):
            call_offset = tree_calls[0]
            tree_data_upper = data_view.get_uint16(call_offset - 6)
            tree_data_lower = data_view.get_uint16(call_offset - 2)
            tree_data_addr = get_reg_set_address(tree_data_upper, tree_data_lower)
            no_prefix_addr = info["addr"] & 0x7FFFFFFF
            addr_diff = tree_data_addr - no_prefix_addr
            tree_data_offset = offset + addr_diff
            addr_base = no_prefix_addr - offset
            tree = parse_decision_tree(data_view, tree_data_offset, addr_base, info["game_version"])
            # addDecisionTree(info.board, info.curSpaceIndex, tree);

        return True

    return False


def _write(data_view, event, info, temp):
    chains = event["parameterValues"]["chains"]
    return f"""
        ADDIU SP SP 0xFFD8
        SW RA 0x24(SP)
        SW S2 0x20(SP)
        SW S1 0x1C(SP)
        SW S0 0x18(SP)

        ; Change player to standing animation?
        ADDIU A0 R0 -1
        ADDIU A1 R0 -1
        JAL 0x80052BE8
        ADDIU A2 R0 2

        JAL SleepVProcess
        NOP
        JAL chainsplit_1_setup_arrows
        NOP
        LUI S0 0x800F
        ADDIU S0 S0 0xD5DC ; 0x800ED5DC
        LH A0 0(S0)
        LUI A1 hi(indices)
        JAL 0x8003C218
        ADDIU A1 A1 lo(indices)
        ADDU S2 V0 R0
        ADDU A0 S2 R0
        LH A1 0(S0)
        JAL 0x8003C060
        ADDU A2 R0 R0
        JAL PlayerIsCPU
        ADDIU A0 R0 -1
        BEQ V0 R0 do_direction_prompt
        NOP
        LUI A0 hi(ai_logic)
        ADDIU A0 A0 lo(ai_logic)
        JAL 0x8003E9B0
        ADDU S0 R0 R0
        SLL V0 V0 0x10
        SRA S1 V0 0x10
        BLEZ S1 choice_neg
        ADDU A0 S2 R0
      choice_pos:
        JAL 0x8003BE84
        ADDIU A1 R0 0xFFFE
        ADDIU S0 S0 1
        SLT V0 S0 S1
        BNE V0 R0 choice_pos
        ADDU A0 S2 R0
      choice_neg:
        JAL 0x8003BE84
        ADDIU A1 R0 0xFFFC
      do_direction_prompt:
        JAL 0x8003C14C ; DirectionPrompt
        ADDU A0 S2 R0
        ADDU S0 V0 R0
        JAL 0x8003B908
        ADDU A0 S2 R0
        JAL chainsplit_1_hide_arrows
        NOP
        BNE S0 R0 set_chain_right
        ADDIU A0 R0 -1
        J set_chain
        ADDIU A1 R0 {js_str(_at(chains, 0))}
      set_chain_right:
        ADDIU A1 R0 {js_str(_at(chains, 1))}
      set_chain:
        JAL SetNextChainAndSpace
        ADDU A2 R0 R0 ; 0th space of the chain
        JAL 0x8005DD90
        ADDU A0 R0 R0
        LW RA 0x24(SP)
        LW S2 0x20(SP)
        LW S1 0x1C(SP)
        LW S0 0x18(SP)
        JR RA
        ADDIU SP SP 0x28

      ; Choose randomly
      ai_logic:
        .word 0x00000000, 0x00000000, 0x00003232

      indices:
        .halfword left_space
        .halfword right_space
        .halfword 0xFFFF
        .align 4

    .beginstatic
      .definelabel CORE_800EE320,0x800EE320

      chainsplit_1_setup_arrows:
        addiu SP, SP, -0x18
        sw    RA, 0x10(SP)
      @@setup_arrows_loop1:
        jal 0x8004B850 ; waiting for this to signal
        NOP
        beq V0, R0, @@setup_arrows_loop1_exit
        NOP
        jal SleepVProcess
        NOP
        j @@setup_arrows_loop1
        NOP
      @@setup_arrows_loop1_exit:
        jal SleepVProcess
        NOP
        addu  A0, R0, R0
        addiu A1, R0, 146
        jal   0x80045D84
        addiu A2, R0, 1
        lui   AT, hi(chainsplit_1_memval1)
        sw    V0, lo(chainsplit_1_memval1)(AT)
        addiu A0, R0, 1
        addiu A1, R0, 160
        jal   0x80045D84
        addiu A2, R0, 1
        lui   AT, hi(chainsplit_1_memval2)
        sw    V0, lo(chainsplit_1_memval2)(AT)
        addiu A0, R0, 3
        addiu A1, R0, 174
        jal   0x80045D84
        addiu A2, R0, 1
        lui   AT, hi(chainsplit_1_memval3)
        sw    V0, lo(chainsplit_1_memval3)(AT)
        addiu A0, R0, 11
        addiu A1, R0, 188
        jal   0x80045D84
        addiu A2, R0, 1
        lui   AT, hi(chainsplit_1_memval4)
        sw    V0, lo(chainsplit_1_memval4)(AT)
        jal   SleepProcess
        addiu A0, R0, 3
        addiu V0, R0, 1
        lui   AT, hi(CORE_800EE320)
        sh    V0, lo(CORE_800EE320)(AT)
        lw    RA, 0x10(SP)
        jr    RA
        addiu SP, SP, 0x18

      chainsplit_1_hide_arrows:
        addiu SP, SP, -0x18
        sw    RA, 0x10(SP)
        lui   AT, hi(CORE_800EE320)
        sh    R0, lo(CORE_800EE320)(AT)
        lui   A0, hi(chainsplit_1_memval1)
        jal   0x80045E6C
        lw    A0, lo(chainsplit_1_memval1)(A0)
        lui   A0, hi(chainsplit_1_memval2)
        jal   0x80045E6C
        lw    A0, lo(chainsplit_1_memval2)(A0)
        lui   A0, hi(chainsplit_1_memval3)
        jal   0x80045E6C
        lw    A0, lo(chainsplit_1_memval3)(A0)
        lui   A0, hi(chainsplit_1_memval4)
        jal   0x80045E6C
        lw    A0, lo(chainsplit_1_memval4)(A0)
        lw    RA, 0x10(SP)
        jr    RA
        addiu SP, SP, 0x18

      chainsplit_1_memval1:
        .word 0
      chainsplit_1_memval2:
        .word 0
      chainsplit_1_memval3:
        .word 0
      chainsplit_1_memval4:
        .word 0
    .endstatic
    """


ChainSplit1 = Event(
    id="CHAINSPLIT1",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    parameters=[
        {"name": "left_space", "type": EventParameterType.Space.value},
        {"name": "right_space", "type": EventParameterType.Space.value},
        {"name": "chains", "type": EventParameterType.NumberArray.value},
    ],
    fake_event=True,
    supported_games=[Game.MP1_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ChainSplit1)
