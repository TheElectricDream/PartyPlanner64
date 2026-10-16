"""ROM file dumps and console debugging helpers (port of utils/dump.ts).

The advanced "dump" feature packs all of the individual filesystem
contents into a zip file. You can edit the zipped contents and import them,
and your changes will be blindly applied to the ROM.

The zip files are built with zipfile and returned as bytes (the TypeScript
handed a Blob to a callback or to file-saver). The helpers that printed to
the browser console return their text instead.
"""

import io
import re
import zipfile

from .arrays import array_buffer_to_data_url, to_hex_string
from .canvas import data_url_to_bytes
from .debug import hexstr, log
from .img.font_pack import font_pack_to_rgba32, is_font_pack, is_known_font_pack
from .img.img_pack import from_pack, img_info_src_to_array_buffer, img_info_src_to_data_view
from .img.tiler import from_tiles
from .string import pad


def _romhandler():
    from ..romhandler import romhandler
    return romhandler


def _form_class():
    from ..models.form import FORM
    return FORM


def _mtnx_class():
    from ..models.mtnx import MTNX
    return MTNX


def _field(obj, *names):
    """Read a field of a dict or object, trying several spellings."""
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            return getattr(obj, name)
    return None


def _form_bitmaps(form_unpacked):
    """The parsed BMP1 entries of an unpacked FORM: (src, width, height)."""
    entries = _field(form_unpacked, "BMP1", "bmp1") or []
    result = []
    for entry in entries:
        parsed = _field(entry, "parsed")
        result.append((_field(parsed, "src"), _field(parsed, "width"), _field(parsed, "height")))
    return result


def _zip_bytes(files):
    """Return a zip of {path: bytes} (folders implied by the paths)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in files.items():
            if path.endswith("/"):
                zf.mkdir(path)  # A folder, as JSZip's zip.folder() made.
            else:
                zf.writestr(path, bytes(data))
    return out.getvalue()


def _png_bytes(data_url):
    return data_url_to_bytes(data_url)


def create(callback=None):
    """Return a zip (bytes) of every MainFS file: mainfs/<dir>/<file>[.form|.mtnx].

    If a callback is given, it is called with the bytes too.
    """
    FORM = _form_class()
    MTNX = _mtnx_class()
    files = {"mainfs/": b""}
    mainfs = _romhandler().get_rom().get_main_fs()
    mainfs_dir_count = mainfs.get_directory_count()
    for d in range(mainfs_dir_count):
        files["mainfs/%d/" % d] = b""
        dir_file_count = mainfs.get_file_count(d)
        for f in range(dir_file_count):
            file = mainfs.get(d, f)
            name = str(f)
            if FORM.is_form(file):
                name += ".form"
            elif MTNX.is_mtnx(file):
                name += ".mtnx"
            files["mainfs/%d/%s" % (d, name)] = file
    data = _zip_bytes(files)
    if callback:
        callback(data)
    return data


def load(buffer, on_error=None):
    """Write the files of a dump zip (as made by create) back into the MainFS."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(bytes(buffer)))
    except Exception as error:  # noqa: BLE001 - reported like the JSZip error
        if on_error:
            on_error(error)
        return
    with zf:
        for info in zf.infolist():
            if not info.filename.startswith("mainfs/") or info.is_dir():
                continue
            relative_path = info.filename[len("mainfs/"):]
            match = re.search(r"(\d+)/(\d+)", relative_path)
            if not match:
                continue
            d = int(match.group(1))
            f = int(match.group(2))
            content = bytearray(zf.read(info))
            log("Overwriting MainFS %d/%d" % (d, f))
            mainfs = _romhandler().get_rom().get_main_fs()
            mainfs.write(d, f, content)


def images():
    """Return a zip (bytes) of every image found in the MainFS.

    (Called via the console as dump.images() in the TypeScript, which saved
    it as mp<version>-images.zip; images_file_name() gives that name.)
    """
    FORM = _form_class()
    files = {"mainfs/": b""}

    game = _romhandler().get_rom_game()

    mainfs = _romhandler().get_rom().get_main_fs()

    def _read_packed_from_main_fs(dir, file):
        img_arr = from_pack(mainfs.get(dir, file))
        if not img_arr:
            return None
        return [img_info_src_to_data_view(img_info["src"]) for img_info in img_arr]

    def _read_imgs_from_main_fs(dir, file):
        img_arr = from_pack(mainfs.get(dir, file))
        if not img_arr:
            return None
        return img_arr

    mainfs_dir_count = mainfs.get_directory_count()
    for d in range(mainfs_dir_count):
        folder = "mainfs/%d/" % d
        files[folder] = b""
        dir_file_count = mainfs.get_file_count(d)
        for f in range(dir_file_count):
            try:
                file_buffer = mainfs.get(d, f)
                if FORM.is_form(file_buffer):
                    try:
                        form_unpacked = FORM.unpack(file_buffer)
                        for idx, (src, width, height) in enumerate(_form_bitmaps(form_unpacked)):
                            data_uri = array_buffer_to_data_url(src, width, height)
                            files["%s%d.%d.png" % (folder, f, idx)] = _png_bytes(data_uri)
                    except Exception:  # noqa: BLE001
                        pass
                    continue

                if (d == 0 and is_font_pack(file_buffer)) or is_known_font_pack(game, d, f):
                    font_pack = None
                    try:
                        font_pack = font_pack_to_rgba32(file_buffer)
                    except Exception:  # noqa: BLE001
                        pass

                    if font_pack:
                        char_width = font_pack["char_width"]
                        char_height = font_pack["char_height"]
                        idx = 0
                        for char_img in font_pack["chars"]:
                            data_uri = array_buffer_to_data_url(char_img, char_width, char_height)
                            files["%s%d.%d.png" % (folder, f, idx)] = _png_bytes(data_uri)
                            idx += 1
                        for img in font_pack["images"]:
                            data_uri = array_buffer_to_data_url(img, char_width, char_height)
                            files["%s%d.%d.png" % (folder, f, idx)] = _png_bytes(data_uri)
                            idx += 1

                        data_views = font_pack["chars"] + font_pack["images"]
                        tiles_buf = from_tiles(data_views, len(data_views), 1, char_width * 4, char_height)
                        tiles_url = array_buffer_to_data_url(
                            tiles_buf, char_width * len(data_views), char_height)
                        files["%s%d.all.png" % (folder, f)] = _png_bytes(tiles_url)
                        continue

                # Maybe an ImgPack?
                imgs = _read_imgs_from_main_fs(d, f)
                for idx, img_info in enumerate(imgs):
                    data_uri = array_buffer_to_data_url(
                        img_info_src_to_array_buffer(img_info["src"]), img_info["width"], img_info["height"])
                    files["%s%d.%d.png" % (folder, f, idx)] = _png_bytes(data_uri)
                if len(imgs) > 1:
                    tiles_buf = from_tiles(_read_packed_from_main_fs(d, f), len(imgs), 1,
                                           imgs[0]["width"] * 4, imgs[0]["height"])
                    tiles_url = array_buffer_to_data_url(
                        tiles_buf, imgs[0]["width"] * len(imgs), imgs[0]["height"])
                    files["%s%d.all.png" % (folder, f)] = _png_bytes(tiles_url)
            except Exception:  # noqa: BLE001
                pass

    return _zip_bytes(files)


def images_file_name():
    """The file name the TypeScript saved images() as."""
    return "mp%s-images.zip" % _romhandler().get_game_version()


def form_images():
    """Dump out all the FORM bitmaps: returns "<dir>/<file>:\\n<data URL>" lines."""
    FORM = _form_class()
    lines = []
    mainfs = _romhandler().get_rom().get_main_fs()
    mainfs_dir_count = mainfs.get_directory_count()
    for d in range(mainfs_dir_count):
        dir_file_count = mainfs.get_file_count(d)
        for f in range(dir_file_count):
            file_buffer = mainfs.get(d, f)
            if not FORM.is_form(file_buffer):
                continue
            try:
                form_unpacked = FORM.unpack(file_buffer)
                for src, width, height in _form_bitmaps(form_unpacked):
                    data_uri = array_buffer_to_data_url(src, width, height)
                    lines.append("%d/%d:" % (d, f))
                    lines.append(data_uri)
            except Exception:  # noqa: BLE001
                pass
    return "\n".join(lines)


def find_strings3(search_str="", raw=False):
    """Return the MP3 (en) strings containing search_str, with their indices."""
    strings3 = _romhandler().get_rom().get_strings3()
    out = []
    dir_count = strings3.get_directory_count("en")
    for d in range(dir_count):
        str_count = strings3.get_string_count("en", d)
        for s in range(str_count):
            text = strings3.read("en", d, s)
            if search_str not in text:
                continue
            entry = "%d/%d (%s/%s):\n" % (d, s, hexstr(d), hexstr(s)) + text
            if raw:
                entry += "\n" + to_hex_string(strings3.read("en", d, s, True))
            out.append(entry)
    return "\n".join(out)


def find_strings(search_str="", raw=False):
    """Return the MP1/MP2 strings containing search_str, with their indices."""
    strings = _romhandler().get_rom().get_strings()
    out = []
    str_count = strings.get_string_count()
    for s in range(str_count):
        text = strings.read(s)
        if search_str not in text:
            continue
        entry = "%d (%s):\n" % (s, hexstr(s)) + text
        if raw:
            entry += "\n" + to_hex_string(strings.read(s, True))
        out.append(entry)
    return "\n".join(out)


# (window.waluigiParts / window.daisyParts in the TypeScript.)
waluigi_parts = None
daisy_parts = None


def save_waluigi():
    global waluigi_parts
    romhandler = _romhandler()
    if romhandler.get_game_version() != 3:
        raise ValueError("Waluigi is not in game %s" % romhandler.get_game_version())

    waluigi_parts = []
    for f in range(163):
        mainfs = romhandler.get_rom().get_main_fs()
        waluigi_parts.append(mainfs.get(8, f))

    return waluigi_parts  # Just to see in console.


def write_waluigi(character=1):
    romhandler = _romhandler()
    if romhandler.get_game_version() != 1:
        raise ValueError("Waluigi cannot write to MP%s" % romhandler.get_game_version())

    if not waluigi_parts:
        raise ValueError("Need to call saveWaluigi first!")

    if len(waluigi_parts) == 163:
        # A couple animations are "extra"... not sure which but for now just cut the last two MTNX
        del waluigi_parts[158:160]

    for i, part in enumerate(waluigi_parts):
        mainfs = romhandler.get_rom().get_main_fs()
        mainfs.write(character, i, part)


def save_daisy():
    global daisy_parts
    romhandler = _romhandler()
    if romhandler.get_game_version() != 3:
        raise ValueError("Daisy is not in game %s" % romhandler.get_game_version())

    mainfs = romhandler.get_rom().get_main_fs()
    daisy_parts = [mainfs.get(9, 1), mainfs.get(9, 3)]

    return daisy_parts  # Just to see in console.


def write_daisy(character=6):
    romhandler = _romhandler()
    if romhandler.get_game_version() != 1:
        raise ValueError("Daisy cannot write to MP%s" % romhandler.get_game_version())

    if not daisy_parts:
        raise ValueError("Need to call saveDaisy first!")

    mainfs = romhandler.get_rom().get_main_fs()
    mainfs.write(character, 158, daisy_parts[0])
    mainfs.write(character, 159, daisy_parts[1])


def search_for_patch_locations(offset):
    """Helper for finding FS read locations. Returns the report text."""
    if not offset:
        raise ValueError("Please pass a ROM offset the game tries to read at runtime")

    upper = (offset & 0xFFFF0000) >> 16
    lower = offset & 0x0000FFFF

    found = 0
    lines = []

    # FIXME: Won't work once scenes are in separate data views.
    rom_view = _romhandler().get_data_view()
    upper_limit = rom_view.byte_length - 10  # Since we read ahead for every i, just stop early.
    for i in range(2, upper_limit, 2):
        val = rom_view.get_uint16(i)
        if val != upper and val + 1 != upper and val - 1 != upper:
            # Desperate times call for desperate measures (and I forget which way to +-1)
            continue

        last = None
        candidates = ([i - 8] if i > 8 else []) + ([i - 4] if i > 4 else []) + \
            [i + 2, i + 3, i + 4, i + 5, i + 6, i + 7, i + 8, i + 9, i + 10, i + 12, i + 16, i + 20]
        for candidate in candidates:
            if rom_view.get_uint16(candidate) == lower:
                last = candidate
                break
        if last is not None:
            lines.append("Found %s, %s (%d) Lower inst: %s" % (
                hexstr(i), hexstr(last), last - i, hexstr(rom_view.get_uint16(last - 2))))
            found += 1

    lines.append("Found %d possible locations" % found)
    return "\n".join(lines)


def print_scene_table():
    """Return the overlay table as a list of dicts of hex strings (console.table)."""
    rom = _romhandler().get_rom()
    if not rom:
        return "ROM is not loaded"

    scenes = rom.get_scenes()
    table = []
    for i in range(scenes.count()):
        info = scenes.get_info(i)
        row = {"i": hexstr(i)}
        for key in ("rom_start", "rom_end", "ram_start", "code_start", "code_end",
                    "rodata_start", "rodata_end", "bss_start", "bss_end"):
            row[key] = hexstr(info[key])
        table.append(row)
    return table


def print_scene_n64_split():
    """Returns the overlay table in n64split format."""
    rom = _romhandler().get_rom()
    if not rom:
        return "ROM is not loaded"

    scenes = rom.get_scenes()
    strings = []
    for i in range(scenes.count()):
        info = scenes.get_info(i)
        strings.append('   - [%s, %s, "asm", "overlay%d_main", %s]' % (
            hexstr(info["rom_start"]),
            hexstr(info["rom_start"] + (info["code_end"] - info["code_start"])),
            i, hexstr(info["code_start"])))
        strings.append('   - [%s, %s, "bin", "overlay%d_rodata_bin"]' % (
            hexstr(info["rom_start"] + (info["rodata_start"] - info["code_start"])),
            hexstr(info["rom_start"] + (info["rodata_end"] - info["code_start"])), i))
        strings.append("   # overlay%d bss: %s - %s" % (i, hexstr(info["bss_start"]), hexstr(info["bss_end"])))

    return "\n".join(strings)


def print_scene_n64_splat():
    """Returns the overlay table in n64splat format."""
    rom = _romhandler().get_rom()
    if not rom:
        return "ROM is not loaded"

    scenes = rom.get_scenes()
    strings = []
    for i in range(scenes.count()):
        info = scenes.get_info(i)
        strings.append("  - name: overlay%d" % i)
        strings.append("    type: code")
        strings.append("    overlay: True")
        strings.append("    start: %s" % hexstr(info["rom_start"]))
        strings.append("    vram: %s" % hexstr(info["code_start"]))
        strings.append("    files:")
        strings.append('      - [%s, "asm"]' % hexstr(info["rom_start"]))
        strings.append('      - [%s, "bin"] # rodata' % hexstr(
            info["rom_start"] + (info["rodata_start"] - info["code_start"])))
        strings.append("")

    return "\n".join(strings)


def _print_inst(value):
    from ..mips import print as mips_print
    return mips_print(value)


def print_asm(start, end):
    """Returns a region of ROM as assembly instructions."""
    rom_view = _romhandler().get_data_view()
    cur_offset = start
    insts = []
    while cur_offset <= end:
        value = rom_view.get_uint32(cur_offset)
        asm = "? " + hexstr(value)
        try:
            asm = _print_inst(value)
        except Exception:  # noqa: BLE001
            log("UNRECOGNIZED: " + hexstr(value))
        insts.append(hexstr(cur_offset) + ": " + asm)
        cur_offset += 4

    return "\n".join(insts)


def print_scene_asm(scene_index):
    """Returns the assembly, rodata and bss of an overlay."""
    rom = _romhandler().get_rom()
    if not rom:
        return "ROM is not loaded"

    scenes = rom.get_scenes()
    scene_info = scenes.get_info(scene_index)
    current_asm_addr = scene_info["code_start"]
    code_data_view = scenes.get_code_data_view(scene_index)
    insts = []
    for i in range(0, code_data_view.byte_length, 4):
        value = code_data_view.get_uint32(i)
        asm = "? " + hexstr(value)
        try:
            asm = _print_inst(value)
        except Exception:  # noqa: BLE001
            log("UNRECOGNIZED: " + hexstr(value))
        insts.append(hexstr(current_asm_addr) + ": " + asm)
        current_asm_addr += 4

    sections = ["\n".join(insts)]

    ro_data_view = scenes.get_ro_data_view(scene_index)
    lines = []
    current_asm_addr = scene_info["rodata_start"]
    i = 0
    while i < ro_data_view.byte_length:
        for k in range(4):
            lines.append("D_" + hexstr(current_asm_addr + 4 * k, "") + ": "
                         + pad(hexstr(ro_data_view.get_uint32(i + 4 * k), ""), 8, "0"))
        current_asm_addr += 16
        i += 16
    sections.append("\n".join(lines))

    lines = []
    for b in range(scene_info["bss_start"], scene_info["bss_end"], 4):
        lines.append("D_%s: .word 0" % hexstr(b, ""))
    sections.append("\n".join(lines))

    return "\n".join(sections)
