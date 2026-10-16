"""ChainMerge: the "event" that takes the player from one chain to another (ChainMergeEvent.ts).

This won't be an actual event when exposed to the user.
"""

from ...types import EditorEventActivationType, EventExecutionType, EventParameterType, Game
from ..event_library import add_event_to_library
from ..events import Event
from ..jsfmt import is_nan, js_or, js_str
from .hash_util import hash_equal


def _chain_at(chains, chain, index):
    # chains[chain][index] (undefined when out of range).
    c = chains[chain]
    if 0 <= index < len(c):
        return c[index]
    return None


def _parse(data_view, info):
    from ...boards import add_connection_internal

    hashes = {
        # Same start and end hashes for MP1, MP2
        "START": "d218c758ea3247b6e5ec2ae0c3568a92",  # +0x0C
        "END": "560c69d6e851f4a22984b74c660e8536",  # [0x18/0x24]+0x0C

        "EXTRA_CALL_START": "BABAF76D201027AE882BEB58BB38B4EB",  # +0x18
    }

    offset = info["offset"]

    # See if this is the the stock, inefficient method.
    if hash_equal([data_view.buffer, offset, 0x0C], hashes["START"]):
        # First 3 instructions
        if hash_equal([data_view.buffer, offset + 0x18, 0x0C], hashes["END"]):
            # Last 3 instructions
            # Read the chain we are going to.
            next_chain = data_view.get_uint16(offset + 0x0E)
            next_chain = 0 if next_chain > 1000 else next_chain  # R0 will be 0x2821 - just check for "way to big".

            # Read the offset into the chain.
            if data_view.get_uint16(offset + 0x14) == 0:
                # Usually this is an add with R0.
                next_space = _chain_at(info["chains"], next_chain, 0)
            else:
                next_space = _chain_at(info["chains"], next_chain,
                                       data_view.get_uint16(offset + 0x16))

            # This isn't an event really - write directly to the board links.
            if not is_nan(next_space):
                add_connection_internal(info["cur_space"], next_space, info["board"])

            return True

    # There is another MP1 variation that sends A0 with something else than -1.
    if hash_equal([data_view.buffer, offset, 0x18], hashes["EXTRA_CALL_START"]):
        if hash_equal([data_view.buffer, offset + 0x24, 12], hashes["END"]):
            # Last 3 instructions
            # Read the chain we are going to.
            next_chain = data_view.get_uint16(offset + 0x1A)
            next_chain = 0 if next_chain > 1000 else next_chain  # R0 will be 0x2821 - just check for "way to big".

            # Read the offset into the chain.
            if data_view.get_uint16(offset + 0x20) == 0:
                # Usually this is an add with R0.
                next_space = _chain_at(info["chains"], next_chain, 0)
            else:
                next_space = _chain_at(info["chains"], next_chain,
                                       data_view.get_uint16(offset + 0x22))

            # This isn't an event really - write directly to the board links.
            if isinstance(next_space, (int, float)) and not isinstance(next_space, bool):
                add_connection_internal(info["cur_space"], next_space, info["board"])

            return True

    return False


# TODO: We can do a O(1) + n/2 style improvement for this event.
def _write(data_view, event, info, temp):
    pv = event["parameterValues"]
    asm = f"""@@TPL@@"""

    return asm


ChainMerge = Event(
    id="CHAINMERGE",
    name="",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    parameters=[
        {"name": "prevSpace", "type": EventParameterType.Number.value},
        {"name": "chain", "type": EventParameterType.Number.value},
        {"name": "spaceIndex", "type": EventParameterType.Number.value},
    ],
    fake_event=True,
    supported_games=[Game.MP1_USA, Game.MP2_USA],
    parse=_parse,
    write=_write,
)
add_event_to_library(ChainMerge)
