"""Board ops from the API: JSON payloads made ready for the reducers.

POST /api/board/op {op, args} names a reducer of boardState.ts; its args are
JSON. Images may come back as image-cache URLs (turned into data URLs here),
and events as JSON (turned into event objects).
"""

from . import board_state as bs
from . import images
from .store import normalize_action_type, store


def _event_from_json(data, what="event"):
    """An event object from {language, asm|code} JSON (or an event object)."""
    if not isinstance(data, dict):
        if hasattr(data, "asm"):
            return data
        raise ValueError("The %s must be an object." % what)
    from ..lib.events.customevents import create_custom_event
    code = data.get("asm") if data.get("asm") is not None else data.get("code")
    if not code:
        raise ValueError("The %s has no code." % what)
    return create_custom_event(data.get("language") or 0, code)


def prepare(op, args):
    """Return (action type, payload) for an op of the API."""
    action_type = normalize_action_type(op)
    payload = images.internalize(args) if args is not None else {}
    if action_type == "includeEventInBoardAction":
        if isinstance(payload, dict) and "event" not in payload and payload.get("eventId"):
            event = store.event_library.get(payload["eventId"])
            if event is None or not getattr(event, "custom", False):
                raise ValueError("There is no custom event %s in the library."
                                 % payload["eventId"])
            payload = dict(payload, event=event)
        else:
            payload = dict(payload, event=_event_from_json(payload.get("event")))
    elif action_type == "addEventToLibraryAction":
        payload = dict(payload, event=_event_from_json(payload.get("event")))
    elif action_type in ("addBoardAction", "setBoardsAction"):
        from .boards import _fix_potentially_old_board
        if action_type == "addBoardAction":
            board = payload.get("board")
            if not isinstance(board, dict):
                raise ValueError("No board given.")
            if payload.get("rom"):
                board["_rom"] = True
            payload = dict(payload, board=_fix_potentially_old_board(board))
        else:
            boards = payload.get("boards")
            if not isinstance(boards, list) or not boards:
                raise ValueError("No boards given.")
            payload = dict(payload, boards=[_fix_potentially_old_board(b) for b in boards])
    elif action_type == "changeCurrentEventAction" and isinstance(payload, dict):
        payload = dict(payload, type=int(payload.get("type") or bs.EventType.None_))
    return action_type, payload


def apply(ops):
    """Apply [(op, args), ...] as one undo step. Raises ValueError (and others) on failure."""
    actions = [prepare(op, args) for op, args in ops]
    from .boards import current_board_changed
    with store.lock:
        before = (store.state.current_board_index, store.state.current_board_is_rom)
        store.dispatch_many(actions, check_current=True)
        after = (store.state.current_board_index, store.state.current_board_is_rom)
        if before != after or any(t in ("setBoardsAction", "deleteBoardAction")
                                  for t, _ in actions):
            current_board_changed()
