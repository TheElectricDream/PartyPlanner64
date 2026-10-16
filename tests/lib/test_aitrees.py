"""AI decision tree parsing, against the TypeScript (fixtures/events/aitrees.json)."""

import json
import os

from partyplanner64.lib.ai.aitrees import DecisionTreeNodeType, parse_decision_tree
from partyplanner64.lib.utils.dataview import DataView

with open(os.path.join(os.path.dirname(__file__), "..", "fixtures", "events", "aitrees.json")) as f:
    REF = json.load(f)


def test_parse_decision_tree():
    view = DataView(bytearray(REF["bytes"]))
    for game in ("1", "2", "3"):
        assert parse_decision_tree(view, 0x10, REF["base"], int(game)) == REF[game]


def test_node_types():
    assert DecisionTreeNodeType.leaf == 0
    assert DecisionTreeNodeType.hasItem == 8
