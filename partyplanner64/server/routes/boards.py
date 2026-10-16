"""Boards: the board list, the current board and its edits (see docs/API.md)."""

import copy
import logging

from ... import state
from ...editor import boards as editor_boards
from ...editor import images, jsjson, ops
from ...editor.store import store
from ..http import ApiError, Response, route

logger = logging.getLogger("partyplanner64")

# Errors from reducers and the library that are the request's fault.
OP_ERRORS = (ValueError, IndexError, KeyError, TypeError, AssertionError, AttributeError)


def op_error(e):
    if isinstance(e, KeyError):
        return ApiError("Missing argument: %s" % (e.args[0] if e.args else e))
    return ApiError(str(e) or type(e).__name__)


def flag(value):
    """A boolean from JSON or a query string ("1", "true")."""
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


def int_arg(value, name):
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError("%s must be a number." % name)
    return value


def current_board_response():
    """{revision, index, rom, board, canUndo, canRedo, ui}."""
    with state.lock:
        present = store.state
        board = state.current_board()
        return {
            "revision": store.revision,
            "index": present.current_board_index,
            "rom": present.current_board_is_rom,
            "board": images.externalize(board),
            "canUndo": store.can_undo,
            "canRedo": store.can_redo,
            "ui": present.ui(),
        }


def _board_or_404(index, rom):
    board = state.get_board(index, rom)
    if board is None:
        raise ApiError("There is no %sboard %s." % ("ROM " if rom else "", index), 404)
    return board


@route("GET", "/api/board")
def get_current_board(req):
    return current_board_response()


@route("GET", "/api/boards/<int:index>")
def get_board(req, index):
    board = _board_or_404(index, flag(req.query.get("rom")))
    return {"board": images.externalize(board)}


@route("GET", "/api/boards/<int:index>/export")
def export_board(req, index):
    board = _board_or_404(index, flag(req.query.get("rom")))
    board = editor_boards.strip_private_props(board)
    return Response(jsjson.stringify(board), "application/json",
                    filename="%s.json" % (board.get("name") or "board"))


@route("POST", "/api/boards/current")
def set_current(req):
    index = int_arg(req.arg("index"), "index")
    rom = flag(req.arg("rom", False))
    if state.get_board(index, rom) is None:
        raise ApiError("There is no %sboard %s." % ("ROM " if rom else "", index), 404)
    editor_boards.set_current_board(index, rom)
    return {"boards": state.boards_info()}


@route("POST", "/api/boards/new")
def new_board(req):
    from ...lib.debug import is_debug
    from ...lib.types import BoardType
    game = req.arg("game", 1)
    if isinstance(game, str) and game.isdigit():
        game = int(game)
    if game not in (1, 2, 3):
        raise ApiError("The game is 1, 2 or 3.")
    board_type = req.arg("type", BoardType.NORMAL.value) or BoardType.NORMAL.value
    if board_type not in (BoardType.NORMAL.value, BoardType.DUEL.value):
        raise ApiError("The board type is NORMAL or DUEL.")
    if game != 3:
        board_type = BoardType.NORMAL.value      # newboard.tsx: only MP3 has duel boards
    theme = req.arg("theme", "default") or "default"
    if theme not in [t["id"] for t in editor_boards.THEMES]:
        raise ApiError("Unknown theme: %s" % theme)
    if board_type == BoardType.DUEL.value and not is_debug():
        raise ApiError("Duel board support is partially finished, coming soon!")
    with state.lock:
        index = editor_boards.add_board(None, game=game, type=BoardType(board_type))
        editor_boards.set_current_board(index)
        return {"boards": state.boards_info(), "index": index}


@route("POST", "/api/boards/import")
def import_board(req):
    try:
        board = jsjson.parse(req.body)
    except (ValueError, UnicodeDecodeError):
        raise ApiError("Board could not be parsed.")
    if not isinstance(board, dict):
        raise ApiError("Board could not be parsed.")
    board = images.internalize(board)
    with state.lock:
        try:
            index = editor_boards.add_board(board)
        except OP_ERRORS as e:
            raise ApiError("Board could not be loaded: %s" % e)
        editor_boards.set_current_board(index)
        return {"boards": state.boards_info(), "index": index}


@route("POST", "/api/boards/copy")
def copy_board(req):
    index = int_arg(req.arg("index"), "index")
    rom = flag(req.arg("rom", False))
    try:
        new_index = editor_boards.copy_board(index, rom, flag(req.arg("makeCurrent", False)))
    except IndexError as e:
        raise ApiError(str(e), 404)
    return {"boards": state.boards_info(), "index": new_index}


@route("POST", "/api/boards/delete")
def delete_board(req):
    index = int_arg(req.arg("index"), "index")
    if flag(req.arg("rom", False)):
        raise ApiError("Boards of the ROM can't be deleted.")
    if state.get_board(index, False) is None:
        raise ApiError("There is no board %s." % index, 404)
    editor_boards.delete_board(index)
    return {"boards": state.boards_info()}


# Edits of the current board


def _apply(op_list):
    try:
        ops.apply(op_list)
    except OP_ERRORS as e:
        logger.debug("Board op failed", exc_info=True)
        raise op_error(e)
    return current_board_response()


@route("POST", "/api/board/op")
def board_op(req):
    body = req.json
    if not isinstance(body, dict) or not body.get("op"):
        raise ApiError("Which op? ({op, args})")
    return _apply([(body["op"], body.get("args"))])


@route("POST", "/api/board/ops")
def board_ops(req):
    body = req.json
    op_list = body.get("ops") if isinstance(body, dict) else None
    if not isinstance(op_list, list) or not all(isinstance(o, dict) and o.get("op")
                                                for o in op_list):
        raise ApiError("Send {ops: [{op, args}, ...]}.")
    if not op_list:
        return current_board_response()
    return _apply([(o["op"], o.get("args")) for o in op_list])


@route("POST", "/api/board/undo")
def undo(req):
    store.undo()
    return current_board_response()


@route("POST", "/api/board/redo")
def redo(req):
    store.redo()
    return current_board_response()


@route("GET", "/api/board/validate")
def validate(req):
    rom_board = req.query.get("romBoard")
    rom_board = int(rom_board) if rom_board not in (None, "") and \
        rom_board.lstrip("-").isdigit() else None
    return state.validate_current_board(rom_board)


# Additional background and music selection code


def _code_kind(kind):
    if kind == "additionalbg":
        from ...lib.events import additionalbg as module
        return (module.test_additional_bg_code_all_games, module.get_default_additional_bg_code,
                "additionalbgcode")
    if kind == "audioselect":
        from ...lib.events import getaudiochoice as module
        return (module.test_get_audio_code_all_games, module.get_default_get_audio_code,
                "audioSelectCode")
    raise ApiError('kind is "additionalbg" or "audioselect".')


def _language(value):
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if value not in (0, 1):
        raise ApiError("The language is 0 (MIPS assembly) or 1 (C).")
    return value


@route("POST", "/api/board/code/test")
def test_code(req):
    test, _, _ = _code_kind(req.arg("kind"))
    code = req.arg("code") or ""
    language = _language(req.arg("language", 0))
    with state.lock:
        board = copy.deepcopy(state.current_board())
    try:
        failures = test(code, language, board)
    except Exception as e:  # noqa: BLE001 - shown to the user
        failures = [str(e)]
    failures = [str(f) for f in failures or []]
    return {"ok": not failures, "messages": failures}


@route("GET", "/api/board/code")
def get_code(req):
    _, _, key = _code_kind(req.query.get("kind"))
    from ...lib import boards as lib_boards
    with state.lock:
        board = state.current_board()
        if key == "additionalbgcode":
            found = lib_boards.get_additional_background_code(board)
        else:
            found = lib_boards.get_audio_select_code(board)
    if not found:
        return {"code": None, "language": None}
    return {"code": found.get("code"), "language": found.get("language")}


@route("GET", "/api/board/code/default")
def get_default_code(req):
    _, default, _ = _code_kind(req.query.get("kind"))
    return {"code": default(_language(req.query.get("language", 0)))}
