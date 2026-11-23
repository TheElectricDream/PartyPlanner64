"""Per-game symbol tables (port of symbols/symbols.ts).

The tables are generated data (scripts/update_symbols.py writes them from
the `symbols` repository) in the JSON files next to this module. A symbol
(ISymbol) is a dict: {"name", "type", "addr"[, "desc"]}.
"""

import json
import os

from ..types import Game

_DIR = os.path.dirname(os.path.abspath(__file__))
_cache = {}


def _load(name):
    symbols = _cache.get(name)
    if symbols is None:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            symbols = json.load(f)
        _cache[name] = symbols
    return symbols


def _get_symbols_for_game(game):
    if game == Game.MP1_USA:
        return _load("MarioParty1U")
    if game == Game.MP1_JPN:
        return _load("MarioParty1J")
    if game == Game.MP1_PAL:
        return _load("MarioParty1E")
    if game == Game.MP2_USA:
        return _load("MarioParty2U")
    if game == Game.MP2_JPN:
        return _load("MarioParty2J")
    if game == Game.MP2_PAL:
        raise ValueError("Symbols not available for game type %s" % _game_str(game))
    if game == Game.MP3_USA:
        return _load("MarioParty3U")
    if game == Game.MP3_JPN:
        return _load("MarioParty3J")
    if game == Game.MP3_PAL:
        raise ValueError("Symbols not available for game type %s" % _game_str(game))
    raise ValueError("Unrecognized game type %s" % _game_str(game))


def _game_str(game):
    return game.value if isinstance(game, Game) else str(game)


def get_symbols(game, type=None):
    """Retrieves the list of symbols for a game, optionally filtered by type."""
    symbols = _get_symbols_for_game(game)
    if not symbols:
        return []

    if type:
        symbols = [sym for sym in symbols if sym["type"] == type]

    return [sym for sym in symbols
            if sym["name"][:1] != "_"  # Filter private-ish symbols
            and sym["name"][:1] != "?"]  # Filter non-symbols starting with ?


def get_symbol(game, name):
    """Retrieves the value (address) of a particular symbol."""
    symbols = _get_symbols_for_game(game)
    if not symbols:
        raise ValueError("Symbols aren't available for %s." % _game_str(game))

    for sym in symbols:
        if sym["name"] == name:
            return sym["addr"]

    raise ValueError("Symbol %s wasn't found for %s." % (name, _game_str(game)))


_NOTES_FILES = {
    Game.MP1_USA: "MarioParty1U", Game.MP1_JPN: "MarioParty1J", Game.MP1_PAL: "MarioParty1E",
    Game.MP2_USA: "MarioParty2U", Game.MP2_JPN: "MarioParty2J",
    Game.MP3_USA: "MarioParty3U", Game.MP3_JPN: "MarioParty3J",
}


def get_symbol_notes(game):
    """The whole comment of each of a game's symbols, by name ({} without symbols).

    A symbol's "desc" is its comment up to the first comma (as the original
    kept it); these (notes/<Game>.json, also written by update_symbols.py) are
    the whole comments, e.g. the arguments of a function: "A0=player_index,
    A1=amount (signed), ensures 0 <= coins <= 999".
    """
    name = _NOTES_FILES.get(game)
    if name is None:
        return {}
    return _load(os.path.join("notes", name))
