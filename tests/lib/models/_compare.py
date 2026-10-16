"""Helpers comparing Python objects with the TypeScript's JSON dumps."""

import re


def snake(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()


def assert_matches(ts, py, path="$"):
    """Assert that every field of the TypeScript dump is equal in the Python value."""
    if isinstance(ts, dict) and set(ts) == {"hex"}:
        assert bytes(py).hex() == ts["hex"], path
    elif isinstance(ts, dict):
        for key, value in ts.items():
            name = snake(key)
            if isinstance(py, dict):
                assert name in py, "%s.%s missing" % (path, name)
                sub = py[name]
            else:
                assert hasattr(py, name), "%s.%s missing" % (path, name)
                sub = getattr(py, name)
            assert_matches(value, sub, path + "." + name)
    elif isinstance(ts, list):
        assert len(ts) == len(py), path
        for i, (a, b) in enumerate(zip(ts, py)):
            assert_matches(a, b, "%s[%d]" % (path, i))
    elif isinstance(ts, float):
        assert abs(ts - py) <= 1e-6 * max(1.0, abs(ts)), path
    else:
        assert ts == py, "%s: %r != %r" % (path, ts, py)
