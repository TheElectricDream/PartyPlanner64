"""Sprites: the image packs in the ROM's MainFS (apps/partyplanner64/views/sprites.tsx).

A MainFS file is a sprite if it unpacks as an ImgPack (utils/img/ImgPack.fromPack);
finding them reads every file, so the list is kept until the ROM changes.

    GET /api/sprites                        -> {sprites: [{dir, file, frames, width, height}]}
    GET /api/sprites/<dir>/<file>           -> {dir, file, frames: [{index, width, height, url}]}
    GET /api/sprites/<dir>/<file>/<i>.png   -> one frame (?download=1 to save it)
    GET /api/sprites/<dir>/<file>/sheet.png -> every frame side by side
    GET /api/sprites/<dir>/<file>/zip       -> every frame, as PNGs in a .zip
"""

import io
import threading
import zipfile
from collections import OrderedDict

from ..http import ApiError, Response, route

_lock = threading.Lock()
_list_cache = {}            # rom key -> [sprite summary]
_frame_cache = OrderedDict()  # (rom key, dir, file) -> [img info]
FRAME_CACHE_SIZE = 32


def _romhandler():
    from ...lib.romhandler import romhandler
    return romhandler


def _mainfs():
    rom = _romhandler().get_rom()
    if rom is None:
        raise ApiError("Open a ROM first.", 409)
    mainfs = rom.get_main_fs()
    return (id(rom), id(mainfs)), mainfs


def _from_pack(buffer):
    from ...lib.utils.img.img_pack import from_pack
    return from_pack(buffer)


def _src_bytes(info):
    from ...lib.utils.img.img_pack import img_info_src_to_array_buffer
    return bytes(img_info_src_to_array_buffer(info["src"]))


def read_imgs(mainfs, d, f):
    """The images of MainFS d/f if it is an ImgPack, else None (as _readImgsFromMainFS)."""
    imgs = _from_pack(mainfs.get(d, f))
    if not imgs:
        return None
    return imgs


def list_sprites(mainfs):
    """Every ImgPack in the MainFS: [{dir, file, frames, width, height}]."""
    out = []
    for d in range(mainfs.get_directory_count()):
        for f in range(mainfs.get_file_count(d)):
            try:
                imgs = read_imgs(mainfs, d, f)
            except Exception:  # noqa: BLE001 - not an ImgPack
                continue
            if imgs:
                out.append({"dir": d, "file": f, "frames": len(imgs),
                            "width": imgs[0]["width"], "height": imgs[0]["height"]})
    return out


def _frames(d, f):
    key, mainfs = _mainfs()
    ck = (key, d, f)
    with _lock:
        if ck in _frame_cache:
            _frame_cache.move_to_end(ck)
            return _frame_cache[ck]
    if not (0 <= d < mainfs.get_directory_count() and 0 <= f < mainfs.get_file_count(d)):
        raise ApiError("There is no MainFS file %d/%d." % (d, f), 404)
    try:
        imgs = read_imgs(mainfs, d, f)
    except Exception:  # noqa: BLE001
        imgs = None
    if not imgs:
        raise ApiError("MainFS %d/%d is not a sprite (an image pack)." % (d, f), 404)
    with _lock:
        _frame_cache[ck] = imgs
        while len(_frame_cache) > FRAME_CACHE_SIZE:
            _frame_cache.popitem(last=False)
    return imgs


MAX_PIXELS = 4096 * 4096


def _rgba_exact(rgba, width, height):
    """width x height x 4 bytes: rgba cut, or padded with transparent pixels."""
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise ApiError("The image's size (%d x %d) can't be right." % (width, height))
    data = bytes(rgba[:width * height * 4])
    return data + bytes(width * height * 4 - len(data))


def png_bytes(rgba, width, height):
    """RGBA32 bytes as a PNG."""
    from PIL import Image
    img = Image.frombytes("RGBA", (width, height), _rgba_exact(rgba, width, height))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def sheet_png(imgs):
    """The frames side by side (as dump.images's .all.png), as a PNG."""
    from PIL import Image
    width = sum(i["width"] for i in imgs)
    if width * max(i["height"] for i in imgs) > MAX_PIXELS:
        raise ApiError("The sprite sheet would be too large.")
    height = max(i["height"] for i in imgs)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for info in imgs:
        w, h = info["width"], info["height"]
        sheet.paste(Image.frombytes("RGBA", (w, h), _rgba_exact(_src_bytes(info), w, h)), (x, 0))
        x += w
    out = io.BytesIO()
    sheet.save(out, "PNG")
    return out.getvalue()


@route("GET", "/api/sprites")
def get_sprites(req):
    key, mainfs = _mainfs()
    with _lock:
        cached = _list_cache.get(key)
    if cached is None:
        cached = list_sprites(mainfs)
        with _lock:
            _list_cache.clear()
            _list_cache[key] = cached
    return {"sprites": cached}


@route("GET", "/api/sprites/<int:d>/<int:f>")
def get_sprite(req, d, f):
    imgs = _frames(d, f)
    return {"dir": d, "file": f, "frames": [
        {"index": i, "width": info["width"], "height": info["height"],
         "url": "/api/sprites/%d/%d/%d.png" % (d, f, i)} for i, info in enumerate(imgs)]}


@route("GET", "/api/sprites/<int:d>/<int:f>/<int:i>.png")
def get_frame_png(req, d, f, i):
    imgs = _frames(d, f)
    if not 0 <= i < len(imgs):
        raise ApiError("Sprite %d/%d has no frame %d." % (d, f, i), 404)
    info = imgs[i]
    name = "sprite-%d-%d-%d.png" % (d, f, i) if req.query.get("download") else None
    return Response(png_bytes(_src_bytes(info), info["width"], info["height"]), "image/png",
                    filename=name)


@route("GET", "/api/sprites/<int:d>/<int:f>/sheet.png")
def get_sheet_png(req, d, f):
    name = "sprite-%d-%d-sheet.png" % (d, f) if req.query.get("download") else None
    return Response(sheet_png(_frames(d, f)), "image/png", filename=name)


@route("GET", "/api/sprites/<int:d>/<int:f>/zip")
def get_sprite_zip(req, d, f):
    imgs = _frames(d, f)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for i, info in enumerate(imgs):
            z.writestr("%d.%d.%d.png" % (d, f, i),
                       png_bytes(_src_bytes(info), info["width"], info["height"]))
        if len(imgs) > 1:
            z.writestr("%d.%d.all.png" % (d, f), sheet_png(imgs))
    return Response(out.getvalue(), "application/zip", filename="sprite-%d-%d.zip" % (d, f))
