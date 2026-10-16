"""The event library: list, create, import, export, delete and test events (docs/API.md)."""

import copy
import logging

from ... import state
from ...editor.store import store
from ..http import ApiError, Response, route

logger = logging.getLogger("partyplanner64")


def _plain(value):
    return getattr(value, "value", value)


def event_json(event, with_code=False):
    """An event's list form: {id, name, custom, supportedGames, activationType, ...}."""
    language = getattr(event, "language", None)
    out = {
        "id": event.id,
        "name": event.name,
        "custom": bool(getattr(event, "custom", False)),
        "supportedGames": [_plain(g) for g in (getattr(event, "supported_games", None) or [])],
        "activationType": _plain(getattr(event, "activation_type", None)),
        "executionType": _plain(getattr(event, "execution_type", None)),
        "parameters": [{"name": p["name"], "type": _plain(p["type"])}
                       for p in (getattr(event, "parameters", None) or [])],
        "language": int(language) if language is not None else None,
        "fakeEvent": bool(getattr(event, "fake_event", False)),
    }
    if with_code:
        out["code"] = getattr(event, "asm", None)
    return out


def _language(value):
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if value not in (0, 1):
        raise ApiError("The language is 0 (MIPS assembly) or 1 (C).")
    return value


def _create(language, code):
    from ...lib.events.customevents import create_custom_event
    if not code or not str(code).strip():
        raise ApiError("No assembly code was provided.")
    try:
        return create_custom_event(language, code)
    except ValueError as e:
        raise ApiError(str(e))


def _validate(event):
    """The test compile's failure message, or None."""
    from ...lib.events.customevents import validate_custom_event
    try:
        validate_custom_event(event)
    except Exception as e:  # noqa: BLE001 - shown to the user
        return str(e) or type(e).__name__
    return None


def _check_name(event):
    existing = store.event_library.get(event.id)
    if existing is not None and not getattr(existing, "custom", False):
        raise ApiError("The event name collides with a reserved event name from the "
                       "original boards.")


def _board_events():
    from ...lib import boards as lib_boards
    from ...lib.events.customevents import create_custom_event
    out = []
    with state.lock:
        board = state.current_board()
        names = list((board.get("events") or {}).keys())
        for name in names:
            board_event = lib_boards.get_board_event(board, name)
            if not board_event:
                continue
            library_event = store.event_library.get(name)
            try:
                entry = event_json(create_custom_event(board_event["language"],
                                                       board_event["code"]))
                entry["error"] = None
            except Exception as e:  # noqa: BLE001
                entry = {"id": name, "name": name, "custom": True, "supportedGames": [],
                         "activationType": None, "executionType": None, "parameters": [],
                         "language": board_event.get("language"), "error": str(e)}
            entry["inLibrary"] = library_event is not None
            entry["differs"] = (library_event is not None
                                and getattr(library_event, "asm", None) != board_event["code"])
            out.append(entry)
    return out


@route("GET", "/api/events")
def list_events(req):
    with state.lock:
        events = [event_json(e) for e in list(store.event_library.values())]
    return {"events": events, "boardEvents": _board_events()}


@route("GET", "/api/events/<id>")
def get_event(req, id):
    event = store.event_library.get(id)
    if event is None:
        raise ApiError("There is no event %s." % id, 404)
    return event_json(event, with_code=True)


@route("POST", "/api/events")
def save_event(req):
    """createevent_shared.tsx saveEvent()."""
    language = _language(req.arg("language", 0))
    code = req.arg("code")
    event = _create(language, code)
    with state.lock:
        _check_name(event)
    if not event.supported_games:
        raise ApiError("At least one game must be supported.")
    warning = _validate(event)
    try:
        if req.arg("board"):
            store.dispatch("includeEventInBoardAction", {"event": event})
        else:
            store.dispatch("addEventToLibraryAction", {"event": event})  # Add globally.
    except (ValueError, IndexError) as e:
        raise ApiError(str(e))
    return {"event": event_json(event, with_code=True), "warning": warning}


def _language_from_file_name(name):
    lower = (name or "").lower()
    if lower.endswith(".s"):
        return 0
    if lower.endswith(".c"):
        return 1
    raise ApiError("Only .s or .c file extensions are recongized. (Saw %s)" % name)


@route("POST", "/api/events/import")
def import_event(req):
    """header.tsx eventFileSelected()."""
    language = _language_from_file_name(req.query.get("name"))
    try:
        code = req.body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError("Event file load failed. The file is not UTF-8 text.")
    try:
        from ...lib.events.customevents import create_custom_event
        event = create_custom_event(language, code)
    except ValueError as e:
        raise ApiError("Event file load failed. %s" % e)
    with state.lock:
        _check_name(event)
    failure = _validate(event)
    if failure:
        raise ApiError("Event file load failed. %s" % failure)
    store.dispatch("addEventToLibraryAction", {"event": event})
    return {"event": event_json(event, with_code=True)}


@route("GET", "/api/events/<id>/export")
def export_event(req, id):
    event = store.event_library.get(id)
    if event is None or not getattr(event, "custom", False):
        raise ApiError("There is no custom event %s." % id, 404)
    ext = ".c" if getattr(event, "language", 0) == 1 else ".s"
    return Response(event.asm, "text/plain; charset=utf-8", filename=event.id + ext)


@route("POST", "/api/events/<id>/delete")
def delete_event(req, id):
    try:
        store.dispatch("removeEventFromLibraryAction", {"eventId": id})
    except ValueError as e:
        raise ApiError(str(e))
    return {}


@route("POST", "/api/events/<id>/copy-to-board")
def copy_to_board(req, id):
    event = store.event_library.get(id)
    if event is None or not getattr(event, "custom", False):
        raise ApiError("There is no custom event %s." % id, 404)
    try:
        store.dispatch("includeEventInBoardAction", {"event": event})
    except (ValueError, IndexError) as e:
        raise ApiError(str(e))
    return {"revision": store.revision}


@route("GET", "/api/board/events/<id>")
def get_board_event(req, id):
    from ...lib import boards as lib_boards
    with state.lock:
        board_event = lib_boards.get_board_event(state.current_board(), id)
    if not board_event:
        raise ApiError("The board has no event %s." % id, 404)
    event = _create(board_event["language"], board_event["code"])
    return event_json(event, with_code=True)


@route("POST", "/api/board/events/<id>/copy-to-library")
def copy_to_library(req, id):
    from ...lib import boards as lib_boards
    with state.lock:
        board_event = lib_boards.get_board_event(state.current_board(), id)
    if not board_event:
        raise ApiError("The board has no event %s." % id, 404)
    event = _create(board_event["language"], board_event["code"])
    with state.lock:
        _check_name(event)
    store.dispatch("addEventToLibraryAction", {"event": event})
    return {"event": event_json(event, with_code=True)}


@route("POST", "/api/board/events/<id>/delete")
def delete_board_event(req, id):
    store.dispatch("excludeEventFromBoardAction", {"eventId": id})
    return {"revision": store.revision}


@route("POST", "/api/events/test")
def test_event(req):
    from ...lib.types import get_game_name
    language = _language(req.arg("language", 0))
    code = req.arg("code") or ""
    try:
        from ...lib.events.customevents import create_custom_event
        event = create_custom_event(language, code)
    except ValueError as e:
        return {"event": None, "error": str(e), "results": []}
    results = []
    for game in event.supported_games:
        single = copy.copy(event)
        single.supported_games = [game]
        failure = _validate(single)
        game_id = _plain(game)
        results.append({"game": game_id, "gameName": get_game_name(game_id),
                        "ok": failure is None, "error": failure})
    return {"event": event_json(event), "error": None, "results": results}
