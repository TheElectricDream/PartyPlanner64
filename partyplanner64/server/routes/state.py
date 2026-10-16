"""GET /api/state: the app's state (the ROM, settings, the board list)."""

from ... import state
from ..http import route


@route("GET", "/api/state")
def get_state(req):
    return state.app_state()
