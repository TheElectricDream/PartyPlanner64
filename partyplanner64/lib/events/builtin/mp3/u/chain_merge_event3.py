"""ChainMerge3: the "event" that takes the player from one chain to another (ChainMergeEvent3.ts).

This won't be an actual event when exposed to the user.
"""

from .....types import EditorEventActivationType, EventExecutionType, EventParameterType, Game
from ....event_library import add_event_to_library
from ....events import Event
from ....jsfmt import is_nan, js_or, js_str
from ...hash_util import hash_equal


def _chain_at(chains, chain, index):
    c = chains[chain]
    if 0 <= index < len(c):
        return c[index]
    return None


def _parse(data_view, info):
    from .....boards import add_connection_internal, has_link_key

    # ChainMerge in 3 uses a helper function. It passes the space index of the
    # _previous_ space the player was before reaching the event space.
    hashes = {
        "START": "16092DD153432852C141C78807ECCBF0",  # +0x08
        # MID: "123FF0D66026C628870C3DAEE5C63134", // [0x10]+0x04 // Use mergeJALs instead
        "END": "0855E7309F121915D7A762AB85A7FDB6",  # [0x18]+0x08
    }

    merge_jals = [
        0x0C03B666,  # JAL 0x800ED998
        0x0C042307,  # JAL 0x80108C1C
    ]

    offset = info["offset"]
    if hash_equal([data_view.buffer, offset, 0x08], hashes["START"]) and \
            data_view.get_uint32(offset + 0x10) in merge_jals and \
            hash_equal([data_view.buffer, offset + 0x18, 0x08], hashes["END"]):
        # Read the chain we are going to.
        next_chain = data_view.get_uint16(offset + 0x0E)
        next_chain = 0 if next_chain > 1000 else next_chain  # R0 will be 0x2821 - just check for "way to big".

        # Read the offset into the chain.
        if data_view.get_uint16(offset + 0x14) == 0:
            # Usually this is an add with R0.
            next_space = _chain_at(info["chains"], next_chain, 0)
        else:
            next_space = _chain_at(info["chains"], next_chain, data_view.get_uint16(offset + 0x16))

        # This isn't an event really - write directly to the board links.
        if not is_nan(next_space):
            # I think this tries to prevent reading the "reverse" event...
            if has_link_key(info["board"], info["cur_space"]):
                return False

            add_connection_internal(info["cur_space"], next_space, info["board"])

        return True

    return False


def _write(data_view, event, info, temp):
    pv = event["parameterValues"]
    # TODO: Could just use "prevSpace" etc below, the definelabels should work...
    return f"""
      ADDIU SP, SP, -0x18
      SW    RA, 0x10(SP)
      ADDIU A0, R0, {js_str(js_or(pv.get("prevSpace"), 0))}
      ADDIU A1, R0, {js_str(js_or(pv.get("chain"), 0))}
      JAL   chainmerge_3_helper
      ADDIU A2, R0, {js_str(js_or(pv.get("spaceIndex"), 0))}
      LW    RA, 0x10(SP)
      JR    RA
      ADDIU SP, SP, 0x18

  .beginstatic
    chainmerge_3_helper:
      addiu SP, SP, -0x20
      sw    RA, 0x1c(SP)
      sw    S2, 0x18(SP)
      sw    S1, 0x14(SP)
      sw    S0, 0x10(SP)
      move  S0, A0
      move  S1, A1
      move  S2, A2
      jal   GetPlayerStruct
        li    A0, -1
      lbu   A0, 0x15(V0)
      sll   A0, A0, 0x18
      sra   A0, A0, 0x18
      lbu   A1, 0x16(V0)
      sll   A1, A1, 0x18
      sra   A1, A1, 0x18
      andi  A0, A0, 0xffff
      jal   GetAbsSpaceIndexFromChainSpaceIndex
        andi  A1, A1, 0xffff
      sll   V0, V0, 0x10
      sra   V0, V0, 0x10
      bne   V0, S0, chainmerge_3_helper_exit
        sll   A1, S1, 0x10
      sll   A2, S2, 0x10
      li    A0, -1
      sra   A1, A1, 0x10
      jal   SetNextChainAndSpace
        sra   A2, A2, 0x10
      chainmerge_3_helper_exit:
      lw    RA, 0x1c(SP)
      lw    S2, 0x18(SP)
      lw    S1, 0x14(SP)
      lw    S0, 0x10(SP)
      jr    RA
        addiu SP, SP, 0x20
  .endstatic
    """


ChainMerge3 = Event(
    id="CHAINMERGE3",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    parameters=[
        {"name": "prevSpace", "type": EventParameterType.Number.value},
        {"name": "chain", "type": EventParameterType.Number.value},
        {"name": "spaceIndex", "type": EventParameterType.Number.value},
    ],
    fake_event=True,
    supported_games=[Game.MP3_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ChainMerge3)
