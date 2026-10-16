"""The ROM: open (POST /api/rom), close, save, and write a board over a ROM board."""

from ... import state
from ..http import ApiError, Response, route


@route("POST", "/api/rom")
def open_rom(req):
    info = state.open_rom_bytes(req.body, req.query.get("name"))
    return {"rom": info, "boards": state.boards_info()}


@route("POST", "/api/rom/close")
def close_rom(req):
    state.close_rom()
    return {"boards": state.boards_info()}


@route("POST", "/api/rom/save")
def save_rom(req):
    data, name = state.save_rom()
    return Response(data, "application/octet-stream", filename=name)


@route("POST", "/api/rom/overwrite")
def overwrite(req):
    index = req.arg("romBoardIndex")
    if isinstance(index, str) and index.lstrip("-").isdigit():
        index = int(index)
    if not isinstance(index, int) or isinstance(index, bool):
        raise ApiError("Which ROM board? (romBoardIndex)")
    return {"boards": state.overwrite_rom_board(index)}
