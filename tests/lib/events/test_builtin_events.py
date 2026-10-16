"""Built-in events: registration order/shape and write() output, against the TypeScript."""

import json
import os

import pytest

from partyplanner64.lib.events.builtin import events_include  # noqa: F401
from partyplanner64.lib.events.builtin.mp1.u.star_event1 import StarEvent1
from partyplanner64.lib.events.builtin.mp3.u.gate_close_event3 import GateClose3
from partyplanner64.lib.events.builtin.mp3.u.gate_event3 import Gate3
from partyplanner64.lib.events.event_library import get_events_in_library
from partyplanner64.lib.utils.dataview import DataView

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "events")


def _load(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


def test_library_order_and_shape():
    expected = _load("library.json")
    events = get_events_in_library()
    builtin_ids = [k for k, e in events.items() if not e.custom]
    assert builtin_ids == [e["key"] for e in expected]
    for e in expected:
        event = events[e["key"]]
        exp = {k: v for k, v in e.items() if k not in ("key", "hasParse", "hasWrite")}
        assert event.to_json() == exp
        assert (event.parse is not None) == e["hasParse"]
        assert (event.write is not None) == e["hasWrite"]


def test_write_outputs_match_typescript():
    data = _load("write.json")
    pvs = data["pvs"]
    results = data["results"]
    events = dict(get_events_in_library())
    events.update({"GATE3": Gate3, "GATECLOSE3": GateClose3, "STAR1": StarEvent1})
    checked = 0
    for event_id, game_version, board_index, p, result_index in data["out"]:
        expected = results[result_index]
        event = events[event_id]
        inst = {"id": event_id, "activationType": 1, "executionType": 1,
                "parameterValues": json.loads(json.dumps(pvs[p]))}
        info = {"game_version": game_version, "board_index": board_index}
        if isinstance(expected, dict) and "error" in expected:
            with pytest.raises(Exception) as excinfo:
                event.write(DataView(bytearray(16)), inst, info, {})
            if expected["error"].startswith("Error: "):
                assert str(excinfo.value) == expected["error"][len("Error: "):]
        else:
            result = event.write(DataView(bytearray(16)), inst, info, {})
            if expected == "__undefined__":
                assert result is None
            else:
                assert result == expected, (event_id, game_version, board_index, p)
        checked += 1
    assert checked == len(data["out"])
