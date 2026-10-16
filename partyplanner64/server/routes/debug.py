"""Debug tools (apps/partyplanner64/views/debug.tsx and packages/lib/utils/dump.ts).

The original printed to the browser's console; here the tools answer text that
the Debug page shows in its console, or files to download.

    GET  /api/debug/dump                    -> mpN-files.zip: every MainFS file (dump.create)
    POST /api/debug/dump                    a .zip as made above: writes its files back (dump.load)
    GET  /api/debug/images                  -> mpN-images.zip (dump.images)
    GET  /api/debug/scenes?format=table|n64split|n64splat -> {scenes, text}
    GET  /api/debug/scenes/<i>              -> {index, info} (hex strings)
    GET  /api/debug/scenes/<i>/asm          -> {text} (printSceneAsm)
    GET  /api/debug/scenes/<i>/download     -> overlay-<i>.bin
    POST /api/debug/scenes/<i>/replace?ram_start=..&code_start=.. (hex)  the overlay's bytes
    GET  /api/debug/string?dir=<hex>&index=<hex>&raw=1 -> {text}
    GET  /api/debug/find-string?q=..&raw=1  -> {text, count}
    GET  /api/debug/rom-to-ram?offset=<hex> -> {result}
    GET  /api/debug/mainfs-to-rom?dir=<n>&file=<n> -> {result}
    GET  /api/debug/asm?start=<hex>&end=<hex> -> {text} (printAsm)
"""

import io
import re
import zipfile

from ..http import ApiError, Response, route

SCENE_FIELDS = ("rom_start", "rom_end", "ram_start", "code_start", "code_end",
                "rodata_start", "rodata_end", "bss_start", "bss_end")
MAX_ASM_WORDS = 0x10000

def _state_lock():
    """The app's lock (state.lock): held while changing the ROM."""
    from ... import state
    return state.lock



def _romhandler():
    from ...lib.romhandler import romhandler
    return romhandler


def _rom():
    rom = _romhandler().get_rom()
    if rom is None:
        raise ApiError("Open a ROM first.", 409)
    return rom


def hexstr(num, prefix="0x"):
    from ...lib.utils.debug import hexstr as _hex
    return _hex(num, prefix)


def _pad(text, length, char="0"):
    return text.rjust(length, char)


def _parse_int(value, base, name):
    try:
        return int(str(value).strip(), base)
    except (TypeError, ValueError):
        raise ApiError("%s must be a %s number." % (name, "hexadecimal" if base == 16 else "whole"))


def _game_version():
    return _romhandler().get_game_version()


def _form_cls():
    from ...lib.models.form import FORM
    return FORM


def _mtnx_cls():
    from ...lib.models.mtnx import MTNX
    return MTNX


def _png(rgba, width, height):
    from .sprites import png_bytes
    return png_bytes(bytes(rgba), width, height)


# File dumps (dump.create, dump.load, dump.images)

def create_dump():
    """Every MainFS file in a zip: mainfs/<dir>/<file>[.form|.mtnx]."""
    mainfs = _rom().get_main_fs()
    try:
        FORM, MTNX = _form_cls(), _mtnx_cls()
    except ImportError:
        FORM = MTNX = None
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in range(mainfs.get_directory_count()):
            z.writestr("mainfs/%d/" % d, b"")
            for f in range(mainfs.get_file_count(d)):
                data = bytes(mainfs.get(d, f))
                name = str(f)
                if FORM and FORM.is_form(data):
                    name += ".form"
                elif MTNX and MTNX.is_mtnx(data):
                    name += ".mtnx"
                z.writestr("mainfs/%d/%s" % (d, name), data)
    return out.getvalue()


def load_dump(zip_bytes):
    """Write the files of a dump back into the MainFS. Returns the list of d/f written."""
    mainfs = _rom().get_main_fs()
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ApiError("Something went wrong while loading the zip. %s" % e)
    written = []
    with z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith("mainfs/"):
                continue
            m = re.search(r"(\d+)/(\d+)", info.filename[len("mainfs/"):])
            if not m:
                continue
            d, f = int(m.group(1)), int(m.group(2))
            mainfs.write(d, f, bytearray(z.read(info)))
            written.append("%d/%d" % (d, f))
    return written


def create_images_zip():
    """The ROM's images as PNGs (dump.images): FORM bitmaps, font packs, image packs."""
    from ...lib.utils.img.img_pack import img_info_src_to_array_buffer
    from . import sprites
    sheet_png = sprites.sheet_png
    rh = _romhandler()
    game = rh.get_rom_game()
    mainfs = _rom().get_main_fs()
    try:
        FORM = _form_cls()
    except ImportError:
        FORM = None
    try:
        from ...lib.utils.img import font_pack
    except ImportError:
        font_pack = None
    out = io.BytesIO()
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in range(mainfs.get_directory_count()):
            folder = "mainfs/%d/" % d
            for f in range(mainfs.get_file_count(d)):
                try:
                    buf = mainfs.get(d, f)
                    if FORM is not None and FORM.is_form(buf):
                        try:
                            form = FORM.unpack(buf)
                            for idx, entry in enumerate(_form_bitmaps(form)):
                                z.writestr("%s%d.%d.png" % (folder, f, idx),
                                           _png(entry["src"], entry["width"], entry["height"]))
                                count += 1
                        except Exception:  # noqa: BLE001
                            pass
                        continue
                    if font_pack is not None and ((d == 0 and font_pack.is_font_pack(buf))
                                                  or font_pack.is_known_font_pack(game, d, f)):
                        pack = None
                        try:
                            pack = font_pack.font_pack_to_rgba32(buf)
                        except Exception:  # noqa: BLE001
                            pass
                        if pack:
                            w, h = pack["char_width"], pack["char_height"]
                            imgs = list(pack["chars"]) + list(pack["images"])
                            for idx, img in enumerate(imgs):
                                z.writestr("%s%d.%d.png" % (folder, f, idx), _png(img, w, h))
                                count += 1
                            if imgs:
                                z.writestr("%s%d.all.png" % (folder, f), sheet_png(
                                    [{"src": i, "width": w, "height": h} for i in imgs]))
                            continue
                    imgs = sprites._from_pack(buf)
                    for idx, info in enumerate(imgs or []):
                        z.writestr("%s%d.%d.png" % (folder, f, idx), _png(
                            img_info_src_to_array_buffer(info["src"]), info["width"], info["height"]))
                        count += 1
                    if imgs and len(imgs) > 1:
                        z.writestr("%s%d.all.png" % (folder, f), sheet_png(imgs))
                except Exception:  # noqa: BLE001 - not an image
                    pass
    return out.getvalue(), count


def _form_bitmaps(form):
    """The parsed BMP1 entries of a FORM: [{src, width, height}]."""
    entries = form.get("BMP1") if isinstance(form, dict) else getattr(form, "BMP1", None)
    out = []
    for entry in entries or []:
        parsed = entry.get("parsed") if isinstance(entry, dict) else getattr(entry, "parsed", None)
        if parsed:
            out.append(parsed)
    return out


# Scenes (overlays)

def _scenes():
    return _rom().get_scenes()


def _scene_info(i):
    scenes = _scenes()
    info = scenes.get_info(i)
    if info is None:
        raise ApiError("There is no scene %d (the ROM has %d)." % (i, scenes.count()), 404)
    return info


def scene_table_text(fmt="table"):
    scenes = _scenes()
    infos = [scenes.get_info(i) for i in range(scenes.count())]
    lines = []
    if fmt == "n64split":
        for i, info in enumerate(infos):
            lines.append('   - [%s, %s, "asm", "overlay%d_main", %s]' % (
                hexstr(info["rom_start"]),
                hexstr(info["rom_start"] + (info["code_end"] - info["code_start"])), i,
                hexstr(info["code_start"])))
            lines.append('   - [%s, %s, "bin", "overlay%d_rodata_bin"]' % (
                hexstr(info["rom_start"] + (info["rodata_start"] - info["code_start"])),
                hexstr(info["rom_start"] + (info["rodata_end"] - info["code_start"])), i))
            lines.append("   # overlay%d bss: %s - %s" % (i, hexstr(info["bss_start"]),
                                                        hexstr(info["bss_end"])))
    elif fmt == "n64splat":
        for i, info in enumerate(infos):
            lines += ["  - name: overlay%d" % i, "    type: code", "    overlay: True",
                      "    start: %s" % hexstr(info["rom_start"]),
                      "    vram: %s" % hexstr(info["code_start"]), "    files:",
                      '      - [%s, "asm"]' % hexstr(info["rom_start"]),
                      '      - [%s, "bin"] # rodata' % hexstr(
                          info["rom_start"] + (info["rodata_start"] - info["code_start"])),
                      ""]
    else:
        header = ["i"] + list(SCENE_FIELDS)
        rows = [[hexstr(i)] + [hexstr(info[k]) for k in SCENE_FIELDS] for i, info in enumerate(infos)]
        widths = [max(len(h), *(len(r[c]) for r in rows)) if rows else len(h)
                  for c, h in enumerate(header)]
        lines.append("  ".join(h.ljust(widths[c]) for c, h in enumerate(header)))
        for r in rows:
            lines.append("  ".join(v.ljust(widths[c]) for c, v in enumerate(r)))
    return infos, "\n".join(lines)


def _mips_print(value):
    from ...lib.mips import print as mips_print
    return mips_print(value)


def _disassemble(view, start_addr, length):
    insts = []
    addr = start_addr
    for i in range(0, length - length % 4, 4):
        value = view.get_uint32(i)
        try:
            asm = _mips_print(value)
        except Exception:  # noqa: BLE001
            asm = "? " + hexstr(value)
        insts.append(hexstr(addr) + ": " + asm)
        addr += 4
    return insts


def scene_asm_text(i):
    """printSceneAsm: the code, the rodata words and the bss of overlay i."""
    info = _scene_info(i)
    scenes = _scenes()
    code = scenes.get_code_data_view(i)
    parts = ["\n".join(_disassemble(code, info["code_start"], code.byte_length))]
    ro = scenes.get_ro_data_view(i)
    lines = []
    addr = info["rodata_start"]
    pos = 0
    while pos < ro.byte_length:
        for k in range(4):
            if pos + k * 4 + 4 <= ro.byte_length:
                word = ro.get_uint32(pos + k * 4)
            else:
                word = 0
            lines.append("D_" + hexstr(addr + k * 4, "") + ": " + _pad(hexstr(word, ""), 8))
        addr += 16
        pos += 16
    parts.append("\n".join(lines))
    parts.append("\n".join("D_%s: .word 0" % hexstr(b, "")
                           for b in range(info["bss_start"], info["bss_end"], 4)))
    return "\n".join(parts)


# Offsets

def rom_to_ram_text(num):
    """onRomToRamClick: an overlay offset, else a MainFS file offset, else rom_to_ram."""
    from ...lib.utils.offsets import rom_to_ram
    scenes = _scenes()
    for i in range(scenes.count()):
        info = scenes.get_info(i)
        if info["rom_start"] <= num <= info["rom_end"]:
            diff = num - info["rom_start"]
            return ("RAM: %s\nOverlay %d (%s) offset +%d (+%s)"
                    % (hexstr(info["ram_start"] + diff, ""), i, hexstr(i), diff, hexstr(diff)))
    result = _find_in_mainfs(num)
    if result:
        return result
    if num >= 0x1000:
        return "RAM: %s" % hexstr(rom_to_ram(num))
    return "Unknown"


def _write_decompressed():
    from ... import state
    return bool(state.get_setting("write.decompressed"))


def _find_in_mainfs(num):
    mainfs = _rom().get_main_fs()
    offset = mainfs.get_rom_offset()
    if offset is None:
        return ""
    size = mainfs.get_byte_length(_write_decompressed())
    if offset < num < offset + size:
        current = offset
        for d in range(mainfs.get_directory_count()):
            for f in range(mainfs.get_file_count(d)):
                compressed = mainfs.get_compressed_size(d, f)
                current += compressed
                if current > num:
                    diff = num - (current - compressed)
                    return ("RAM: N/A\nMainFS %d/%d (%s/%s) offset +%d (+%s)"
                            % (d, f, hexstr(d), hexstr(f), diff, hexstr(diff)))
    return ""


def mainfs_to_rom_text(dir, file):
    """onMainFSToRomClick: where MainFS dir/file starts in the ROM."""
    from ...lib.utils.number import make_divisible_by
    mainfs = _rom().get_main_fs()
    current = mainfs.get_rom_offset()
    if current is None:
        return "Unknown"
    dir_count = mainfs.get_directory_count()
    current += 4 + 4 * dir_count  # Count of directories, directory offsets
    for d in range(dir_count):
        file_count = mainfs.get_file_count(d)
        current += 4 + 4 * file_count  # Count of files, file offsets
        for f in range(file_count):
            current += mainfs.get_file_header_size(d, f)
            if d == dir and f == file:
                return "ROM: %s" % hexstr(current)
            current += mainfs.get_compressed_size(d, f)
            current = make_divisible_by(current, 2)
    return "Unknown"


# Routes

@route("GET", "/api/debug/dump")
def get_dump(req):
    return Response(create_dump(), "application/zip", filename="mp%s-files.zip" % _game_version())


@route("POST", "/api/debug/dump")
def post_dump(req):
    if not req.body:
        raise ApiError("Send a .zip made by Export File Dump.")
    with _state_lock():
        written = load_dump(req.body)
    return {"written": len(written), "files": written}


@route("GET", "/api/debug/images")
def get_images(req):
    data, count = create_images_zip()
    return Response(data, "application/zip", filename="mp%s-images.zip" % _game_version(),
                    headers=[("X-Image-Count", str(count))])


@route("GET", "/api/debug/scenes")
def get_scene_table(req):
    fmt = req.query.get("format", "table")
    if fmt not in ("table", "n64split", "n64splat"):
        raise ApiError("Unknown format %s (table, n64split or n64splat)." % fmt)
    infos, text = scene_table_text(fmt)
    return {"count": len(infos), "format": fmt, "text": text,
            "scenes": [{k: info[k] for k in SCENE_FIELDS} for info in infos]}


@route("GET", "/api/debug/scenes/<int:i>")
def get_scene(req, i):
    info = _scene_info(i)
    return {"index": i, "info": {k: hexstr(info[k], "") for k in SCENE_FIELDS}}


@route("GET", "/api/debug/scenes/<int:i>/asm")
def get_scene_asm(req, i):
    return {"index": i, "text": scene_asm_text(i)}


@route("GET", "/api/debug/scenes/<int:i>/download")
def download_scene(req, i):
    _scene_info(i)
    view = _scenes().get_data_view(i)
    data = bytes(view.buffer[view.byte_offset:view.byte_offset + view.byte_length]) \
        if hasattr(view, "buffer") else bytes(view)
    return Response(data, "application/octet-stream", filename="overlay-%d.bin" % i)


@route("POST", "/api/debug/scenes/<int:i>/replace")
def replace_scene(req, i):
    _scene_info(i)
    if not req.body:
        raise ApiError("Send the overlay's bytes.")
    values = {}
    for k in SCENE_FIELDS[2:]:
        if req.query.get(k):
            values[k] = _parse_int(req.query[k], 16, k)
    with _state_lock():
        _scenes().replace(i, bytearray(req.body), values)
    return {"index": i, "size": len(req.body)}


@route("GET", "/api/debug/string")
def get_debug_string(req):
    index = _parse_int(req.query.get("index", ""), 16, "The index")
    raw = req.query.get("raw") in ("1", "true")
    rom = _rom()
    if _game_version() == 3:
        d = _parse_int(req.query.get("dir", ""), 16, "The directory")
        result = rom.get_strings3().read("en", d, index, raw)
        where = "%s/%s" % (hexstr(d), hexstr(index))
    else:
        result = rom.get_strings().read(index, raw)
        where = hexstr(index)
    if raw:
        data = bytes(result)
        text = "\n".join(" ".join("%02X" % b for b in data[o:o + 16]) for o in range(0, len(data), 16))
    else:
        text = result
    return {"where": where, "text": text}


@route("GET", "/api/debug/find-string")
def find_string(req):
    from .strings import search
    raw = req.query.get("raw") in ("1", "true")
    results = search(req.query.get("q", ""), "en", raw)
    blocks = []
    for r in results:
        where = ("%d/%d (%s/%s)" % (r["dir"], r["index"], hexstr(r["dir"]), hexstr(r["index"]))
                 if r["dir"] is not None else "%d (%s)" % (r["index"], hexstr(r["index"])))
        block = where + ":\n" + r["text"]
        if raw:
            block += "\n" + r.get("raw", "")
        blocks.append(block)
    return {"count": len(results), "text": "\n\n".join(blocks)}


@route("GET", "/api/debug/rom-to-ram")
def rom_to_ram_route(req):
    num = _parse_int(req.query.get("offset", ""), 16, "The ROM offset")
    return {"offset": num, "result": rom_to_ram_text(num)}


@route("GET", "/api/debug/mainfs-to-rom")
def mainfs_to_rom_route(req):
    d = _parse_int(req.query.get("dir", ""), 10, "The directory")
    f = _parse_int(req.query.get("file", ""), 10, "The file")
    return {"dir": d, "file": f, "result": mainfs_to_rom_text(d, f)}


@route("GET", "/api/debug/asm")
def print_asm(req):
    start = _parse_int(req.query.get("start", ""), 16, "The start")
    end = _parse_int(req.query.get("end", ""), 16, "The end")
    if end < start:
        raise ApiError("The end is before the start.")
    if (end - start) // 4 > MAX_ASM_WORDS:
        raise ApiError("That's more than %d instructions; pick a smaller range." % MAX_ASM_WORDS)
    rh = _romhandler()
    view = rh.get_data_view()
    insts = []
    cur = start
    while cur <= end and cur + 4 <= view.byte_length:
        value = view.get_uint32(cur)
        try:
            asm = _mips_print(value)
        except Exception:  # noqa: BLE001
            asm = "? " + hexstr(value)
        insts.append(hexstr(cur) + ": " + asm)
        cur += 4
    return {"text": "\n".join(insts)}
