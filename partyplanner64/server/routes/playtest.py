"""Test play: build a ROM that boots straight into the current board (or into a small
board around one event), and start it in an emulator (GET/POST /api/playtest)."""

from ... import state
from ..http import ApiError, Response, route


def _rom_board_index(req):
    index = req.arg("romBoardIndex")
    if index is None or index == "":
        return None
    if isinstance(index, str) and index.lstrip("-").isdigit():
        index = int(index)
    if not isinstance(index, int) or isinstance(index, bool):
        raise ApiError("romBoardIndex is the index of a ROM board.")
    return index


def _options(req):
    options = req.arg("options")
    if options is not None and not isinstance(options, dict):
        raise ApiError("options is an object.")
    return options


@route("GET", "/api/playtest")
def info(req):
    return state.playtest_info()


@route("POST", "/api/playtest/options")
def set_options(req):
    return state.set_playtest_options(req.arg("emulator"), _options(req))


@route("POST", "/api/playtest")
def playtest(req):
    launch = req.arg("launch", True)
    return state.playtest(_rom_board_index(req), _options(req), launch=launch is not False)


@route("POST", "/api/playtest/rom")
def test_rom(req):
    data, info = state.build_test_rom(_rom_board_index(req), _options(req))
    return Response(data, "application/octet-stream", filename=info["fileName"])


def _settings(req):
    settings = req.arg("settings")
    if settings is not None and not isinstance(settings, dict):
        raise ApiError("settings is an object.")
    return settings


@route("POST", "/api/playtest/event/info")
def event_info(req):
    """The event test dialog's contents, for the event's code (saved or not)."""
    return state.event_test_info(req.arg("code"), req.arg("language", 0))


@route("POST", "/api/playtest/event")
def event_playtest(req):
    """Test-play an event: a test ROM of a small board whose spaces run it."""
    launch = req.arg("launch", True)
    return state.event_playtest(req.arg("code"), req.arg("language", 0), _settings(req),
                                _rom_board_index(req), launch=launch is not False)


@route("POST", "/api/playtest/stop")
def stop(req):
    from ... import emulator
    return {"stopped": emulator.stop()}
