"""Board (IBoard) helpers that don't touch the editor state (boards.ts).

Boards are plain dicts with the board JSON's camelCase keys. Spaces are dicts
({"x", "y", "z", "type", "subtype"?, "rotation"?, "events"?, "star"?,
"aiTree"?}) and event instances are dicts ({"id", "activationType",
"executionType", "parameterValues"?, "custom"?}).

`board["links"]` maps a starting space index to an index or a list of
indices. JSON gives string keys ("3"); fix_potentially_old_board turns them
into ints, which json.dumps writes back as the same strings. Every helper
here accepts either kind of key.
"""

from enum import IntEnum
import logging

from .events.event_library import get_events_in_library
from .events.events import get_event
from .types import BoardType, CostumeType, EventCodeLanguage, Space
from .utils.debug import assert_
from .utils.obj import copy_object

logger = logging.getLogger("partyplanner64")


class BoardAudioType(IntEnum):
    """Type of board audio."""
    # Song from the original game.
    InGame = 0
    # Song provided by the user.
    Custom = 1


# ---------------------------------------------------------------------------
# Links (Python helpers for the int/str key duality; not in the TypeScript).

def _is_index_key(key):
    if isinstance(key, bool):
        return False
    if isinstance(key, int):
        return key >= 0
    return isinstance(key, str) and key.isdigit() and key.isascii() \
        and (key == "0" or not key.startswith("0"))


def _link_key(links, index):
    """The key under which `links` holds `index`'s connections, or None."""
    if links is None:
        return None
    if index in links:
        return index
    s = str(index)
    if s in links:
        return s
    if isinstance(index, str):
        try:
            i = int(index)
        except ValueError:
            return None
        if i in links:
            return i
    return None


def get_link(board, index):
    """board.links[index]: an int, a list of ints, or None."""
    links = board.get("links")
    key = _link_key(links, index)
    if key is None:
        return None
    return links[key]


def has_link_key(board, index):
    """board.links.hasOwnProperty(index)."""
    return _link_key(board.get("links"), index) is not None


def get_link_start_indices(board):
    """The starting space indices in board.links, in the order JavaScript's
    `for (const idx in board.links)` visits them (integer keys ascending
    first, then the rest in insertion order)."""
    links = board.get("links") or {}
    index_keys = []
    other_keys = []
    for key in links:
        if _is_index_key(key):
            index_keys.append(int(key))
        else:
            try:
                other_keys.append(int(key))
            except (TypeError, ValueError):
                other_keys.append(key)
    return sorted(set(index_keys)) + other_keys


def _normalize_links(board):
    links = board.get("links")
    if not isinstance(links, dict):
        return
    normalized = {}
    for start in get_link_start_indices(board):
        normalized[start] = get_link(board, start)
    board["links"] = normalized


# ---------------------------------------------------------------------------

def fix_potentially_old_board(board):
    """Applies "fixes" to a board which may be from an older editor version.

    Returns the given board (modified in place). Also turns the string keys of
    board["links"] into ints (see the module docstring).
    """
    if "game" not in board:
        board["game"] = 1

    if "type" not in board:
        board["type"] = BoardType.NORMAL.value

    if "events" not in board:
        board["events"] = {}

    for event_id in list(board["events"]):
        event_data = board["events"][event_id]
        if isinstance(event_data, str):
            board["events"][event_id] = {
                "code": event_data,
                "language": int(EventCodeLanguage.MIPS),
            }

    if "audioType" not in board:
        board["audioType"] = int(BoardAudioType.InGame)

    if board.get("audioData") and not isinstance(board["audioData"], list):
        board["audioData"] = [board["audioData"]]

    if board["game"] == 2 and not _is_number(board.get("costumeTypeIndex")):
        board["costumeTypeIndex"] = int(CostumeType.NORMAL)

    _migrate_old_custom_events(board)

    _normalize_links(board)

    if "fov" not in board["bg"]:
        game = board["game"]
        if game == 3:
            if board["type"] == BoardType.DUEL:
                board["bg"].update({
                    "fov": 15,
                    "scaleFactor": 0.1,
                    "cameraEyePosX": 0,
                    "cameraEyePosY": 210,
                    "cameraEyePosZ": 210,
                    "lookatPointX": 0,
                    "lookatPointY": 0,
                    "lookatPointZ": 0,
                })
            else:
                board["bg"].update({
                    "fov": 15,
                    "scaleFactor": 0.1,
                    "cameraEyePosX": 0,
                    "cameraEyePosY": 300,
                    "cameraEyePosZ": 300,
                    "lookatPointX": 0,
                    "lookatPointY": 0,
                    "lookatPointZ": 0,
                })
        elif game == 2:
            board["bg"].update({
                "fov": 3,
                "scaleFactor": 0.1,
                "cameraEyePosX": 0,
                "cameraEyePosY": 1570,
                "cameraEyePosZ": 1577,
                "lookatPointX": 0,
                "lookatPointY": 0,
                "lookatPointZ": 0,
            })
        elif game == 1:
            board["bg"].update({
                "fov": 17,
                "scaleFactor": 1,
                "cameraEyePosX": 0,
                "cameraEyePosY": 1355,
                "cameraEyePosZ": 1780,
                "lookatPointX": 0,
                "lookatPointY": 0,
                "lookatPointZ": 0,
            })

    return board


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _migrate_old_custom_events(board):
    def fix(space_event, *_):
        # Unnecessary properties of space events.
        space_event.pop("parameters", None)
        space_event.pop("supportedGames", None)

        # Move any asm into the single collection.
        if space_event.get("asm"):
            space_event["id"] = space_event.get("name")
            existing = board["events"].get(space_event["id"])
            if existing and existing != space_event["asm"]:
                logger.warning(
                    "When updating the format of %s, event %s had multiple versions. "
                    "Only one will be kept.", board.get("name"), space_event["id"])
            board["events"][space_event["id"]] = space_event["asm"]
            del space_event["asm"]

    for_each_event(board, fix)


def has_connection(start_idx, end_idx, board):
    """Tests if there is a connection from start_idx to end_idx.

    If end_idx is "*" (or omitted, as in the TypeScript's undefined), tests if
    any connection is outbound from start_idx. None stands for JavaScript's
    null, which matches nothing.
    """
    link = get_link(board, start_idx)
    if isinstance(link, list):
        if end_idx == "*":
            return True  # Asking if any connections exist out of startIdx
        return end_idx in link
    if link is not None:
        if end_idx == "*":
            return True
        return link == end_idx
    return False


def get_connections(space_index, board):
    """Returns list of space indices connected to from a space."""
    if space_index < 0:
        return None

    if not board.get("links"):
        return []

    link = get_link(board, space_index)
    if isinstance(link, list):
        return link[:]

    if _is_number(link):
        return [link]

    return []


def add_connection_internal(start_space_index, end_space_index, board):
    """Adds a connection, no redux state modification."""
    if end_space_index is None:
        return  # (JavaScript's undefined: nothing would be added.)
    if start_space_index == end_space_index or \
            has_connection(start_space_index, end_space_index, board):
        return

    if not board.get("links"):
        board["links"] = {}
    links = board["links"]
    key = _link_key(links, start_space_index)
    current = links[key] if key is not None else None
    if key is None:
        key = start_space_index
    if isinstance(current, list):
        current.append(end_space_index)
    elif _is_number(current):
        links[key] = [current, end_space_index]
    elif end_space_index >= 0:
        links[key] = end_space_index


def get_board_event(board, event_id):
    """The board's copy of a custom event's code: {"language", "code"} or None."""
    if board.get("events"):
        board_event = board["events"].get(event_id)
        if isinstance(board_event, str):
            return {"language": int(EventCodeLanguage.MIPS), "code": board_event}
        return board_event or None
    return None


def include_event_in_board_internal(board, event):
    if not event.asm:
        raise ValueError(f"Attempting to add event {event.name} but it doesn't have code")
    board["events"][event.name] = {
        "language": int(event.language),
        "code": event.asm,
    }


def add_event_to_space_internal(board, space, event, to_start, event_library):
    if space.get("events") is None:
        space["events"] = []
    if event:
        if to_start:
            space["events"].insert(0, event)
        else:
            space["events"].append(event)

        if event.get("custom"):
            custom_event = get_event(event["id"], board, event_library)
            include_event_in_board_internal(board, custom_event)


def get_additional_background_code(board):
    if board.get("additionalbgcode"):
        additional_bg_code = board["additionalbgcode"]
        if isinstance(additional_bg_code, str):
            return {"language": int(EventCodeLanguage.MIPS), "code": additional_bg_code}
        return additional_bg_code or None
    return None


def get_audio_select_code(board):
    return board.get("audioSelectCode") or None


def get_dead_ends(board):
    dead_ends = []
    spaces = copy_object(board["spaces"])
    links = board.get("links") or {}

    def _check_dead_end(start):
        # An iterative form of the TypeScript's recursive _checkDeadEnd
        # (which returns true as soon as it finds a dead end).
        stack = []
        node = start
        end = object()
        while True:
            if spaces[node].get("_seen"):
                result = False  # We have reached a previous space - no dead end.
            elif _link_key(links, node) is None:
                dead_ends.append(node)
                result = True
            else:
                spaces[node]["_seen"] = True
                next_spaces = get_link(board, node)
                stack.append(iter(next_spaces if isinstance(next_spaces, list) else [next_spaces]))
                result = None
            if result is True:
                return True
            while stack:
                n = next(stack[-1], end)
                if n is end:
                    stack.pop()
                    continue
                node = n
                break
            else:
                return None

    # Build a reverse lookup of space to _pointing_ spaces.
    pointing_map = {}
    for s in range(len(spaces)):
        if spaces[s]:
            pointing_map[s] = []
    for start_idx in get_link_start_indices(board):
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
        if int(prev_idx) not in pointing_map[space_idx]:
            return True
        if len(pointing_map[space_idx]) > 1:
            return True  # Assumes prevIdx is not duplicated
        return False  # length === 1 && only entry is prevIdx

    start_idx = get_start_space_index(board)
    if start_idx >= 0:
        _check_dead_end(start_idx)

    for s in range(len(spaces)):
        if not spaces[s]:
            continue
        if spaces[s].get("_seen"):
            continue  # Don't even need to check, we already visited it.

        # The latter condition is not totally necessary, but I don't know that
        # we want to or can handle single-space chains.
        # FIXME (from the TypeScript): passing null, so has_connection is always false.
        if not space_is_linked_from_by_another(s) and has_connection(s, None, board):
            _check_dead_end(s)

    return dead_ends


def supports_animation_backgrounds(board):
    return board.get("game") == 2


def supports_additional_backgrounds(board):
    return board.get("game") != 2


def get_space_index(space, board):
    for i, s in enumerate(board["spaces"]):
        if s is space:
            return i
    return -1


def get_start_space_index(board):
    spaces = board["spaces"]
    for i in range(len(spaces)):
        if not spaces[i]:
            continue
        if spaces[i].get("type") == Space.START:
            return i
    return -1


def get_spaces_of_type(type, board):
    spaces = board["spaces"]
    type_spaces = []
    for i in range(len(spaces)):
        if not spaces[i]:
            continue
        if spaces[i].get("type") == type:
            type_spaces.append(i)
    return type_spaces


def add_space_internal(x, y, type, subtype, board, event_library):
    new_space = {
        "x": x,
        "y": y,
        "z": 0,
        "type": int(type),
    }

    if subtype is not None:
        new_space["subtype"] = int(subtype)

    from .adapter.adapters import get_adapter
    adapter = get_adapter(board.get("game") or 1, {})
    if adapter:
        adapter.hydrate_space(new_space, board, event_library)

    board["spaces"].append(new_space)
    return len(board["spaces"]) - 1


def get_dead_space_index(board):
    """Gets the index of the "dead space." The space is created if it hasn't been already."""
    if _is_number(board.get("_deadSpace")):
        return board["_deadSpace"]
    dead_space_index = add_space_internal(
        board["bg"]["width"] + 150,
        board["bg"]["height"] + 100,
        Space.OTHER,
        None,
        board,
        get_events_in_library(),
    )
    board["_deadSpace"] = dead_space_index
    return dead_space_index


def get_dead_space(board):
    """Gets the "dead space." The space is created if it hasn't been already."""
    return board["spaces"][get_dead_space_index(board)]


def get_spaces_of_sub_type(subtype, board):
    spaces = board["spaces"]
    subtype_spaces = []
    for i in range(len(spaces)):
        if not spaces[i]:
            continue
        if spaces[i].get("subtype") == subtype and spaces[i].get("subtype") is not None:
            subtype_spaces.append(i)
    return subtype_spaces


def get_spaces_with_event(event_name, board):
    """Returns list of space indices of spaces with a given event."""
    event_spaces = []

    def fn(event, event_index, space=None, space_index=None):
        if space and event["id"] == event_name:
            event_spaces.append(space_index)

    for_each_event(board, fn)
    return event_spaces


def add_event_by_index(board, space_idx, event, to_start, event_library):
    space = board["spaces"][space_idx]
    add_event_to_space_internal(board, space, event, to_start, event_library)


def for_each_event(board, fn):
    """Calls fn(event, event_index, space=None, space_index=None) for every
    event instance: board events first, then each space's (in reverse, so the
    callback may delete)."""
    boardevents = board.get("boardevents")
    if boardevents:
        # Reverse to allow deletion in callback.
        for i in range(len(boardevents) - 1, -1, -1):
            event = boardevents[i]
            fn(event, i)

    spaces = board.get("spaces")
    if spaces:
        for s in range(len(spaces)):
            space = spaces[s]
            events = space.get("events") if space else None
            if events:
                for i in range(len(events) - 1, -1, -1):
                    event = events[i]
                    fn(event, i, space, s)


def for_each_event_parameter(board, event_library, fn):
    """Calls fn(parameter, event, event_index, space=None, space_index=None)
    for every parameter of every event instance."""
    def each(event_instance, event_index, space=None, space_index=None):
        event = get_event(event_instance["id"], board, event_library)
        assert_(bool(event))
        if event.parameters:
            for parameter in event.parameters:
                fn(parameter, event_instance, event_index, space, space_index)

    for_each_event(board, each)
