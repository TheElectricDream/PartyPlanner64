"""events.py and EventLibrary.py basics."""

import pytest

from partyplanner64.lib.events import event_library
from partyplanner64.lib.events import events as E
from partyplanner64.lib.events.builtin import events_include  # noqa: F401
from partyplanner64.lib.events.customevents import create_custom_event
from partyplanner64.lib.events.event_cache import EventCache
from partyplanner64.lib.types import EditorEventActivationType, Game

CODE = "; NAME: My Event\n; GAMES: MP1_USA,MP3_USA\n; EXECUTION: Direct\n; PARAM: Number|n\nnop\n"


def test_create_event_instance():
    lib = event_library.get_events_in_library()
    assert E.create_event_instance(lib["BANK"]) == {"id": "BANK", "activationType": 1, "executionType": 1}
    custom = create_custom_event(0, CODE)
    inst = E.create_event_instance(custom, {"parameterValues": {"n": 3}, "activationType": -2})
    assert inst == {"id": "My Event", "activationType": -2, "executionType": 1,
                    "parameterValues": {"n": 3}, "custom": True}


def test_get_event_prefers_board_code():
    lib = event_library.get_events_in_library()
    board = {"events": {"My Event": CODE}}
    ev = E.get_event("My Event", board, lib)
    assert ev.custom and ev.asm == CODE and ev.activation_type == EditorEventActivationType.LANDON
    assert E.get_event("BOO", board, lib) is lib["BOO"]
    assert E.get_event("NOPE", board, lib) is None


def test_write_dispatch():
    board = {"events": {"My Event": {"language": 0, "code": CODE}}}
    buf = bytearray(0x40)
    info = {"board": board, "game_version": 3, "offset": 0x10}
    assert E.write(buf, {"id": "My Event", "custom": True}, info, {}) == CODE
    assert "__PP64_INTERNAL_BANK_SPACE_EVENT" in E.write(buf, {"id": "BANK"}, info, {})
    with pytest.raises(ValueError, match="custom event, but its code"):
        E.write(buf, {"id": "Other", "custom": True}, info, {})
    with pytest.raises(ValueError, match="Could not find/write NOPE for game 3"):
        E.write(buf, {"id": "NOPE"}, info, {})
    with pytest.raises(ValueError, match="Could not write BANK for game 1"):
        E.write(buf, {"id": "BANK"}, dict(info, game_version=1), {})


def test_custom_events_and_support():
    lib = event_library.get_events_in_library()
    custom = create_custom_event(0, CODE)
    event_library.add_event_to_library(custom)
    try:
        customs = E.get_custom_events()
        assert [e.id for e in customs] == ["My Event"]
        assert customs[0] is not custom and customs[0].to_json() == custom.to_json()
        assert not E.is_unsupported(custom, Game.MP1_USA)
        assert E.is_unsupported(custom, "NMWE")
        assert not E.is_unsupported(custom, "NMVE")
        with pytest.raises(ValueError, match="as it is a built-in event"):
            event_library.remove_event_from_library("BOO")
        with pytest.raises(ValueError, match="isn't in the event library"):
            event_library.remove_event_from_library("NOPE")
        event_library.remove_event_from_library("My Event")  # (A no-op, as in the TypeScript.)
    finally:
        lib.pop("My Event", None)


def test_set_event_library_implementation():
    old = event_library.get_event_library_implementation()
    new = event_library.BasicEventLibrary()
    try:
        event_library.set_event_library_implementation(new)
        assert list(new.get_events_in_library()) == list(old.get_events_in_library())
        assert event_library.get_event_from_library("BOO") is old.get_event_from_library("BOO")
    finally:
        event_library.set_event_library_implementation(old)


def test_event_cache():
    EventCache.set("k", [1])
    assert EventCache.get("k") == [1]
    assert EventCache.get("missing") is None
