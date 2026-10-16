"""Shared helpers for the adapter tests (E1)."""

import json
import os

import pytest

import partyplanner64.lib.events.builtin.events_include  # noqa: F401  (registers the built-in events)

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "adapter")

GAME_IDS = {1: "CLBE", 2: "NMWE", 3: "NMVE"}


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def as_json(value):
    """Round-trip through the JavaScript-style JSON writer (string keys, 5 not 5.0)."""
    from partyplanner64.lib.adapter._js import json_stringify
    return json.loads(json_stringify(value))


@pytest.fixture
def fake_game(monkeypatch):
    """Make the romhandler report a game without a ROM: fake_game(3)."""
    from partyplanner64.lib.romhandler import romhandler

    def set_game(version):
        monkeypatch.setattr(romhandler, "get_game_version", lambda: version)
        monkeypatch.setattr(romhandler, "get_rom_game", lambda: GAME_IDS[version])
        return romhandler

    return set_game
