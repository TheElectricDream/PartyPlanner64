"""The editor's board state and its reducers (port of apps/partyplanner64/boardState.ts).

The TypeScript kept this state in a Redux slice; here a `BoardState` holds the
same fields (snake_case) and each reducer is a function
`reducer(state, payload, event_library)` that changes the state in place.
`REDUCERS` maps the Redux action names ("setBoardNameAction", ...) to them.
The store (store.py) gives every reducer a draft copy of the state, as
immer did, so states kept in the undo history never change.

Differences from the TypeScript:
- The event library is not part of this state (see store.py); reducers get
  it as `event_library` (an id -> event dict).
- The reducers that worked on "the one selected space" accept an optional
  `spaceIndex` in their payload, so the server needn't track the selection.
- Boards are plain dicts as in the board JSON, so `links` keys are strings.
"""

import copy
from enum import IntEnum

from ..lib.types import EventParameterType
from ..lib.utils.debug import assert_
from ..lib.utils.number import line_distance
from ..lib.utils.obj import copy_object


class EventType(IntEnum):
    None_ = 0
    Library = 1
    Board = 2


def _boards_lib():
    from ..lib import boards
    return boards


class BoardState:
    """The boardState slice of the Redux store (without the event library)."""

    __slots__ = ("boards", "rom_boards", "current_board_index", "current_board_is_rom",
                 "selected_space_indices", "selection_box_coords", "highlighted_space_indices",
                 "temporary_connections", "current_event_id", "current_event_type",
                 "hovered_board_event_index")

    def __init__(self):
        self.boards = []
        self.rom_boards = []
        self.current_board_index = 0
        self.current_board_is_rom = False
        self.selected_space_indices = {}
        self.selection_box_coords = None
        self.highlighted_space_indices = None
        self.temporary_connections = None
        self.current_event_id = None
        self.current_event_type = EventType.None_
        self.hovered_board_event_index = -1

    def draft(self, edit_board=True):
        """A copy to change: the lists are copied, and (edit_board) the current board."""
        d = BoardState.__new__(BoardState)
        for name in BoardState.__slots__:
            setattr(d, name, getattr(self, name))
        d.boards = list(self.boards)
        d.rom_boards = list(self.rom_boards)
        d.selected_space_indices = dict(self.selected_space_indices)
        if edit_board:
            collection = d.rom_boards if d.current_board_is_rom else d.boards
            if 0 <= d.current_board_index < len(collection):
                collection[d.current_board_index] = copy.deepcopy(collection[d.current_board_index])
        return d

    def __eq__(self, other):
        if not isinstance(other, BoardState):
            return NotImplemented
        return all(getattr(self, n) == getattr(other, n) for n in BoardState.__slots__)

    def __ne__(self, other):
        eq = self.__eq__(other)
        return eq if eq is NotImplemented else not eq

    __hash__ = None

    def ui(self):
        """The UI fields, for the API (camelCase)."""
        return {
            "selectedSpaceIndices": sorted(int(i) for i in self.selected_space_indices),
            "highlightedSpaceIndices": self.highlighted_space_indices,
            "selectionBoxCoords": self.selection_box_coords,
            "temporaryConnections": self.temporary_connections,
            "hoveredBoardEventIndex": self.hovered_board_event_index,
            "currentEventId": self.current_event_id,
            "currentEventType": int(self.current_event_type),
        }


def _make_default_board(*args):
    from .boards import _make_default_board as make
    return make(*args)


# Reducers


def set_boards_action(state, payload, event_library):
    state.boards = list(payload["boards"])


def add_board_action(state, payload, event_library):
    board = payload["board"]
    collection = state.rom_boards if payload.get("rom") else state.boards
    collection.append(board)


def delete_board_action(state, payload, event_library):
    board_index = payload.get("boardIndex")
    if (not isinstance(board_index, (int, float)) or isinstance(board_index, bool)
            or board_index != board_index or board_index < 0
            or board_index >= len(state.boards)):
        return
    board_index = int(board_index)

    if len(state.boards) == 1:
        state.boards.append(_make_default_board())  # Can never leave empty.

    del state.boards[board_index]

    next_board_index = -1
    if state.current_board_index > board_index:
        next_board_index = state.current_board_index - 1
    elif len(state.boards) == 1:
        next_board_index = 0  # We deleted the last remaining board
    elif (state.current_board_index == board_index
          and state.current_board_index == len(state.boards)):
        next_board_index = state.current_board_index - 1  # We deleted the end and current entry.

    if next_board_index >= 0:
        state.current_board_index = next_board_index
        state.current_board_is_rom = False


def set_current_board_action(state, payload, event_library):
    index = payload["index"]
    rom = bool(payload.get("rom"))

    changing = state.current_board_index != index or state.current_board_is_rom != rom

    state.current_board_index = index
    state.current_board_is_rom = rom

    if changing:
        state.selected_space_indices = {}
        state.selection_box_coords = None
        state.hovered_board_event_index = -1
        state.temporary_connections = None
        state.highlighted_space_indices = None


def clear_boards_from_rom_action(state, payload, event_library):
    state.rom_boards = []

    if not state.boards:
        state.boards.append(_make_default_board())  # Can never leave empty.


def copy_current_board_action(state, payload, event_library):
    source = get_current_board(state)

    board_copy = copy_object(source)
    board_copy.pop("_rom", None)
    board_copy["name"] = "Copy of " + str(board_copy.get("name"))

    if state.current_board_is_rom:
        insertion_index = len(state.boards)
        state.boards.append(board_copy)
    else:
        insertion_index = state.current_board_index + 1
        state.boards.insert(insertion_index, board_copy)

    if (payload or {}).get("makeCurrent"):
        state.current_board_index = insertion_index
        state.current_board_is_rom = False


def set_board_name_action(state, payload, event_library):
    get_current_board(state)["name"] = payload["name"]


def set_board_description_action(state, payload, event_library):
    get_current_board(state)["description"] = payload["description"]


def set_board_difficulty_action(state, payload, event_library):
    get_current_board(state)["difficulty"] = payload["difficulty"]


def set_board_costume_type_index_action(state, payload, event_library):
    get_current_board(state)["costumeTypeIndex"] = payload["costumeType"]


def set_background_action(state, payload, event_library):
    get_current_board(state)["bg"]["src"] = payload["bg"]


def set_board_other_bg_action(state, payload, event_library):
    get_current_board(state)["otherbg"][payload["name"]] = payload["value"]


def add_animation_background_action(state, payload, event_library):
    board = get_current_board(state)
    board["animbg"] = board.get("animbg") or []
    board["animbg"].append(payload["bg"])


def remove_animation_background_action(state, payload, event_library):
    index = payload["index"]
    board = get_current_board(state)
    if not board.get("animbg") or len(board["animbg"]) <= index or index < 0:
        return
    del board["animbg"][index]


def add_additional_background_action(state, payload, event_library):
    board = get_current_board(state)
    board["additionalbg"] = board.get("additionalbg") or []
    board["additionalbg"].append(payload["bg"])


def remove_additional_background_action(state, payload, event_library):
    index = payload["index"]
    board = get_current_board(state)
    if not board.get("additionalbg") or len(board["additionalbg"]) <= index or index < 0:
        return
    del board["additionalbg"][index]


def set_additional_background_code_action(state, payload, event_library):
    code = payload.get("code")
    board = get_current_board(state)
    if code:
        board["additionalbgcode"] = {"code": code, "language": payload.get("language")}
    else:
        board.pop("additionalbgcode", None)


def set_audio_select_code_action(state, payload, event_library):
    code = payload.get("code")
    board = get_current_board(state)
    if code:
        board["audioSelectCode"] = {"code": code, "language": payload.get("language")}
    else:
        board.pop("audioSelectCode", None)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def set_board_audio_action(state, payload, event_library):
    audio_changes = payload["audioChanges"]
    board = get_current_board(state)

    if "audioType" in audio_changes:
        board["audioType"] = audio_changes["audioType"]
        if audio_changes["audioType"] == 1:  # BoardAudioType.Custom
            if not board.get("audioData"):
                board["audioData"] = []

    if _is_number(audio_changes.get("gameAudioIndex")):
        board["audioIndex"] = audio_changes["gameAudioIndex"]

    custom_audio_index = audio_changes.get("customAudioIndex")
    if _is_number(custom_audio_index):
        assert_(isinstance(board.get("audioData"), list))
        assert_(custom_audio_index <= len(board["audioData"]))

        if custom_audio_index == len(board["audioData"]):
            board["audioData"].append({
                "name": "(select a midi file)",
                "data": "",
                "soundbankIndex": 0,
            })

        if audio_changes.get("delete"):
            assert_(custom_audio_index < len(board["audioData"]))
            del board["audioData"][custom_audio_index]
        else:
            entry = board["audioData"][custom_audio_index]
            if audio_changes.get("midiName"):
                entry["name"] = audio_changes["midiName"]
            if audio_changes.get("midiData"):
                entry["data"] = audio_changes["midiData"]
            if _is_number(audio_changes.get("soundbankIndex")):
                entry["soundbankIndex"] = audio_changes["soundbankIndex"]


def add_space_action(state, payload, event_library):
    board = get_current_board(state)
    _boards_lib().add_space_internal(payload["x"], payload["y"], payload["type"],
                                     payload.get("subtype"), board, event_library)


def remove_space_action(state, payload, event_library):
    remove_space(state, get_current_board(state), payload["index"], event_library)


def remove_spaces_action(state, payload, event_library):
    space_indices = list(payload["spaceIndices"])
    current_board = get_current_board(state)
    for i in range(len(space_indices)):
        space_index = space_indices[i]
        if remove_space(state, current_board, space_index, event_library):
            # Adjust indices, since deleting index N affects the indices after N.
            for j in range(i + 1, len(space_indices)):
                if space_indices[j] > space_index:
                    space_indices[j] -= 1


def add_connection_action(state, payload, event_library):
    board = get_current_board(state)
    _boards_lib().add_connection_internal(payload["startSpaceIndex"], payload["endSpaceIndex"],
                                          board)

    # Otherwise this may show up in undo/redo states.
    state.temporary_connections = None


def erase_connections_action(state, payload, event_library):
    _erase_lines(get_current_board(state), payload["x"], payload["y"])


def set_temporary_ui_connections(state, payload, event_library):
    state.temporary_connections = payload.get("connections")


def set_space_positions_action(state, payload, event_library):
    space_indices = payload["spaceIndices"]
    coords = payload["coords"]
    current_board = get_current_board(state)
    for i in range(len(space_indices)):
        space = current_board["spaces"][space_indices[i]]
        coord_set = coords[i]
        if _is_number(coord_set.get("x")):
            space["x"] = coord_set["x"]
        if _is_number(coord_set.get("y")):
            space["y"] = coord_set["y"]
        if _is_number(coord_set.get("z")):
            space["z"] = coord_set["z"]


def set_space_type_action(state, payload, event_library):
    space_indices = payload["spaceIndices"]
    space_type = payload.get("type")
    subtype = payload.get("subtype")
    current_board = get_current_board(state)
    for i in range(len(space_indices)):
        space = current_board["spaces"][space_indices[i]]
        if space_type is not None:
            space["type"] = space_type
            if space.get("rotation"):
                del space["rotation"]
        if subtype is not None:
            space["subtype"] = subtype
        else:
            space.pop("subtype", None)


def set_space_subtype_action(state, payload, event_library):
    space_indices = payload["spaceIndices"]
    subtype = payload.get("subtype")
    current_board = get_current_board(state)
    for i in range(len(space_indices)):
        space = current_board["spaces"][space_indices[i]]
        if subtype is None:
            space.pop("subtype", None)
        else:
            space["subtype"] = subtype


def set_space_hosts_star_action(state, payload, event_library):
    space_indices = payload["spaceIndices"]
    hosts_star = payload.get("hostsStar")
    current_board = get_current_board(state)
    for i in range(len(space_indices)):
        space = current_board["spaces"][space_indices[i]]
        if hosts_star:
            space["star"] = True
        else:
            space.pop("star", None)


def _js_round(value):
    """Math.round: halves round up."""
    import math
    return int(math.floor(value + 0.5))


def set_space_rotation_action(state, payload, event_library):
    space_index = payload["spaceIndex"]
    angle_y_axis_deg = payload["angleYAxisDeg"]
    assert_not_rom_board(state)

    board = get_current_board(state)
    space = (board["spaces"][space_index]
             if isinstance(space_index, int) and 0 <= space_index < len(board["spaces"])
             else None)
    if not space:
        raise ValueError("setSpaceRotation: Invalid space index " + str(space_index))
    space["rotation"] = _js_round(angle_y_axis_deg)


def add_selected_space_action(state, payload, event_library):
    state.selected_space_indices[int(payload)] = True


def set_selected_space_action(state, payload, event_library):
    state.selected_space_indices = {int(payload): True}


def set_selected_spaces_action(state, payload, event_library):
    state.selected_space_indices = {int(index): True for index in payload}


def clear_selected_spaces_action(state, payload, event_library):
    state.selected_space_indices = {}


def set_highlighted_spaces_action(state, payload, event_library):
    state.highlighted_space_indices = payload.get("spaceIndices")


def set_selection_box_coords_action(state, payload, event_library):
    state.selection_box_coords = payload.get("selectionCoords")


def change_current_event_action(state, payload, event_library):
    state.current_event_id = payload.get("id")
    state.current_event_type = EventType(payload.get("type") or 0)


def set_hovered_board_event_index_action(state, payload, event_library):
    state.hovered_board_event_index = payload["eventIndex"]


def add_event_to_board_action(state, payload, event_library):
    event = payload["event"]
    board = get_current_board(state)
    if not board.get("boardevents"):
        board["boardevents"] = []

    board["boardevents"].append(event)

    if event.get("custom"):
        custom_event = get_event(state, event["id"], board, event_library)
        _boards_lib().include_event_in_board_internal(board, custom_event)


def remove_event_from_board_action(state, payload, event_library):
    remove_event_from_board(get_current_board(state), payload["eventIndex"])


def include_event_in_board_action(state, payload, event_library):
    board = get_current_board(state)
    _boards_lib().include_event_in_board_internal(board, payload["event"])


def exclude_event_from_board_action(state, payload, event_library):
    exclude_event_from_board(get_current_board(state), payload["eventId"])


def set_board_event_activation_type_action(state, payload, event_library):
    board = get_current_board(state)
    event_instance = board["boardevents"][payload["eventIndex"]]
    event_instance["activationType"] = payload["activationType"]


def set_board_event_event_parameter_action(state, payload, event_library):
    board = get_current_board(state)
    event_instance = board["boardevents"][payload["eventIndex"]]
    if not event_instance.get("parameterValues"):
        event_instance["parameterValues"] = {}
    event_instance["parameterValues"][payload["name"]] = payload.get("value")


def add_event_to_space_action(state, payload, event_library):
    board = get_current_board(state)
    selected_space = get_current_single_selected_space(state, payload)
    _boards_lib().add_event_to_space_internal(board, selected_space, payload["event"],
                                              bool(payload.get("toStart")), event_library)


def add_event_to_spaces_action(state, payload, event_library):
    board = get_current_board(state)
    for space_index in payload["spaceIndices"]:
        space = board["spaces"][space_index]
        # The TypeScript shared one (frozen) object; each space gets a copy here.
        _boards_lib().add_event_to_space_internal(board, space, copy_object(payload["event"]),
                                                  False, event_library)


def remove_event_from_space_action(state, payload, event_library):
    selected_space = get_current_single_selected_space(state, payload)
    remove_event_from_space(selected_space, payload["eventIndex"])


def remove_events_from_spaces_action(state, payload, event_library):
    event_indices = payload["eventIndices"]
    space_indices = payload["spaceIndices"]
    assert_(len(event_indices) == len(space_indices))
    board = get_current_board(state)
    for i in range(len(event_indices)):
        space = board["spaces"][space_indices[i]]
        remove_event_from_space(space, event_indices[i])


def set_space_event_activation_type_action(state, payload, event_library):
    selected_space = get_current_single_selected_space(state, payload)
    event_instance = selected_space["events"][payload["eventIndex"]]
    event_instance["activationType"] = payload["activationType"]


def set_space_events_activation_type_action(state, payload, event_library):
    space_indices = payload["spaceIndices"]
    event_indices = payload["eventIndices"]
    board = get_current_board(state)
    for i in range(len(event_indices)):
        space = board["spaces"][space_indices[i]]
        event_instance = space["events"][event_indices[i]]
        event_instance["activationType"] = payload["activationType"]


def set_space_event_event_parameter_action(state, payload, event_library):
    selected_space = get_current_single_selected_space(state, payload)
    event_instance = selected_space["events"][payload["eventIndex"]]
    if not event_instance.get("parameterValues"):
        event_instance["parameterValues"] = {}
    event_instance["parameterValues"][payload["name"]] = payload.get("value")


def set_space_events_event_parameter_action(state, payload, event_library):
    space_indices = payload["spaceIndices"]
    event_indices = payload["eventIndices"]
    board = get_current_board(state)
    for i in range(len(event_indices)):
        space = board["spaces"][space_indices[i]]
        event_instance = space["events"][event_indices[i]]
        if not event_instance.get("parameterValues"):
            event_instance["parameterValues"] = {}
        event_instance["parameterValues"][payload["name"]] = payload.get("value")


# The library's reducers (addEventToLibraryAction, removeEventFromLibraryAction)
# change the event library, which the store keeps outside this state.


# Selectors


def select_current_board(state):
    if state.current_board_is_rom:
        return state.rom_boards[state.current_board_index]
    return state.boards[state.current_board_index]


def select_current_event(state, event_library):
    if state.current_event_type == EventType.Board:
        assert_(bool(state.current_event_id))
        board_event = _boards_lib().get_board_event(select_current_board(state),
                                                    state.current_event_id)
        from ..lib.events.customevents import create_custom_event
        return create_custom_event(board_event["language"], board_event["code"])
    if state.current_event_type == EventType.Library:
        assert_(bool(state.current_event_id))
        return event_library.get(state.current_event_id)
    return None


# Helpers


def remove_space(state, board, index, event_library):
    """Removes a space, its connections and references; returns whether it existed."""
    if not isinstance(index, int) or index < 0 or index >= len(board["spaces"]):
        return False

    # Remove any attached connections.
    _remove_connections(index, board)
    _remove_associations(index, board, event_library)

    # Remove the actual space.
    old_space_len = len(board["spaces"])
    del board["spaces"][index]

    def _adjust(old_idx):
        return old_idx - 1 if int(old_idx) > int(index) else old_idx

    # Update the links that are at a greater index.
    links = board.get("links")
    if links is not None:
        for i in range(old_space_len):
            key = str(i)
            if key not in links:
                continue

            start = _adjust(i)
            end = links[key]
            if start != i:
                del links[key]
            if isinstance(end, list):
                links[str(start)] = [_adjust(e) for e in end]
            else:
                links[str(start)] = _adjust(end)

    # Update space event parameter indices
    def _update(parameter, event, *rest):
        ptype = parameter.get("type")
        values = event.get("parameterValues")
        if ptype == EventParameterType.Space:
            if values and parameter["name"] in values:
                values[parameter["name"]] = _adjust_value(values[parameter["name"]], _adjust)
        elif ptype == EventParameterType.SpaceArray:
            value = values.get(parameter["name"]) if values else None
            if values and isinstance(value, list):
                values[parameter["name"]] = [_adjust_value(v, _adjust) for v in value]

    _boards_lib().for_each_event_parameter(board, event_library, _update)

    return True


def _adjust_value(value, adjust):
    """_adjust for a parameter value, which may not be a number (JS coerced it)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            number = int(value)
        except (TypeError, ValueError):
            return value
        return adjust(number) if adjust(number) != number else value
    return adjust(value)


def _remove_connections(space_idx, board):
    """Removes all connections to a certain space."""
    links = board.get("links")
    if not links:
        return

    links.pop(str(space_idx), None)
    for start_space in list(links.keys()):
        value = links[start_space]
        if isinstance(value, list):
            if space_idx in value:
                value.remove(space_idx)
            if len(value) == 1:
                links[start_space] = value[0]
            elif not value:
                del links[start_space]
        elif value == space_idx:
            del links[start_space]


def _erase_lines(board, x, y):
    from .jsjson import js_ordered_items
    spaces = board["spaces"]
    links = board.get("links") or {}
    something_erased = False
    for start_idx, _ in js_ordered_items(links):
        if start_idx not in links:
            continue
        start_space = spaces[int(start_idx)]
        end_links = links[start_idx]
        if isinstance(end_links, list):
            i = 0
            while i < len(end_links):
                end_space = spaces[end_links[i]]
                if _should_erase_line(start_space, end_space, x, y):
                    del end_links[i]
                    something_erased = True
                else:
                    i += 1
            if len(end_links) == 1:
                links[start_idx] = end_links[0]
            elif not end_links:
                del links[start_idx]
        else:
            end_space = spaces[end_links]
            if _should_erase_line(start_space, end_space, x, y):
                del links[start_idx]
                something_erased = True
    return something_erased


def _should_erase_line(start_space, end_space, target_x, target_y):
    if target_x > start_space["x"] and target_x > end_space["x"]:
        return False
    if target_x < start_space["x"] and target_x < end_space["x"]:
        return False
    if target_y > start_space["y"] and target_y > end_space["y"]:
        return False
    if target_y < start_space["y"] and target_y < end_space["y"]:
        return False
    try:
        return line_distance(target_x, target_y, start_space["x"], start_space["y"],
                             end_space["x"], end_space["y"]) <= 4
    except ZeroDivisionError:
        return False  # NaN or Infinity in JavaScript


def _remove_associations(space_idx, board, event_library):
    def _update(parameter, event, *rest):
        ptype = parameter.get("type")
        values = event.get("parameterValues")
        if ptype == EventParameterType.Space:
            if values and parameter["name"] in values:
                if values[parameter["name"]] == space_idx and not isinstance(
                        values[parameter["name"]], bool):
                    del values[parameter["name"]]
        elif ptype == EventParameterType.SpaceArray:
            value = values.get(parameter["name"]) if values else None
            if values and isinstance(value, list):
                values[parameter["name"]] = [s for s in value
                                             if not (s == space_idx and not isinstance(s, bool))]

    _boards_lib().for_each_event_parameter(board, event_library, _update)


def get_current_board(state):
    if state.current_board_is_rom:
        return state.rom_boards[state.current_board_index]
    return state.boards[state.current_board_index]


def get_current_single_selected_space(state, payload=None):
    """The space a single-space reducer works on: payload["spaceIndex"], or the selection."""
    board = get_current_board(state)
    if isinstance(payload, dict) and payload.get("spaceIndex") is not None:
        space_index = payload["spaceIndex"]
    else:
        selected = [int(k) for k in state.selected_space_indices]
        assert_(len(selected) == 1)
        space_index = selected[0]
    space = (board["spaces"][space_index]
             if isinstance(space_index, int) and 0 <= space_index < len(board["spaces"])
             else None)
    assert_(bool(space))
    return space


def remove_event_from_board(board, event_index):
    """Removes an event from `boardevents`."""
    if board.get("boardevents"):
        if event_index >= 0:
            del board["boardevents"][event_index:event_index + 1]


def exclude_event_from_board(board, event_id):
    """Removes an event from the collection of events stored in the board file."""
    if board.get("events"):
        board["events"].pop(event_id, None)

    def _remove(event, event_index, space=None, space_index=None):
        if event.get("id") == event_id:
            if space:
                remove_event_from_space(space, event_index)
            else:
                remove_event_from_board(board, event_index)

    _boards_lib().for_each_event(board, _remove)


def remove_event_from_space(space, event_index):
    if not space or not space.get("events"):
        return

    if event_index >= 0:
        del space["events"][event_index:event_index + 1]


def get_event(state, event_id, board, event_library):
    """Gets an event, either from the board's set or the global library."""
    lib = _boards_lib()
    if board and board.get("events") and lib.get_board_event(board, event_id):
        board_event = lib.get_board_event(board, event_id)
        from ..lib.events.customevents import create_custom_event
        return create_custom_event(board_event["language"], board_event["code"])
    return event_library.get(event_id)


def assert_not_rom_board(state):
    if state.current_board_is_rom:
        raise ValueError("Current board must not be a ROM board.")


# The reducers by Redux action type (the name in boardState.ts).

REDUCERS = {
    "setBoardsAction": set_boards_action,
    "addBoardAction": add_board_action,
    "deleteBoardAction": delete_board_action,
    "setCurrentBoardAction": set_current_board_action,
    "clearBoardsFromROMAction": clear_boards_from_rom_action,
    "copyCurrentBoardAction": copy_current_board_action,
    "setBoardNameAction": set_board_name_action,
    "setBoardDescriptionAction": set_board_description_action,
    "setBoardDifficultyAction": set_board_difficulty_action,
    "setBoardCostumeTypeIndexAction": set_board_costume_type_index_action,
    "setBackgroundAction": set_background_action,
    "setBoardOtherBgAction": set_board_other_bg_action,
    "addAnimationBackgroundAction": add_animation_background_action,
    "removeAnimationBackgroundAction": remove_animation_background_action,
    "addAdditionalBackgroundAction": add_additional_background_action,
    "removeAdditionalBackgroundAction": remove_additional_background_action,
    "setAdditionalBackgroundCodeAction": set_additional_background_code_action,
    "setAudioSelectCodeAction": set_audio_select_code_action,
    "setBoardAudioAction": set_board_audio_action,

    "addConnectionAction": add_connection_action,
    "eraseConnectionsAction": erase_connections_action,
    "setTemporaryUIConnections": set_temporary_ui_connections,

    "addSpaceAction": add_space_action,
    "removeSpaceAction": remove_space_action,
    "removeSpacesAction": remove_spaces_action,
    "setSpacePositionsAction": set_space_positions_action,
    "setSpaceTypeAction": set_space_type_action,
    "setSpaceSubtypeAction": set_space_subtype_action,
    "setSpaceHostsStarAction": set_space_hosts_star_action,
    "setSpaceRotationAction": set_space_rotation_action,

    "addSelectedSpaceAction": add_selected_space_action,
    "setSelectedSpaceAction": set_selected_space_action,
    "setSelectedSpacesAction": set_selected_spaces_action,
    "clearSelectedSpacesAction": clear_selected_spaces_action,

    "setHighlightedSpacesAction": set_highlighted_spaces_action,

    "setSelectionBoxCoordsAction": set_selection_box_coords_action,

    "changeCurrentEventAction": change_current_event_action,
    "addEventToBoardAction": add_event_to_board_action,
    "removeEventFromBoardAction": remove_event_from_board_action,
    "includeEventInBoardAction": include_event_in_board_action,
    "excludeEventFromBoardAction": exclude_event_from_board_action,
    "setHoveredBoardEventIndexAction": set_hovered_board_event_index_action,
    "setBoardEventActivationTypeAction": set_board_event_activation_type_action,
    "setBoardEventEventParameterAction": set_board_event_event_parameter_action,

    "addEventToSpaceAction": add_event_to_space_action,
    "addEventToSpacesAction": add_event_to_spaces_action,
    "removeEventFromSpaceAction": remove_event_from_space_action,
    "removeEventsFromSpacesAction": remove_events_from_spaces_action,
    "setSpaceEventActivationTypeAction": set_space_event_activation_type_action,
    "setSpaceEventsActivationTypeAction": set_space_events_activation_type_action,
    "setSpaceEventEventParameterAction": set_space_event_event_parameter_action,
    "setSpaceEventsEventParameterAction": set_space_events_event_parameter_action,
}

# Reducers that only change UI state (no board, no board list).
UI_ACTIONS = {
    "setTemporaryUIConnections", "addSelectedSpaceAction", "setSelectedSpaceAction",
    "setSelectedSpacesAction", "clearSelectedSpacesAction", "setHighlightedSpacesAction",
    "setSelectionBoxCoordsAction", "changeCurrentEventAction", "setHoveredBoardEventIndexAction",
}

# Reducers that change the board list or which board is current (not its content).
LIST_ACTIONS = {
    "setBoardsAction", "addBoardAction", "deleteBoardAction", "setCurrentBoardAction",
    "clearBoardsFromROMAction", "copyCurrentBoardAction",
}

# The event library's reducers; the store routes these to the library.
LIBRARY_ACTIONS = {"addEventToLibraryAction", "removeEventFromLibraryAction"}
