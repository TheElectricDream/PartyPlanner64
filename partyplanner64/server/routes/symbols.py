"""The games' symbols (functions and data in RAM), for the MIPS autocompletion of
the event code editor (apps/partyplanner64/utils/lib/mp-mips-autocomplete.ts).

    GET /api/symbols?games=MP1_USA,MP3_USA&type=code
        -> {games: ["MP1_USA", "MP3_USA"], missing: [], symbols: [{name, type, addr, desc}]}

With several games, the answer is the intersection of their symbols (by name), as
the original completed only names that every supported game has. `type` filters
by symbol type ("code", "data", "u32", ...). Private-ish names (starting with
"_" or "?") are left out, as in symbols.getSymbols.
"""

from functools import lru_cache

from ..http import ApiError, route


def _game(value):
    """A Game from a member name ("MP3_USA") or an ID ("NMVE")."""
    from ...lib.types import Game
    value = str(value).strip()
    if value in Game.__members__:
        return Game[value]
    for game in Game:
        if game.value == value:
            return game
    raise ApiError("Unknown game: %s" % value)


def _get_symbols(game, sym_type=None):
    from ...lib.symbols.symbols import get_symbols
    return get_symbols(game, sym_type)


def _plain(sym):
    """A symbol as JSON (the port may give dicts or objects)."""
    get = sym.get if isinstance(sym, dict) else (lambda k, d=None: getattr(sym, k, d))
    out = {"name": get("name"), "type": get("type"), "addr": get("addr")}
    if get("desc"):
        out["desc"] = get("desc")
    return out


@lru_cache(maxsize=64)
def symbols_for(games, sym_type=None):
    """The symbols every game in `games` (a tuple of Games) has, sorted by name.

    Returns (symbols, missing): missing lists the games without symbols.
    """
    result = None
    missing = []
    for game in games:
        try:
            syms = [_plain(s) for s in _get_symbols(game, sym_type)]
        except ImportError:
            raise ApiError("The game symbols are not available in this installation.", 501)
        except Exception:  # noqa: BLE001 - e.g. no symbols for MP2/MP3 PAL
            missing.append(game.name)
            continue
        if result is None:
            result = syms
        else:
            names = {s["name"] for s in syms}
            result = [s for s in result if s["name"] in names]
    result = sorted(result or [], key=lambda s: s["name"])
    return result, missing


@route("GET", "/api/symbols")
def get_symbols_route(req):
    raw = req.query.get("games") or req.query.get("game") or ""
    games = tuple(_game(g) for g in raw.split(",") if g.strip())
    if not games:
        return {"games": [], "missing": [], "symbols": []}
    sym_type = req.query.get("type") or None
    symbols, missing = symbols_for(games, sym_type)
    return {"games": [g.name for g in games], "missing": missing, "symbols": symbols}
