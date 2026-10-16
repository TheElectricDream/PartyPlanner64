"""Settings: GET/POST /api/settings (ids as the original's, e.g. "ui.advanced")."""

from ... import state
from ..http import ApiError, route


@route("GET", "/api/settings")
def get_settings(req):
    return state.get_settings()


@route("POST", "/api/settings")
def set_settings(req):
    try:
        return state.set_settings(req.json)
    except ValueError as e:
        raise ApiError(str(e))


@route("GET", "/api/settings/schema")
def get_settings_schema(req):
    return state.settings_schema()


@route("POST", "/api/settings/reset")
def reset_settings(req):
    return state.reset_settings()
