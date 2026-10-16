"""Whether debug behaviours are on (the "Debug features" setting)."""

_debug = False


def is_debug():
    """Return whether debug behaviors are enabled."""
    return _debug


def set_debug(on):
    """Turn debug behaviors on or off."""
    global _debug
    _debug = bool(on)
