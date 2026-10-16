"""Tests here may replace the global event library (state.configure); put it back after."""

import pytest


@pytest.fixture(autouse=True)
def _restore_globals():
    from partyplanner64.lib import debug
    from partyplanner64.lib.events import event_library
    library = event_library.get_event_library_implementation()
    was_debug = debug.is_debug()
    yield
    event_library._event_library = library
    debug.set_debug(was_debug)
