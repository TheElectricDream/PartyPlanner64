"""The app's state: the open ROM, the boards, the event library and settings.

The browser held all this in the TypeScript app; the server holds it here, for
every open page. Boards, custom events and settings are kept in the data
folder (default ~/.partyplanner64) as the browser kept them in localStorage
and cookies:

- boards.json: your boards (localStorage "boards": a JSON list of boards);
- events.json: your custom events (localStorage "events": a list of
  {id, name, custom, language, asm, activationType, executionType,
  supportedGames, parameters});
- settings.json: {setting id: value}.

Files are written atomically, a moment after a change (and at exit).
Everything is guarded by `lock` (an RLock shared with the editor store), so
the threaded server may call these functions from any thread; route modules
that use the ROM should hold it too:

    from partyplanner64 import state
    with state.lock:
        rom = state.require_rom()       # ApiError (409) if no ROM is open
"""

import atexit
import copy
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

from . import __version__
from .editor import board_state as bs
from .editor import boards as editor_boards
from .editor import images, jsjson
from .editor.store import store

logger = logging.getLogger("partyplanner64")

lock = store.lock

SAVE_DELAY = 1.0                    # [s] after a change, before the files are written

# Settings (views/settings.tsx): (section, id, type, default, name, description, advanced)
SETTINGS_SCHEMA = [
    ("Theme", "ui.theme", "theme", "classic", "Theme", "", False),
    ("UI", "ui.advanced", "checkbox", False, "Advanced features",
     "Enables infrequently used, potentially complicated, and developer features.", False),
    ("UI", "ui.debug", "checkbox", False, "Debug features",
     "Enables debug output and UI that may aid development.", True),
    ("UI", "ui.skipvalidation", "checkbox", False, "Skip Overwrite Validation",
     "Allow boards to be written regardless of warnings.", True),
    ("UI", "ui.showromboards", "checkbox", True, "Show ROM Boards",
     "Show boards parsed from the ROM in the editor.", False),
    ("UI", "ui.allowallroms", "checkbox", False, "Allow All ROMs",
     "Allows more than just the officially supported ROMs to attempt to load.", True),
    ("ROM", "write.branding", "checkbox", True, "Include branding",
     "Adds the PartyPlanner64 logo to the game boot splashscreens.", False),
    ("ROM", "write.decompressed", "checkbox", False, "Leave ROM decompressed",
     "Leaves all files decompressed when saving a ROM, resulting in larger file size.", True),
    ("Model Viewer", "models.limitfps", "checkbox", True, "Limit FPS",
     "Reduce the refresh rate for better performance.", False),
    ("Model Viewer", "models.limitAnimations", "checkbox", True, "Limit animations",
     "Limit animations to those in the same directory as the model.", False),
    ("Model Viewer", "models.useGLB", "checkbox", False, "Use GLB container for glTF",
     "Create a GLB container when exporting models to glTF.", False),
]
THEMES = [("classic", "Classic"), ("dark-gray", "Dark Gray")]      # EditorThemes
SETTING_DEFAULTS = {s[1]: s[3] for s in SETTINGS_SCHEMA}

GAME_TITLES = {
    "CLBE": "Mario Party (U)", "CLBJ": "Mario Party (J)", "NLBP": "Mario Party (E)",
    "NMWE": "Mario Party 2 (U)", "NMWJ": "Mario Party 2 (J)", "NMWP": "Mario Party 2 (E)",
    "NMVE": "Mario Party 3 (U)", "NMVJ": "Mario Party 3 (J)", "NMVP": "Mario Party 3 (E)",
}


def _api_error(message, status=400):
    from .server.http import ApiError
    return ApiError(message, status)


def _publish(kind, data=None):
    try:
        from .server.http import hub
    except ImportError:          # pragma: no cover
        return
    hub.publish(kind, data)


class _Saver:
    """Writes files a moment after they change (debounced), atomically."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending = {}           # path -> producer (returns the text)
        self._timer = None
        self.delay = SAVE_DELAY

    def schedule(self, path, producer):
        with self._lock:
            self._pending[path] = producer
            if self._timer is None:
                self._timer = threading.Timer(self.delay, self.flush)
                self._timer.daemon = True
                self._timer.start()

    def flush(self):
        """Write everything pending now."""
        with self._lock:
            pending, self._pending = self._pending, {}
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        for path, producer in pending.items():
            try:
                write_atomic(path, producer())
            except Exception:  # noqa: BLE001 - keep the server going
                logger.exception("Could not save %s", path)


def write_atomic(path, text):
    """Write a text file so that it is either the old or the new file, never half."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class _AppState:
    def __init__(self):
        self.data_dir = None
        self.configured = False
        self.settings = {}           # saved values (only ids that were set)
        self.session = {}            # session-only values (--debug)
        self.rom_file_name = None
        self.saver = _Saver()
        self.unsubscribe = None
        self.loading = False         # no saving while the saved files are read


_app = _AppState()


# Set-up


def default_data_dir():
    return Path(os.environ.get("PARTYPLANNER64_DATA") or Path.home() / ".partyplanner64")


def configure(data_dir=None, debug=False):
    """Start the app's state: read the data folder (boards, events, settings).

    Args:
        data_dir: The data folder (default ~/.partyplanner64, or $PARTYPLANNER64_DATA).
        debug: Turn the debug features on for this session.
    """
    with lock:
        if _app.unsubscribe:
            _app.unsubscribe()
            _app.unsubscribe = None
        _app.saver.flush()
        _app.data_dir = Path(data_dir).expanduser() if data_dir else default_data_dir()
        _app.settings = _read_settings()
        _app.session = {"ui.debug": True} if debug else {}
        _app.rom_file_name = None
        _apply_debug()
        _initialize_state()
        _app.unsubscribe = store.subscribe(_on_store_change)
        _app.configured = True


def shutdown():
    """Write anything not yet saved."""
    _app.saver.flush()


atexit.register(shutdown)


def data_path(name):
    """A file in the data folder."""
    if _app.data_dir is None:
        _app.data_dir = default_data_dir()
    return _app.data_dir / name


def _read_json_file(name):
    path = data_path(name)
    if not path.is_file():
        return None
    try:
        return jsjson.parse(path.read_bytes())
    except (ValueError, OSError) as e:
        backup = path.with_name("%s.bad-%d" % (path.name, int(time.time())))
        logger.error("Could not read %s (%s); it was moved to %s", path, e, backup.name)
        try:
            os.replace(path, backup)
        except OSError:
            pass
        return None


def _load_builtin_events():
    """Import the built-in events (events.include.ts registered them on import)."""
    import importlib
    for name in ("partyplanner64.lib.events.builtin.events_include",
                 "partyplanner64.lib.events.builtin"):
        try:
            importlib.import_module(name)
        except ImportError as e:
            logger.debug("No built-in events from %s: %s", name, e)


def _initialize_state():
    """app.tsx initializeState(): the event library, saved boards and events."""
    from .lib.events.customevents import create_custom_event
    from .lib.events.event_library import set_event_library_implementation
    from .lib.types import EventCodeLanguage
    from .editor.events.redux_event_library import ReduxEventLibrary

    from .lib.events.event_library import get_events_in_library

    _app.loading = True
    try:
        _load_builtin_events()
        builtin = [e for e in get_events_in_library().values() if not e.custom]
        store.reset()
        set_event_library_implementation(ReduxEventLibrary(store))
        for event in builtin:
            store.event_library.setdefault(event.id, event)

        boards = None
        cached_boards = _read_json_file("boards.json")
        if isinstance(cached_boards, list) and cached_boards:
            boards = []
            for board in cached_boards:
                try:
                    boards.append(editor_boards._fix_potentially_old_board(board))
                except Exception as e:  # noqa: BLE001
                    logger.error("Skipping a saved board that can't be read: %s", e)
        if not boards:
            boards = [editor_boards._make_default_board(1)]
        store.dispatch("setBoardsAction", {"boards": boards})

        cached_events = _read_json_file("events.json")
        if isinstance(cached_events, list):
            for event_obj in cached_events:
                if not isinstance(event_obj, dict) or not event_obj.get("asm"):
                    continue
                try:
                    custom_event = create_custom_event(
                        event_obj.get("language") or EventCodeLanguage.MIPS, event_obj["asm"])
                    store.dispatch("addEventToLibraryAction", {"event": custom_event})
                except Exception as e:  # noqa: BLE001
                    # Just let the error slide, event format changed or something?
                    logger.error("Error reading cached event: %s", e)

        store.clear_history()
    finally:
        _app.loading = False


def _on_store_change(changes):
    """Save and tell the pages what changed."""
    if _app.loading:
        return
    if changes & {"board", "boards"}:
        _app.saver.schedule(data_path("boards.json"), _boards_file_text)
    if "events" in changes:
        _app.saver.schedule(data_path("events.json"), _events_file_text)
        _publish("events", None)
    if changes & {"boards"}:
        _publish("boards", {"revision": store.revision, "current": current_ref()})
    if changes & {"board", "history"}:
        _publish("board", {"revision": store.revision, "canUndo": store.can_undo,
                           "canRedo": store.can_redo})


def _boards_file_text():
    with lock:
        boards = list(store.state.boards)      # states never change: safe outside the lock
    return jsjson.stringify(boards)


def _events_file_text():
    with lock:
        events = [e for e in store.event_library.values() if e.custom]
    return jsjson.stringify([e.to_json() for e in events])


def save_now():
    """Write boards, events and settings now (tests, shutdown)."""
    _app.saver.schedule(data_path("boards.json"), _boards_file_text)
    _app.saver.schedule(data_path("events.json"), _events_file_text)
    _app.saver.flush()


# Settings


def _read_settings():
    data = _read_json_file("settings.json")
    if not isinstance(data, dict):
        return {}
    settings = {}
    for key, value in data.items():
        try:
            settings[key] = _check_setting(key, value)
        except ValueError:
            pass
    return settings


def _check_setting(setting_id, value):
    if setting_id not in SETTING_DEFAULTS:
        raise ValueError("Unknown setting: %s" % setting_id)
    if setting_id == "ui.theme":
        if value not in [t[0] for t in THEMES]:
            raise ValueError("Unknown theme: %s" % (value,))
        return value
    if not isinstance(value, bool):
        raise ValueError("The setting %s is on (true) or off (false)." % setting_id)
    return value


def get_setting(setting_id):
    """A setting's value (ids as the original, e.g. "ui.advanced")."""
    with lock:
        if setting_id in _app.session:
            return _app.session[setting_id]
        if setting_id in _app.settings:
            return _app.settings[setting_id]
        return SETTING_DEFAULTS.get(setting_id)


def get_settings():
    """{id: value} for every setting."""
    with lock:
        return {s[1]: get_setting(s[1]) for s in SETTINGS_SCHEMA}


def set_settings(values):
    """Change settings ({id: value}); returns all settings. ValueError for bad ones."""
    if not isinstance(values, dict):
        raise ValueError("Settings are sent as {id: value}.")
    with lock:
        checked = {k: _check_setting(k, v) for k, v in values.items()}
        for key, value in checked.items():
            _app.settings[key] = value
            _app.session.pop(key, None)
        _apply_debug()
        _save_settings()
        result = get_settings()
    _publish("settings", {"settings": result})
    return result


def reset_settings():
    """Back to the defaults (SettingsManager.reset)."""
    with lock:
        _app.settings = {}
        _app.session = {}
        _apply_debug()
        _save_settings()
        result = get_settings()
    _publish("settings", {"settings": result})
    return result


def _save_settings():
    text = jsjson.stringify(dict(_app.settings), indent=1)
    _app.saver.schedule(data_path("settings.json"), lambda: text)


def _apply_debug():
    from .lib.debug import set_debug
    set_debug(bool(get_setting("ui.debug")))


def settings_schema():
    """The settings page's sections and settings."""
    sections = []
    for section, sid, stype, default, name, desc, advanced in SETTINGS_SCHEMA:
        if not sections or sections[-1]["name"] != section:
            sections.append({"name": section, "settings": []})
        entry = {"id": sid, "type": stype, "name": name, "desc": desc, "default": default,
                 "advanced": advanced}
        if stype == "theme":
            entry["choices"] = [{"value": v, "name": n} for v, n in THEMES]
        sections[-1]["settings"].append(entry)
    return {"sections": sections}


# The ROM


def _romhandler():
    from .lib.romhandler import romhandler
    return romhandler


def rom_is_loaded():
    try:
        rh = _romhandler()
    except ImportError:
        return False
    return bool(rh.get_rom()) if hasattr(rh, "get_rom") else bool(rh.rom_is_loaded())


def require_rom():
    """The open ROM (romhandler.get_rom()); ApiError (409) if none is open."""
    if not rom_is_loaded():
        raise _api_error("No ROM is open.", 409)
    return _romhandler().get_rom()


def rom_info():
    """null, or {game, gameName, gameVersion, supported, fileName, title, shortName}."""
    with lock:
        if not rom_is_loaded():
            return None
        rh = _romhandler()
        game = rh.get_rom_game()
        game = getattr(game, "value", game)
        from .lib.types import get_game_name
        version = rh.get_game_version()
        try:
            supported = bool(rh.rom_supported())
        except Exception:  # noqa: BLE001
            supported = False
        return {
            "game": game,
            "gameName": get_game_name(game) if game else None,
            "gameVersion": int(version) if version else None,
            "supported": supported,
            "fileName": _app.rom_file_name,
            "title": GAME_TITLES.get(game, game),
            "shortName": "MP%d" % version if version else None,
        }


def open_rom_bytes(data, file_name=None):
    """Open a ROM (header.tsx romSelected) and read its boards.

    Raises ApiError (400) if the file isn't a recognized (or supported) ROM;
    `ui.allowallroms` skips the supported check.
    Returns rom_info().
    """
    if not data:
        raise _api_error("The file is empty.")
    with lock:
        if rom_is_loaded():
            _close_rom_locked(publish=False)
        rh = _romhandler()
        errors = []
        skip_supported_check = bool(get_setting("ui.allowallroms"))
        try:
            ok = rh.set_rom_buffer(bytearray(data), skip_supported_check, errors.append)
        except Exception as e:  # noqa: BLE001
            rh.clear()
            raise _api_error("Error loading the ROM file.\n\n%s" % e)
        if not ok:
            rh.clear()
            raise _api_error(errors[0] if errors else "The ROM could not be loaded.")
        _app.rom_file_name = file_name
        store.clear_history()                  # romLoadedChanged
        try:
            editor_boards.load_boards_from_rom()
        except Exception as e:  # noqa: BLE001
            logger.exception("Reading the ROM's boards failed")
            _close_rom_locked(publish=False)
            raise _api_error("Error loading the ROM file.\n\n%s" % e)
        info = rom_info()
    _publish("rom", {"rom": info})
    return info


def open_rom_file(path):
    """Open a ROM file (python -m partyplanner64 --rom)."""
    path = Path(path)
    return open_rom_bytes(path.read_bytes(), path.name)


def _close_rom_locked(publish=True):
    rh = _romhandler()
    rh.clear()
    _app.rom_file_name = None
    actions = [("clearBoardsFromROMAction", None)]
    state = store.state
    if state.current_board_is_rom or state.current_board_index != 0:
        actions.append(("setCurrentBoardAction", {"index": 0, "rom": False}))
    store.dispatch_many(actions)
    store.clear_history()                      # currentBoardChanged, romLoadedChanged


def close_rom():
    """Close the ROM (Action.ROM_UNLOAD): its boards go; board 0 becomes current."""
    with lock:
        if rom_is_loaded():
            _close_rom_locked()
        else:
            store.dispatch("clearBoardsFromROMAction")
    _publish("rom", {"rom": None})


def save_rom():
    """The ROM with everything written to it: (bytes, file name)."""
    with lock:
        require_rom()
        rh = _romhandler()
        buffer = rh.save_rom(bool(get_setting("write.decompressed")))
        return bytes(buffer), "MyMarioParty%s.z64" % rh.get_game_version()


# Boards


def current_ref():
    state = store.state
    return {"index": state.current_board_index, "rom": state.current_board_is_rom}


def board_summary(board, index, rom):
    bg = board.get("bg") if isinstance(board.get("bg"), dict) else {}
    return {
        "index": index,
        "rom": rom,
        "name": board.get("name"),
        "game": board.get("game"),
        "type": board.get("type"),
        "spaceCount": len(board.get("spaces") or ()),
        "description": board.get("description"),
        "bg": images.url_for(bg.get("src")),
    }


def boards_info():
    """{revision, current: {index, rom}, list: [summary], romList: [summary]}."""
    with lock:
        state = store.state
        return {
            "revision": store.revision,
            "current": current_ref(),
            "list": [board_summary(b, i, False) for i, b in enumerate(state.boards)],
            "romList": [board_summary(b, i, True) for i, b in enumerate(state.rom_boards)],
        }


def app_state():
    """GET /api/state."""
    with lock:
        return {
            "version": __version__,
            "rom": rom_info(),
            "settings": get_settings(),
            "boards": boards_info(),
        }


def get_board(index, rom=False):
    """A board (the store's: don't change it); None if there is none."""
    with lock:
        collection = store.state.rom_boards if rom else store.state.boards
        if isinstance(index, int) and 0 <= index < len(collection):
            return collection[index]
        return None


def current_board():
    with lock:
        return bs.select_current_board(store.state)


def validate_current_board(rom_board_index=None, board=None):
    """Validate the current board (or the given one) for writing over the ROM's boards.

    Returns {results: [{level, message}], general: {errors, warnings},
    boards: [{index, name, unavailable, forcedDisabled, errors, warnings}], romLoaded}.
    """
    with lock:
        empty = {"results": [], "general": {"errors": [], "warnings": []}, "boards": [],
                 "romLoaded": rom_is_loaded()}
        if not rom_is_loaded():
            return empty
        from .lib.validation.validation import validate_current_board_for_overwrite
        rom_boards = list(store.state.rom_boards)
        board = copy.deepcopy(current_board() if board is None else board)
        results = validate_current_board_for_overwrite(
            rom_boards, board, bool(get_setting("ui.skipvalidation")))
    if not results:
        return empty

    def field(r, camel, snake, default=None):
        if camel in r:
            return r[camel]
        return r.get(snake, default)

    general = results[0]
    out = dict(empty)
    out["general"] = {"errors": list(general.get("errors") or []),
                      "warnings": list(general.get("warnings") or [])}
    out["boards"] = []
    for i, r in enumerate(results[1:]):
        out["boards"].append({
            "index": i,
            "name": r.get("name"),
            "unavailable": bool(r.get("unavailable")),
            "forcedDisabled": bool(field(r, "forcedDisabled", "forced_disabled")),
            "errors": list(r.get("errors") or []),
            "warnings": list(r.get("warnings") or []),
        })
    messages = [(1, m) for m in out["general"]["errors"]] + \
        [(2, m) for m in out["general"]["warnings"]]
    if rom_board_index is not None and 0 <= rom_board_index < len(out["boards"]):
        entry = out["boards"][rom_board_index]
        messages += [(1, m) for m in entry["errors"]] + [(2, m) for m in entry["warnings"]]
    out["results"] = [{"level": level, "message": message} for level, message in messages]
    return out


def overwrite_rom_board(rom_board_index):
    """Write the current board over a ROM board (HeaderOverwriteBoardDropdownEntry)."""
    with lock:
        require_rom()
        rom_boards = store.state.rom_boards
        if not isinstance(rom_board_index, int) or isinstance(rom_board_index, bool) \
                or not 0 <= rom_board_index < len(rom_boards):
            raise _api_error("There is no ROM board %s." % (rom_board_index,))
        validation = validate_current_board(rom_board_index)
        entry = validation["boards"][rom_board_index] if rom_board_index < len(
            validation["boards"]) else None
        if entry is None:
            raise _api_error("The board can't be checked against ROM board %d."
                             % rom_board_index)
        if entry["unavailable"]:
            raise _api_error("%s can't be overwritten." % entry["name"])
        errors = validation["general"]["errors"] + entry["errors"]
        if errors or entry["forcedDisabled"]:
            raise _api_error("The board can't be written over %s:\n\n%s"
                             % (entry["name"], "\n".join("- " + e for e in errors)))

        from .lib.adapter.adapters import get_rom_adapter
        adapter = get_rom_adapter({"write_branding": bool(get_setting("write.branding"))})
        if not adapter:
            raise _api_error("This ROM can't be written to.")

        state = store.state
        board = copy.deepcopy(bs.select_current_board(state))
        new_board_index = state.current_board_index if not state.current_board_is_rom else 0
        try:
            adapter.overwrite_board(rom_board_index, board)
        except Exception as e:  # noqa: BLE001
            logger.exception("Overwriting the board failed")
            raise _api_error("Error overwriting the board.\n\n%s" % e)

        # clearBoardsFromROM(); loadBoardsFromROM(); setCurrentBoard(indexOfBoard(board) or 0)
        if new_board_index >= len(store.state.boards):
            new_board_index = 0
        store.dispatch_many([("clearBoardsFromROMAction", None),
                             ("setCurrentBoardAction", {"index": new_board_index, "rom": False})])
        editor_boards.load_boards_from_rom()
        editor_boards.current_board_changed()
        info = rom_info()
    _publish("rom", {"rom": info})
    return boards_info()


# Test play: a ROM that boots straight into a board (lib/playtest), and the emulator

PLAYTEST_FILE = "playtest.json"
PLAYTEST_DIR = "playtest"


def _playtest_saved():
    """What playtest.json holds: {"emulator": str, "options": {game version: options},
    "events": {event id: event test settings}}."""
    data = _read_json_file(PLAYTEST_FILE)
    if not isinstance(data, dict):
        data = {}
    emulator = data.get("emulator")
    options = data.get("options")
    events = data.get("events")
    return {"emulator": emulator if isinstance(emulator, str) else "",
            "options": options if isinstance(options, dict) else {},
            "events": events if isinstance(events, dict) else {}}


def _save_playtest(saved):
    text = jsjson.stringify(saved, indent=1)
    _app.saver.schedule(data_path(PLAYTEST_FILE), lambda: text)
    _app.saver.flush()


def _playtest_options(game_version, saved=None):
    """A game's saved test options, checked (the defaults if they no longer fit)."""
    from .lib import playtest
    saved = saved if saved is not None else _playtest_saved()
    try:
        return playtest.normalize_options(game_version, saved["options"].get(str(game_version)))
    except playtest.PlaytestError:
        return playtest.normalize_options(game_version)


def _emulator_info(saved=None):
    from . import emulator
    saved = saved if saved is not None else _playtest_saved()
    detected = emulator.detect()
    command = saved["emulator"].strip() or (detected["command"] if detected else "")
    return {"command": saved["emulator"].strip(), "detected": detected, "effective": command}


def playtest_info():
    """What the Test Play dialog shows.

    {romLoaded, supported, reason, game: describe() or None, options,
     emulator: {command (as set, "" = automatic), detected: {name, command} or None,
     effective}}.
    """
    from .lib import playtest
    with lock:
        saved = _playtest_saved()
        info = {"romLoaded": rom_is_loaded(), "supported": False, "reason": None, "game": None,
                "options": None, "emulator": _emulator_info(saved)}
        if not info["romLoaded"]:
            info["reason"] = "Open a ROM to test boards in it."
            return info
        rh = _romhandler()
        version = rh.get_game_version()
        board = current_board() or {}
        reason = playtest.unsupported_reason(rh.get_rom_game(), board.get("type"))
        if not reason and not store.state.current_board_is_rom and board.get("game") != version:
            reason = "This board is for Mario Party %s; the ROM is Mario Party %s." % (
                board.get("game"), version)
        info["game"] = playtest.describe(version)
        if info["game"]:
            info["options"] = _playtest_options(version, saved)
        info["supported"] = not reason
        info["reason"] = reason
        return info


def set_playtest_options(emulator=None, options=None):
    """Save the emulator command and/or the open ROM's game's test options."""
    from .lib import playtest
    with lock:
        saved = _playtest_saved()
        if emulator is not None:
            if not isinstance(emulator, str):
                raise _api_error("The emulator is a command line.")
            saved["emulator"] = emulator.strip()
        if options is not None:
            version = _romhandler().get_game_version() if rom_is_loaded() else None
            if not version:
                raise _api_error("Open a ROM to set its game's test options.", 409)
            try:
                saved["options"][str(version)] = playtest.normalize_options(version, options)
            except playtest.PlaytestError as e:
                raise _api_error(str(e))
        _save_playtest(saved)
    return playtest_info()


def _pick_test_board(rom_board_index, board=None):
    """The ROM board to write the current board (or the given one) over for a test:
    (index, name)."""
    validation = validate_current_board(board=board)
    entries = validation["boards"]
    general = validation["general"]["errors"]

    def blocked(entry):
        return entry["unavailable"] or entry["forcedDisabled"] or entry["errors"]

    if rom_board_index is not None:
        if isinstance(rom_board_index, bool) or not isinstance(rom_board_index, int) \
                or not 0 <= rom_board_index < len(entries):
            raise _api_error("There is no ROM board %s." % (rom_board_index,))
        candidates = [entries[rom_board_index]]
    else:
        candidates = entries
    if not general:
        for entry in candidates:
            if not blocked(entry):
                return entry["index"], entry["name"]
    problems = list(general)
    for entry in candidates:
        for message in entry["errors"]:
            if message not in problems:
                problems.append(message)
    if not problems:
        problems.append("None of the ROM's boards can be overwritten by this board.")
    raise _api_error("The board has problems to fix before it can be tested:\n\n%s"
                     % "\n".join("- " + p for p in problems))


def build_test_rom(rom_board_index=None, options=None, board=None):
    """A ROM that boots straight into the current board: (bytes, info).

    The open ROM is not changed: the board is written over one of the boards of a
    copy of it (rom_board_index, or the first it passes the checks for), unless the
    current board is one of the ROM's own. options: test options (lib.playtest);
    the saved ones by default. board: a board to test instead of the current one
    (an event's test board), written over a ROM board in the same way.
    info: {game, romBoardIndex, romBoardName, boardName, fileName, options}.
    """
    from .lib import playtest
    from .lib.adapter.adapters import get_rom_adapter
    with lock:
        require_rom()
        rh = _romhandler()
        version = rh.get_game_version()
        state = store.state
        given = board is not None
        if not given:
            board = bs.select_current_board(state)
        if board is None:
            raise _api_error("There is no board to test.")
        from_rom = not given and bool(state.current_board_is_rom)
        reason = playtest.unsupported_reason(rh.get_rom_game(), board.get("type"))
        if reason:
            raise _api_error(reason)
        try:
            options = playtest.normalize_options(version, options) if options is not None \
                else _playtest_options(version)
        except playtest.PlaytestError as e:
            raise _api_error(str(e))

        if from_rom:
            target, target_name = state.current_board_index, board.get("name")
        else:
            if board.get("game") != version:
                raise _api_error("This board is for Mario Party %s; the ROM is Mario Party %s."
                                 % (board.get("game"), version))
            target, target_name = _pick_test_board(rom_board_index, board if given else None)

        original = rh._rom
        rh._rom = copy.deepcopy(original)
        try:
            if not from_rom:
                adapter = get_rom_adapter({"write_branding": False})
                if not adapter:
                    raise _api_error("This ROM can't be written to.")
                adapter.overwrite_board(target, copy.deepcopy(board))
            playtest.apply(target, options)
            buffer = rh.save_rom(False)
            playtest.finish_rom(buffer)
        except playtest.PlaytestError as e:
            raise _api_error(str(e))
        except Exception as e:  # noqa: BLE001
            if getattr(e, "status", None):           # an ApiError
                raise
            logger.exception("Building the test ROM failed")
            raise _api_error("Error building the test ROM.\n\n%s" % e)
        finally:
            rh._rom = original
        info = {
            "game": version,
            "romBoardIndex": target,
            "romBoardName": target_name,
            "boardName": board.get("name"),
            "fileName": "PartyPlanner64 Test (MP%s).z64" % version,
            "options": options,
        }
        return bytes(buffer), info


def playtest(rom_board_index=None, options=None, launch=True, board=None):
    """Build the test ROM, write it to the data folder and start the emulator with it.

    board: a board to test instead of the current one (see build_test_rom).
    Returns build_test_rom's info, plus {path, launched, command: [arguments]}.
    """
    from . import emulator
    command = _emulator_info()["effective"]
    if launch and not command:
        raise _api_error("No Nintendo 64 emulator was found. Set the emulator's command "
                         "in the Test Play options.")
    data, info = build_test_rom(rom_board_index, options, board)
    directory = data_path(PLAYTEST_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / info["fileName"]
    tmp = directory / ("." + info["fileName"] + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)          # a running emulator keeps the file it opened
    info["path"] = str(path)
    info["launched"] = False
    info["command"] = None
    if launch:
        try:
            info["command"] = emulator.launch(command, path,
                                              log_path=directory / "emulator.log")
        except emulator.EmulatorError as e:
            raise _api_error("%s\n\nThe test ROM is at %s." % (e, path))
        info["launched"] = True
    return info


# Test play of one event: a small board around it (lib/playtest/eventtest)

def _event_for_test(code, language):
    """The custom event of the code (as the event editor has it, saved or not)."""
    from .lib.events.customevents import create_custom_event
    if isinstance(language, str) and language.isdigit():
        language = int(language)
    if language not in (0, 1) or isinstance(language, bool):
        raise _api_error("The language is 0 (MIPS assembly) or 1 (C).")
    if not isinstance(code, str) or not code.strip():
        raise _api_error("The event has no code.")
    try:
        return create_custom_event(language, code)
    except ValueError as e:
        raise _api_error(str(e))


def _event_test_reason(event):
    """Why the event cannot be test-played with the open ROM, or None."""
    from .lib import playtest
    from .lib.playtest import eventtest
    from .lib.types import Game
    if not rom_is_loaded():
        return "Open a Mario Party 3 (U) ROM to test events in it."
    rh = _romhandler()
    return playtest.unsupported_reason(rh.get_rom_game()) or \
        eventtest.unsupported_reason(event, Game.MP3_USA)


def event_test_info(code, language):
    """What the event's Test Play dialog shows.

    {event: {id, name}, supported, reason, test: eventtest.describe(),
     settings: the saved settings for the event (or the defaults), emulator}.
    """
    from .lib.playtest import eventtest
    with lock:
        event = _event_for_test(code, language)
        saved = _playtest_saved()
        reason = _event_test_reason(event)
        return {
            "event": {"id": event.id, "name": event.name},
            "supported": not reason,
            "reason": reason,
            "test": eventtest.describe(event),
            "settings": eventtest.normalize_settings(event, saved["events"].get(event.id),
                                                     lenient=True),
            "emulator": _emulator_info(saved),
        }


def event_playtest(code, language, settings=None, rom_board_index=None, launch=True):
    """Test-play an event: build its test board, then a test ROM of it (playtest()).

    The settings (eventtest.normalize_settings) are saved for the event's next test.
    The players, coins, turn and emulator are the Test Play options.
    Returns playtest()'s info, plus {event: name, settings}.
    """
    from .lib.events.customevents import validate_custom_event
    from .lib.playtest import PlaytestError, eventtest
    from .lib.types import Game
    with lock:
        require_rom()
        event = _event_for_test(code, language)
        reason = _event_test_reason(event)
        if reason:
            raise _api_error(reason)
        try:
            settings = eventtest.normalize_settings(event, settings)
        except PlaytestError as e:
            raise _api_error(str(e))
        saved = _playtest_saved()
        saved["events"][event.id] = settings
        _save_playtest(saved)

        # Its code is checked first, for a clearer message than the ROM build's.
        single = copy.copy(event)
        single.supported_games = [Game.MP3_USA]
        try:
            validate_custom_event(single)
        except ValueError as e:
            raise _api_error(str(e))
        new_board = editor_boards._make_default_board(_romhandler().get_game_version())
        board = eventtest.build_board(new_board, event, settings)
    info = playtest(rom_board_index, None, launch, board)
    info["event"] = event.name
    info["settings"] = settings
    return info
