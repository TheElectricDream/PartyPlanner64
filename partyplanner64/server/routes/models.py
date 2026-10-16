"""Models: the ROM's 3D models (FORM files) and animations (MTNX files) in the
MainFS (apps/partyplanner64/views/models.tsx).

The browser converted FORMs to three.js objects (models/FormToThreeJs.ts); here
the server converts them to a scene description (partyplanner64.lib.models)
that js/lib/model3d.js builds into three.js objects, and exports glTF/GLB/OBJ.

    GET /api/models                     -> {models: [{dir, file}], first: {dir, file} | null}
    GET /api/models/animations?dir=<d>  -> {animations: [{dir, file}]} (every MTNX, or dir d's)
    GET /api/models/<d>/<f>             -> the scene (form_to_scene; options
        ?textures=0&wireframe=1&normals=1&camera=1&bg=FFFFFF)
    GET /api/models/<d>/<f>/animation/<ad>/<af> -> the animation for that model
    GET /api/models/<d>/<f>/export?format=gltf|glb|obj -> the file (format defaults to
        models.useGLB: glb or gltf)
"""

import inspect
import importlib
import json
import threading

from ..http import ApiError, Response, route

_lock = threading.Lock()
_lists = {}     # rom key -> {"models": [...], "animations": [...]}


def _romhandler():
    from ...lib.romhandler import romhandler
    return romhandler


def _mainfs():
    rom = _romhandler().get_rom()
    if rom is None:
        raise ApiError("Open a ROM first.", 409)
    mainfs = rom.get_main_fs()
    return (id(rom), id(mainfs)), mainfs


def _form_cls():
    from ...lib.models.form import FORM
    return FORM


def _mtnx_cls():
    from ...lib.models.mtnx import MTNX
    return MTNX


def _lib(name):
    """A function of C's partyplanner64.lib.models, wherever it ended up."""
    for mod in ("...lib.models", "...lib.models.scene", "...lib.models.form_to_scene",
                "...lib.models.form_to_three_js", "...lib.models.mtnx_to_animation",
                "...lib.models.mtnx_to_three_js", "...lib.models.gltf", "...lib.models.export",
                "...lib.models.obj"):
        try:
            m = importlib.import_module(mod, __package__)
        except ImportError:
            continue
        fn = getattr(m, name, None)
        if fn:
            return fn
    raise ApiError("This installation can't convert models yet (%s is missing)." % name, 501)


def _call(fn, *args, **opts):
    """Call fn with the keyword options it accepts."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(*args)
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return fn(*args, **opts)
    return fn(*args, **{k: v for k, v in opts.items() if k in params})


def _scan():
    """Every FORM and MTNX in the MainFS (kept until the ROM changes)."""
    key, mainfs = _mainfs()
    with _lock:
        if key in _lists:
            return _lists[key]
    FORM, MTNX = _form_cls(), _mtnx_cls()
    models, animations = [], []
    for d in range(mainfs.get_directory_count()):
        for f in range(mainfs.get_file_count(d)):
            try:
                buf = mainfs.get(d, f)
            except Exception:  # noqa: BLE001
                continue
            if FORM.is_form(buf):
                models.append({"dir": d, "file": f})
            elif MTNX.is_mtnx(buf):
                animations.append({"dir": d, "file": f})
    result = {"models": models, "animations": animations}
    with _lock:
        _lists.clear()
        _lists[key] = result
    return result


def _file(d, f):
    _, mainfs = _mainfs()
    if not (0 <= d < mainfs.get_directory_count() and 0 <= f < mainfs.get_file_count(d)):
        raise ApiError("There is no MainFS file %d/%d." % (d, f), 404)
    return mainfs.get(d, f)


def _form(d, f):
    buf = _file(d, f)
    FORM = _form_cls()
    if not FORM.is_form(buf):
        raise ApiError("MainFS %d/%d is not a model (FORM)." % (d, f), 404)
    form = FORM.unpack(buf)
    if not form:
        raise ApiError("Model %d/%d couldn't be read." % (d, f))
    return form


def _mtnx(d, f):
    buf = _file(d, f)
    MTNX = _mtnx_cls()
    if not MTNX.is_mtnx(buf):
        raise ApiError("MainFS %d/%d is not an animation (MTNX)." % (d, f), 404)
    mtnx = MTNX.unpack(buf)
    if not mtnx:
        raise ApiError("Animation %d/%d couldn't be read." % (d, f))
    return mtnx


def _flag(req, name, default):
    value = req.query.get(name)
    if value is None:
        return default
    return value not in ("0", "false", "no", "")


def _setting(name):
    from ... import state
    return state.get_setting(name)


@route("GET", "/api/models")
def get_models(req):
    lists = _scan()
    models = lists["models"]
    # The original starts at directory 2, so it's Mario.
    first = next((m for m in models if m["dir"] >= 2), models[0] if models else None)
    return {"models": models, "first": first}


@route("GET", "/api/models/animations")
def get_animations(req):
    anims = _scan()["animations"]
    d = req.query.get("dir")
    if d not in (None, ""):
        try:
            d = int(d)
        except ValueError:
            raise ApiError("dir must be a number.")
        anims = [a for a in anims if a["dir"] == d]
    return {"animations": anims}


@route("GET", "/api/models/<int:d>/<int:f>")
def get_model(req, d, f):
    form = _form(d, f)
    try:
        bg = int(req.query.get("bg") or "0", 16) & 0xFFFFFF
    except ValueError:
        raise ApiError("bg is a colour in hexadecimal, e.g. FFFFFF.")
    scene = _call(_lib("form_to_scene"), form, bg_color=bg,
                  show_textures=_flag(req, "textures", True),
                  show_wireframe=_flag(req, "wireframe", False),
                  show_vertex_normals=_flag(req, "normals", False),
                  use_form_camera=_flag(req, "camera", False))
    if isinstance(scene, (bytes, bytearray)):
        return Response(scene, "application/json")
    if isinstance(scene, dict):
        scene.setdefault("dir", d)
        scene.setdefault("file", f)
    return scene


@route("GET", "/api/models/<int:d>/<int:f>/animation/<int:ad>/<int:af>")
def get_animation(req, d, f, ad, af):
    form = _form(d, f)
    mtnx = _mtnx(ad, af)
    anim = _call(_lib("mtnx_to_animation"), mtnx, form)
    if isinstance(anim, dict):
        anim.setdefault("dir", ad)
        anim.setdefault("file", af)
    return anim


@route("GET", "/api/models/<int:d>/<int:f>/export")
def export_model(req, d, f):
    fmt = (req.query.get("format") or "").lower()
    if not fmt:
        fmt = "glb" if _setting("models.useGLB") else "gltf"
    if fmt not in ("gltf", "glb", "obj"):
        raise ApiError("Unknown model format: %s (gltf, glb or obj)." % fmt)
    form = _form(d, f)
    name = "model-%d-%d" % (d, f)
    if fmt == "obj":
        try:
            export = _lib("form_to_obj")
            result = _call(export, form)
        except ApiError:
            scene = _call(_lib("form_to_scene"), form)
            result = _call(_lib("scene_to_obj"), scene)
        if isinstance(result, dict):
            # {"obj": text, "mtl": text, "textures": {name: png bytes}} -> a .zip
            import io
            import zipfile
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(name + ".obj", result.get("obj", ""))
                if result.get("mtl"):
                    z.writestr(name + ".mtl", result["mtl"])
                for tex_name, data in (result.get("textures") or {}).items():
                    z.writestr(tex_name, data)
            return Response(out.getvalue(), "application/zip", filename=name + ".zip")
        return Response(result, "text/plain; charset=utf-8", filename=name + ".obj")
    scene = _call(_lib("form_to_scene"), form)
    binary = fmt == "glb"
    result = _call(_lib("scene_to_gltf"), scene, binary=binary)
    if binary:
        return Response(bytes(result), "model/gltf-binary", filename=name + ".glb")
    if not isinstance(result, (bytes, bytearray, str)):
        result = json.dumps(result)
    return Response(result, "model/gltf+json", filename=name + ".gltf")
