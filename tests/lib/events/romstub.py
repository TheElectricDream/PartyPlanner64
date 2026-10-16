"""A stand-in for the ROM handler in tests of events and validation.

Uses the real `partyplanner64.lib.romhandler.romhandler` singleton when that
module exists (patching its methods), or installs a stub module otherwise.
"""

import sys
import types

from partyplanner64.lib.types import Game


def _version_of(game):
    if game is None:
        return None
    name = Game(game).name
    return int(name[2])


class _StubRomHandler:
    def get_rom_game(self):
        return None

    def get_game_version(self):
        return None

    def rom_is_loaded(self):
        return False

    def get_rom(self):
        return None


def install(monkeypatch, game=None, rom=None):
    """Make the ROM handler report `game` (a Game, or None for no ROM)."""
    try:
        from partyplanner64.lib.romhandler import romhandler
    except ImportError:
        module = types.ModuleType("partyplanner64.lib.romhandler")
        module.romhandler = _StubRomHandler()
        monkeypatch.setitem(sys.modules, "partyplanner64.lib.romhandler", module)
        import partyplanner64.lib as lib
        monkeypatch.setattr(lib, "romhandler", module, raising=False)
        romhandler = module.romhandler
    monkeypatch.setattr(romhandler, "get_rom_game", lambda: game, raising=False)
    monkeypatch.setattr(romhandler, "get_game_version", lambda: _version_of(game), raising=False)
    monkeypatch.setattr(romhandler, "rom_is_loaded", lambda: rom is not None, raising=False)
    monkeypatch.setattr(romhandler, "get_rom", lambda: rom, raising=False)
    return romhandler
