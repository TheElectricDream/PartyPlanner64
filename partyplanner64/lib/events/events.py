"""Events: the IEvent shape, and parsing/writing events (events.ts).

An event (built-in or custom) is an `Event` object with snake_case
attributes: id, name, activation_type, execution_type, fake_event,
supported_games, parameters (list of {"name", "type"} dicts), custom, asm,
language, and the callables parse(data_view, info) and
write(data_view, event_instance, info, temp) (None when the event has none).

Event instances (what a board stores on a space) are plain dicts with the
camelCase keys of the board JSON: {"id", "activationType", "executionType",
"parameterValues"?, "custom"?}.

Parse/write info objects (IEventParseInfo, IEventWriteInfo) are dicts with
snake_case keys: addr, offset, board, board_index, cur_space,
cur_space_index, chains, game, game_version (parse); board_index, board,
board_info, audio_indices, cur_space_index, cur_space, chains, offset, addr,
game, game_version, args_addr, test_compile (write).
"""

from ..types import Game
from ..utils.dataview import DataView
from ..utils.obj import copy_object
from .event_library import get_event_from_library, get_events_in_library


class Event:
    """An IEvent. Partial events (helpers holding only parse/write) are
    instances too, with the other attributes left None."""

    def __init__(self, id=None, name=None, activation_type=None, execution_type=None,
                 supported_games=None, parameters=None, fake_event=False, custom=False,
                 language=None, asm=None, parse=None, write=None):
        self.id = id
        self.name = name
        self.activation_type = activation_type
        self.execution_type = execution_type
        self.supported_games = list(supported_games) if supported_games is not None else []
        self.parameters = parameters
        self.fake_event = fake_event
        self.custom = custom
        self.language = language
        self.asm = asm
        self.parse = parse
        self.write = write

    def to_json(self):
        """The camelCase JSON form the TypeScript saved (functions omitted)."""
        def plain(v):
            return v.value if hasattr(v, "value") else v

        out = {"id": self.id, "name": self.name}
        if self.custom:
            out["custom"] = True
        if self.language is not None:
            out["language"] = int(self.language)
        if self.asm is not None:
            out["asm"] = self.asm
        if self.activation_type is not None:
            out["activationType"] = int(self.activation_type)
        if self.execution_type is not None:
            out["executionType"] = int(self.execution_type)
        if self.parameters is not None and not self.custom:
            out["parameters"] = [{"name": p["name"], "type": plain(p["type"])}
                                 for p in self.parameters]
        if self.fake_event:
            out["fakeEvent"] = True
        out["supportedGames"] = [plain(g) for g in self.supported_games]
        if self.parameters is not None and self.custom:
            out["parameters"] = [{"name": p["name"], "type": plain(p["type"])}
                                 for p in self.parameters]
        return out

    def copy(self):
        """A copy of the event (copyObject in the TypeScript, which drops the functions)."""
        e = Event(self.id, self.name, self.activation_type, self.execution_type,
                  self.supported_games, copy_object(self.parameters), self.fake_event,
                  self.custom, self.language, self.asm)
        return e

    def __repr__(self):
        return "<Event %s>" % (self.id,)


def _supported_games_match(supported_games, game_version):
    for game in supported_games:
        if game in (Game.MP1_USA, Game.MP1_JPN, Game.MP1_PAL):
            if game_version == 1:
                return True
        elif game in (Game.MP2_USA, Game.MP2_JPN, Game.MP2_PAL):
            if game_version == 2:
                return True
        elif game in (Game.MP3_USA, Game.MP3_JPN, Game.MP3_PAL):
            if game_version == 3:
                return True
    return False


def get_event(event_id, board, event_library):
    """Gets an event, either from the board's set or the global library."""
    from ..boards import get_board_event
    from .customevents import create_custom_event

    if board and board.get("events") and get_board_event(board, event_id):
        board_event = get_board_event(board, event_id)
        return create_custom_event(board_event["language"], board_event["code"])
    return event_library.get(event_id)


def create_event_instance(event, args=None):
    """Creates an event instance (the object stored in the board json for a given event)."""
    space_event = {
        "id": event.id,
        "activationType": int(event.activation_type),
        "executionType": int(event.execution_type),
    }
    if args:
        space_event.update(args)
    if event.custom:
        space_event["custom"] = True

    return space_event


def parse(rom_view, info):
    """Tries every library event's parse on the code at info["offset"].

    Returns False, True (a fake event matched), or {"id": ..., "args"?: ...}.
    """
    from ..romhandler import romhandler

    current_game = romhandler.get_rom_game()
    _events = get_events_in_library()
    for event_id in list(_events):
        event = _events[event_id]
        if not event.parse:
            continue
        if current_game not in event.supported_games:
            continue
        args = event.parse(rom_view, info)
        if args:
            if event.fake_event:
                return True
            result = {"id": event_id}
            if args is not True:
                result["args"] = args
            return result
    return False


def get_available_events(board):
    """The non-fake library events that support the board's game."""
    events = []
    _events = get_events_in_library()
    cur_game_version = board.get("game") or 1
    for id in list(_events):
        event = _events[id]
        if _supported_games_match(event.supported_games, cur_game_version) and not event.fake_event:
            events.append(event)
    return events


def get_custom_events():
    """Copies of the custom events in the library."""
    events = []
    _events = get_events_in_library()
    for id in list(_events):
        event = _events[id]
        if event.custom:
            events.append(event.copy())
    return events


def write(buffer, event, info, temp):
    """Writes an event instance's code; returns what the event's write gave
    (normally assembly text)."""
    from ..boards import get_board_event
    from .customevents import write_custom_event

    asm_view = DataView(buffer, info.get("offset") or 0)

    if event.get("custom"):
        board_event = get_board_event(info["board"], event["id"])
        if not board_event:
            raise ValueError(
                f"A space had the {event['id']} custom event, but its code wasn't in the board file")
        result = write_custom_event(asm_view, event, info, board_event["language"],
                                    board_event["code"], temp)
    else:
        lib_event = get_event_from_library(event["id"])
        if not lib_event:
            raise ValueError(
                f"Could not find/write {event['id']} for game {info.get('game_version')}")
        result = lib_event.write(asm_view, event, info, temp)

    if result is False:
        raise ValueError(f"Could not write {event['id']} for game {info.get('game_version')}")

    return result


def is_unsupported(event, game_id):
    return game_id not in event.supported_games
