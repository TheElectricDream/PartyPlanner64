"""Board definition files: spaces and chains (port of adapter/boarddef.ts).

The board def ("boarddef") is the MainFS file that lists a board's spaces
(type and 3d position) and its "chains", runs of linked spaces.
"""

import logging
import math

from ..types import Space
from ..utils.number import midpoint, distance
from ..utils.debug import log, hexstr
from ..utils.obj import copy_object
from ..utils.dataview import DataView
from ._js import at, get_link, index_of, is_number, js_keys, link_key

logger = logging.getLogger("partyplanner64")


def _get_game_version():
    from ..romhandler import romhandler
    return romhandler.get_game_version()


def parse(buffer, board):
    """Parse a board def into a (partial) board.

    Sets board["spaces"], board["links"] and board["_chains"] (the chains are
    needed for event parsing; the caller removes them).
    """
    header = _parse_header(buffer)
    board["spaces"] = _parse_spaces(buffer, header)
    link_result = _parse_links(buffer, header)
    board["links"] = link_result["links"]
    board["_chains"] = link_result["chains"]  # We need this for event parsing.
    log("Parsing board def, %s (%d) spaces" % (hexstr(header["space_count"]), header["space_count"]))
    return board


def _parse_header(buffer):
    board16_view = DataView(buffer)
    game = _get_game_version()
    if game == 1:
        return {
            "space_count": board16_view.get_uint16(0),
            "chain_count": board16_view.get_uint16(4),
            "space_start_offset": board16_view.get_uint16(6),
            "link_start_offset": board16_view.get_uint16(10),
        }
    if game in (2, 3):
        return {
            "space_count": board16_view.get_uint16(0),
            "chain_count": board16_view.get_uint16(2),
            "space_start_offset": board16_view.get_uint16(4),
            "link_start_offset": board16_view.get_uint16(6),
        }

    raise ValueError("Unrecongized game %s" % (game,))


def _parse_spaces(buffer, header):
    space_view = DataView(buffer, header["space_start_offset"])
    spaces = []
    buffer_idx = 0
    for _ in range(header["space_count"]):
        spaces.append({
            "type": space_view.get_uint8(buffer_idx + 3),
            "x": space_view.get_float32(buffer_idx + 4),
            "y": space_view.get_float32(buffer_idx + 12),
            "z": space_view.get_float32(buffer_idx + 8),
        })
        buffer_idx += 16

    return spaces


def _parse_links(buffer, header):
    chains = [None] * header["chain_count"]
    links = {}
    links_view = DataView(buffer, header["link_start_offset"])
    for i in range(header["chain_count"]):
        chain_offset = links_view.get_uint16(i * 2)
        chain_view = DataView(buffer, header["link_start_offset"] + chain_offset)
        chain_len = chain_view.get_uint16(0)
        chains[i] = []
        if chain_len == 1:
            # The loop won't work.
            chains[i].append(chain_view.get_uint16(2))
        else:
            for j in range(1, chain_len):
                start = chain_view.get_uint16(j * 2)
                end = chain_view.get_uint16((j + 1) * 2)
                key = start  # (A string key in board JSON.)
                if key in links:
                    if not isinstance(links[key], list):
                        links[key] = [links[key]]
                    if end not in links[key]:
                        links[key].append(end)
                else:
                    links[key] = end
                chains[i].append(start)
                if j + 1 == chain_len:
                    chains[i].append(end)

    # Keep the key order a JavaScript object would have.
    links = {key: links[key] for key in js_keys(links)}

    return {
        "links": links,
        "chains": chains,
    }


def create(board, chains=None):
    """Create a board def buffer (bytearray) for a board."""
    if chains is None:
        chains = determine_chains(board)
    board_def_buffer = bytearray(_board_def_size(board, chains))
    _write_header(board_def_buffer, board, chains)
    _write_spaces(board_def_buffer, board["spaces"])
    _write_chains(board_def_buffer, chains)
    return board_def_buffer


def _board_def_size(board, chains):
    """Calculates the byte length needed to create a board def."""
    header_size = _board_def_header_size()
    spaces_size = len(board["spaces"]) * 16

    chains_size = len(chains) * 2  # The 16-bit offsets for each chain.
    for chain in chains:
        chains_size += (len(chain) + 1) * 2  # +1 for chain length short

    return header_size + spaces_size + chains_size


def _board_def_header_size():
    game = _get_game_version()
    if game == 1:
        header_size = 12
    elif game in (2, 3):
        header_size = 8
    else:
        raise ValueError("_boardDefHeaderSize: unknown game version %s" % (game,))

    return header_size


def _write_header(board_def_buffer, board, chains):
    board_def_view = DataView(board_def_buffer)
    game = _get_game_version()
    chain_offset = _board_def_header_size() + len(board["spaces"]) * 16
    if game == 1:
        board_def_view.set_uint16(0, len(board["spaces"]))
        board_def_view.set_uint16(4, len(chains))
        board_def_view.set_uint16(6, 0xC)
        board_def_view.set_uint16(8, chain_offset)
        board_def_view.set_uint16(10, chain_offset)
    elif game in (2, 3):
        board_def_view.set_uint16(0, len(board["spaces"]))
        board_def_view.set_uint16(2, len(chains))
        board_def_view.set_uint16(4, 0x8)
        board_def_view.set_uint16(6, chain_offset)


def _write_spaces(board_def_buffer, spaces):
    board_def_view = DataView(board_def_buffer)
    cur_offset = _board_def_header_size()
    for space in spaces:
        board_def_view.set_uint32(cur_offset, space["type"])
        board_def_view.set_float32(cur_offset + 4, space["x"])
        board_def_view.set_float32(cur_offset + 8, space.get("z") or 0)
        board_def_view.set_float32(cur_offset + 12, space["y"])
        cur_offset += 16


def _write_chains(board_def_buffer, chains):
    board_def_view = DataView(board_def_buffer)

    offsets_offset = _parse_header(board_def_buffer)["link_start_offset"]  # Yuck!
    chain_region_offset = offsets_offset

    chain_offset = len(chains) * 2
    for chain in chains:
        # Write the entry into the chain offsets.
        board_def_view.set_uint16(offsets_offset, chain_offset)

        # Write the chain size.
        board_def_view.set_uint16(chain_region_offset + chain_offset, len(chain))
        chain_offset += 2

        # Write the chain indices.
        for space_index in chain:
            board_def_view.set_uint16(chain_region_offset + chain_offset, space_index)
            chain_offset += 2

        offsets_offset += 2


def determine_chains(board):
    """Builds a list of lists of space indices representing the board chains."""
    from ..boards import get_connections, get_start_space_index, has_connection

    board = copy_object(board)
    spaces = board["spaces"]
    links = board.get("links") or {}
    chains = []

    # Recursive chain parsing function.
    def parse_chain(starting_space_idx):
        chain = []  # Given first space always goes in.
        cur_space_idx = starting_space_idx
        while True:
            cur_space = at(spaces, cur_space_idx)
            if cur_space is None:
                raise TypeError("Cannot read properties of undefined (reading '_seen')")
            if cur_space.get("_seen"):
                break
            cur_space["_seen"] = True
            chain.append(cur_space_idx)
            next_space_idx = get_link(links, cur_space_idx)

            # Must break the chain if path divides.
            if isinstance(next_space_idx, list):
                chains.append(chain)
                for idx in next_space_idx:
                    parse_chain(idx)
                return

            # Hit a dead end. Just warn but keep going.
            if not is_number(next_space_idx):
                logger.warning("determineChains.parseChain hit a dead end at %s (%d)",
                               hexstr(cur_space_idx), cur_space_idx)
                chains.append(chain)
                return

            # Must break the chain if a chain intersects the next space.
            if space_is_linked_from_by_another(next_space_idx, cur_space_idx):
                chains.append(chain)
                parse_chain(next_space_idx)
                return

            cur_space_idx = next_space_idx

        # There will be no chain len if this parseChain call was previously made.
        if chain:
            chains.append(chain)

    # Build a reverse lookup of space to _pointing_ spaces.
    pointing_map = {}
    for s in range(len(spaces)):
        if spaces[s] is not None:
            pointing_map[s] = []
    for start_idx in js_keys(links):
        ends = get_connections(int(start_idx), board)
        for end in ends:
            pointing_map[end].append(int(start_idx))

    # Returns true if the given space is linked to from another space besides
    # the previous space.
    def space_is_linked_from_by_another(space_idx, prev_idx=None):
        # If no previous index passed, just see if anything points.
        if prev_idx is None:
            return bool(len(pointing_map[space_idx]))

        if not len(pointing_map[space_idx]):
            return False
        if index_of(pointing_map[space_idx], prev_idx) == -1:
            return True
        if len(pointing_map[space_idx]) > 1:
            return True  # Assumes prevIdx is not duplicated
        return False  # length === 1 && only entry is prevIdx

    # We want to generate chains starting at the start space, and starting
    # from any space that doesn't have anything pointing at it.
    # The latter is for dead ends that you can only reach via going in reverse
    # in MP3, or perhaps in the future if we have warps or something.
    # Doing start space first is important because MP2/3 assume start space
    # is first space of first chain.

    # 1. Parse from start space.
    parse_chain(get_start_space_index(board))

    # 2. Parse from other "starting spaces" of paths.
    for s in range(len(spaces)):
        if spaces[s] is None:
            continue
        if spaces[s].get("_seen"):
            continue  # Don't even need to check, we already visited it.

        # The latter condition is not totally necessary, but I don't know that
        # we want to or can handle single-space chains.
        if not space_is_linked_from_by_another(s) and has_connection(s, "*", board):
            parse_chain(s)

    # 3. Catch any "cycles" that might be left, if they reached this point.
    for s in range(len(spaces)):
        if spaces[s] is None or spaces[s].get("_seen"):
            continue

        # Handle all others, even single decorative spaces.
        parse_chain(s)

    log("chains: ", chains)
    return chains


def pad_chains(board, chains):
    """Pad 1-length chains with an extra invisible space.

    WTF is this?
    There are bytes that can live right where DK's chains get written.
    If we don't overwrite these and have a 1-length chain, it becomes part of the chain and CRASH.
    If we pad to at least 2-length chains, we guarantee to overwrite it, and
    who knows if 1-length chains actually work anyways.
    """
    from ..boards import add_space_internal
    from ..events.event_library import get_events_in_library

    spaces = board["spaces"]
    if board.get("links") is None:
        board["links"] = {}
    links = board["links"]
    for chain in chains:
        if len(chain) == 1:
            # Padding is done by adding an extra transparent space in such a way that the player won't notice.
            last_space_idx = chain[0]
            last_space = spaces[last_space_idx]
            old_links = get_link(links, last_space_idx)
            pad_x = pad_y = None
            if isinstance(old_links, list):
                if len(old_links) == 1:
                    # Shouldn't happen, but there was a bug where some boards might have these 1 length arrays.
                    # CHAINMERGE
                    # Just put it half way in between, who cares.
                    next_space = spaces[old_links[0]]
                    mid = midpoint(last_space["x"], last_space["y"], next_space["x"], next_space["y"])
                    pad_x = mid["x"]
                    pad_y = mid["y"]
                elif len(old_links) == 2:
                    # CHAINSPLIT
                    # TODO: Very precisely push it towards the split spaces, otherwise the player faces down always.
                    next_left = spaces[old_links[0]]
                    next_right = spaces[old_links[1]]
                    dest_midpoint = midpoint(next_left["x"], next_left["y"],
                                             next_right["x"], next_right["y"])
                    # padX = lastSpace.x + 0.01;
                    # padY = ((destMidpoint.y - lastSpace.y) / (destMidpoint.x - lastSpace.x)) * (padX - lastSpace.x) + lastSpace.y;
                    dist = distance(last_space["x"], last_space["y"],
                                    dest_midpoint["x"], dest_midpoint["y"])
                    ratio = 0.01 / dist if dist else math.inf
                    pad_x = (1 - ratio) * last_space["x"] + ratio * dest_midpoint["x"]
                    pad_y = (1 - ratio) * last_space["y"] + ratio * dest_midpoint["y"]
                    log("Padding branch x: %s, y: %s, padX: %s, padY: %s"
                        % (last_space["x"], last_space["y"], pad_x, pad_y))
                else:
                    # FIXME when multi-split works.
                    pad_x = last_space["x"]
                    pad_y = last_space["y"]
            elif is_number(old_links):
                # CHAINMERGE
                # Just put it half way in between, who cares.
                next_space = spaces[old_links]
                mid = midpoint(last_space["x"], last_space["y"], next_space["x"], next_space["y"])
                pad_x = mid["x"]
                pad_y = mid["y"]

            if is_number(pad_x) and is_number(pad_y):
                new_link = add_space_internal(pad_x, pad_y, Space.OTHER, None, board,
                                              get_events_in_library())
                chain.append(new_link)

                # CS classic, insert into linkedish list.
                links[link_key(links, last_space_idx)] = new_link
                links[link_key(links, new_link)] = old_links


def trim_chains(board, chains):
    # TODO: This would make board parsing not have weird extra spaces.
    pass


def get_chain_index_values_from_absolute_index(chains, abs_space_index):
    """Gets the "chain index" and "chain space index" for an absolute
    space index found somewhere within the chains.
    """
    for c, chain in enumerate(chains):
        chain_space_index = index_of(chain, abs_space_index)
        if chain_space_index >= 0:
            return [c, chain_space_index]
    return [-1, -1]
