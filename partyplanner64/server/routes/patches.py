"""Patches: GameShark cheats embedded in the ROM when it is saved
(apps/partyplanner64/views/gameshark.tsx, packages/lib/patches/gameshark).

The cheats are compiled to MIPS when added and kept in
partyplanner64.lib.patches.gameshark.cheats.current_cheats until the ROM is
closed or another is opened (romhandler resets them); saving the ROM writes
them with the game's hook.

    GET  /api/patches               -> {supported, game, cheats: [{index, text, codes, size}]}
    POST /api/patches/parse {text}  -> {codes: [{opcode, addr, value}]} (checks, applies nothing)
    POST /api/patches {text}        -> as GET, with the cheat added
    POST /api/patches/<i>/delete    -> as GET
    POST /api/patches/clear         -> as GET
"""

import threading

from ..http import ApiError, route

_lock = threading.Lock()
# What the user typed for each compiled cheat: [(buffer, text, codes)]. The buffers
# are the objects in cheats.current_cheats, matched by identity, so this follows
# reset_cheats() (a new ROM) without being told.
_applied = []

def _state_lock():
    """The app's lock (state.lock): held while changing the ROM."""
    from ... import state
    return state.lock



def _romhandler():
    from ...lib.romhandler import romhandler
    return romhandler


def _gs():
    """The gameshark modules: (parser, compiler, cheats, hook)."""
    try:
        from ...lib.patches.gameshark import cheats, compiler, hook, parser
    except ImportError:
        raise ApiError("GameShark patches aren't available in this installation.", 501)
    return parser, compiler, cheats, hook


def _code_json(code):
    get = code.get if isinstance(code, dict) else (lambda k: getattr(code, k))
    return {"opcode": get("opcode"), "addr": get("addr"), "value": get("value")}


def _parse(text):
    """Parse cheat text: the codes, or ApiError (as the original's message)."""
    parser = _gs()[0]
    codes = parser.Parser.parse(text or "")
    if not codes:
        if not (text or "").split():
            raise ApiError("Paste one or more GameShark codes first.")
        raise ApiError("There was an error parsing the entered cheats. Each code is an "
                       "address and a value, e.g. 8105E418 2400; the supported types are "
                       "80, 81 (write) and D0 to D3 (conditions).")
    return codes


def _listing():
    rh = _romhandler()
    rom = rh.get_rom()
    from ...lib.types import get_game_name
    game = rh.get_rom_game() if rom else None
    supported = False
    current = []
    if rom is not None:
        _, _, cheats, hook = _gs()
        supported = bool(hook.rom_supports_cheats())
        current = list(cheats.current_cheats)
    with _lock:
        by_id = {id(buf): (text, codes) for buf, text, codes in _applied}
        _applied[:] = [(buf, *by_id[id(buf)]) for buf in current if id(buf) in by_id]
    out = []
    for i, buf in enumerate(current):
        text, codes = by_id.get(id(buf), (None, []))
        out.append({"index": i, "text": text, "codes": codes, "size": len(buf)})
    return {"supported": supported, "game": get_game_name(game) if game else None,
            "romOpen": rom is not None, "cheats": out}


def _require_supported():
    rh = _romhandler()
    if rh.get_rom() is None:
        raise ApiError("Open a ROM first.", 409)
    if not _gs()[3].rom_supports_cheats():
        raise ApiError("Embeddable GameShark cheats are not supported with this ROM.")


@route("GET", "/api/patches")
def get_patches(req):
    return _listing()


@route("POST", "/api/patches/parse")
def parse_patch(req):
    codes = _parse(req.arg("text", ""))
    return {"codes": [_code_json(c) for c in codes]}


@route("POST", "/api/patches")
def add_patch(req):
    _require_supported()
    text = req.arg("text", "")
    codes = _parse(text)
    _, compiler, cheats, _ = _gs()
    buf = compiler.Compiler().compile(codes)
    if not buf:
        raise ApiError("There was an error compiling the entered cheats.")
    with _state_lock():
        cheats.current_cheats.append(buf)
    with _lock:
        _applied.append((buf, "\n".join(" ".join(line.split()) for line in text.strip().splitlines()
                                        if line.strip()),
                         [_code_json(c) for c in codes]))
    return _listing()


@route("POST", "/api/patches/<int:index>/delete")
def delete_patch(req, index):
    _require_supported()
    cheats = _gs()[2]
    if not 0 <= index < len(cheats.current_cheats):
        raise ApiError("There is no cheat %d." % index, 404)
    with _state_lock():
        del cheats.current_cheats[index]
    return _listing()


@route("POST", "/api/patches/clear")
def clear_patches(req):
    if _romhandler().get_rom() is not None:
        with _state_lock():
            _gs()[2].current_cheats.clear()
    return _listing()
