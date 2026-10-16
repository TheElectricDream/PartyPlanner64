"""Plain-object helpers."""

import copy
import json


def copy_object(obj):
    """Return a deep copy of a JSON-like value (JSON.parse(JSON.stringify(obj)))."""
    return copy.deepcopy(obj)


def equals(obj1, obj2):
    """Return whether two JSON-like values serialize the same."""
    return json.dumps(obj1, sort_keys=False) == json.dumps(obj2, sort_keys=False)


def is_empty(obj):
    """Return whether a dict (or other container) has no entries."""
    return not obj
