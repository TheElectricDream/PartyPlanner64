"""Whole-ROM tests: load, edit and save synthetic ROMs, against the TypeScript.

gen_rom.ts built a synthetic Mario Party 1, 2 and 3 ROM with the TypeScript's
own saveROM, loaded it, recorded what every file system held, applied the
edits of _edit() below and recorded the md5 of the saved ROMs.
"""

import gzip
import hashlib
import json
import os

import pytest

from partyplanner64.lib.romhandler import ROM, romhandler
from partyplanner64.lib.utils.canvas import ImageData

from . import rom_stubs

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures", "core")
GAMES = ["MP1", "MP2", "MP3"]


def md5(data):
    return hashlib.md5(bytes(data)).hexdigest()


def _load_fixture(name):
    with open(os.path.join(FIXTURES, "rom_%s.json" % name)) as f:
        expected = json.load(f)
    with gzip.open(os.path.join(FIXTURES, "rom_%s.z64.gz" % name)) as f:
        original = f.read()
    return expected, original


@pytest.fixture
def stubs(monkeypatch):
    def install(char_map):
        rom_stubs.install(monkeypatch, {int(k): v for k, v in char_map.items()})
    yield install
    romhandler.clear()


def _formula(n, a, c):
    return bytearray((i * a + c) & 0xFF for i in range(n))


def _img(w, h, a, c):
    return ImageData(w, h, bytearray((i * a + c + (i >> 9)) & 0xFF for i in range(w * h * 4)))


def _describe(version):
    rom = romhandler.get_rom()
    r = {}
    scenes = rom.get_scenes()
    infos = [scenes.get_info(i) for i in range(scenes.count())]
    r["scenes"] = {
        "count": scenes.count(),
        "infos": md5(json.dumps(infos, separators=(",", ":")).encode()),
        "overlays": md5(",".join(md5(scenes.get_data_view(i).buffer) for i in range(scenes.count())).encode()),
    }
    mainfs = rom.get_main_fs()
    r["mainfs"] = []
    for d in range(mainfs.get_directory_count()):
        files = []
        for f in range(mainfs.get_file_count(d)):
            e = mainfs._mainfs_cache[d][f]
            if not e:
                files.append(None)
                continue
            files.append([e["compression_type"], e.get("decompressed_size"), md5(e["decompressed"]),
                          md5(e["compressed"]) if e.get("compressed") is not None else None,
                          mainfs.get_file_header_size(d, f), mainfs.get_compressed_size(d, f)])
        r["mainfs"].append(files)
    r["mainfsByteLength"] = [mainfs.get_byte_length(False), mainfs.get_byte_length(True)]
    if version == 3:
        s3 = rom.get_strings3()
        r["strings3"] = {}
        for locale in s3.get_locales(romhandler.get_rom_game()):
            r["strings3"][locale] = [
                [[md5(s3.read(locale, d, s, True)), s3.read(locale, d, s, False)]
                 for s in range(s3.get_string_count(locale, d))]
                for d in range(s3.get_directory_count(locale))]
        r["stringsByteLength"] = s3.get_byte_length()
    else:
        s = rom.get_strings()
        r["strings"] = [[md5(s.read(i, True)), s.read(i, False)] for i in range(s.get_string_count())]
        r["stringsByteLength"] = s.get_byte_length()
    hvqfs = rom.get_hvqfs()
    r["hvq"] = [{"files": [md5(x) for x in hvqfs._hvq_cache[b]], "meta": dict(hvqfs.get_metadata(b)),
                 "bg": md5(hvqfs.read_background_img_data(b).data)}
                for b in range(hvqfs.get_directory_count())]
    r["hvqByteLength"] = hvqfs.get_byte_length()
    if version == 2:
        anim = rom.get_animation_fs()
        r["anim"] = [[[[k, e[k]["compression_type"], md5(e[k]["decompressed"]), md5(e[k]["compressed"])]
                       for k in sorted(e)] for e in s] for s in anim._animfs_cache]
        r["animByteLength"] = anim.get_byte_length()
    r["romLength"] = len(rom.get_buffer())
    return r


def _edit(version):
    rom = romhandler.get_rom()
    mainfs = rom.get_main_fs()
    mainfs.write(0, 1, _formula(300, 13, 1))
    mainfs.write(1, mainfs.get_file_count(1) + 2, _formula(77, 7, 0))
    mainfs.write(0, 0, bytearray(mainfs.get(0, 0)))
    if version == 3:
        rom.get_strings3().write("en", 1, 0, _formula(9, 1, 0x41))
        rom.get_strings3().write("jp", 0, 1, _formula(9, 1, 0x41))
    else:
        rom.get_strings().write(2, _formula(9, 1, 0x41))
    hvqfs = rom.get_hvqfs()
    hvqfs.write_background(1, _img(128, 96, 3, 5), 128, 96)
    hvqfs.write_background(hvqfs.get_directory_count(), _img(128, 96, 7, 1), 128, 96, {
        "tileWidth": 64, "tileHeight": 48, "tileCountX": 2, "tileCountY": 2, "fov": 17.5,
        "scaleFactor": 0.25, "cameraEyePosX": 1, "cameraEyePosY": 2, "cameraEyePosZ": 3,
        "lookatPointX": 4, "lookatPointY": 5, "lookatPointZ": 6, "cameraUpVecX": 0,
        "cameraUpVecY": 1, "cameraUpVecZ": 0})
    hvqfs.update_metadata(0, {"fov": 33.25, "cameraEyePosZ": 1000})
    if version == 2:
        anim = rom.get_animation_fs()
        anim.write_animation_background(0, 1, _img(128, 96, 3, 5), _img(128, 96, 3, 9), 128, 96)
        anim.set_set_entry_count(1, 0)
    scenes = rom.get_scenes()
    scenes.replace(5, _formula(0x40, 5, 3), {"code_end": scenes.get_info(5)["code_start"] + 0x40})


def _norm(value):
    """JSON round trip (the TypeScript side's values went through JSON)."""
    return json.loads(json.dumps(value))


@pytest.mark.parametrize("name", GAMES)
def test_load_edit_save_matches_typescript(name, stubs):
    expected, original = _load_fixture(name)
    stubs(expected["loaded"]["charMap"])
    assert md5(original) == expected["originalMd5"]
    version = int(name[2])

    errors = []
    assert romhandler.set_rom_buffer(bytearray(original), True, errors.append) is True
    assert errors == expected["errors"]

    loaded = _describe(version)
    for key in loaded:
        assert _norm(loaded[key]) == expected["loaded"][key], key

    # Saving without changes gives the original back.
    assert md5(romhandler.save_rom(False)) == expected["resaveMd5"] == expected["originalMd5"]

    _edit(version)
    edited = _describe(version)
    for key in edited:
        assert _norm(edited[key]) == expected["edited"][key], key

    saved = romhandler.save_rom(False)
    assert len(saved) == expected["savedLength"]
    assert md5(saved) == expected["savedMd5"]
    saved_decompressed = romhandler.save_rom(True)
    assert len(saved_decompressed) == expected["savedDecompressedLength"]
    assert md5(saved_decompressed) == expected["savedDecompressedMd5"]


def _byteswap(data, kind):
    data = bytearray(data)
    n = len(data) - len(data) % 4
    out = bytearray(data)
    for i in range(0, n, 4):
        a, b_, c, d = data[i:i + 4]
        if kind == "v64":
            out[i:i + 4] = bytes((b_, a, d, c))
        elif kind == "n64":
            out[i:i + 4] = bytes((d, c, b_, a))
        else:  # word-swapped
            out[i:i + 4] = bytes((c, d, a, b_))
    return out


@pytest.mark.parametrize("kind", ["v64", "n64", "wordswap"])
def test_byte_swapped_roms_load_the_same(kind):
    _, original = _load_fixture("MP2")
    swapped = _byteswap(original, kind)
    assert swapped != original
    rom = ROM(swapped)
    assert rom.get_buffer() == original
    assert rom.get_game() == "NMWE" and rom.get_game_version() == 2


def test_set_rom_buffer_rejections(stubs):
    stubs({})
    errors = []
    assert romhandler.set_rom_buffer(None, False, errors.append) is False
    assert romhandler.set_rom_buffer(bytearray(0x40), False, errors.append) is False
    assert errors == ["File is not recognized as any valid ROM."]
    jpn = bytearray(0x1000)
    jpn[0:4] = b"\x80\x37\x12\x40"
    jpn[0x3B:0x3F] = b"NMWJ"
    assert romhandler.set_rom_buffer(jpn, False, errors.append) is False
    assert errors[-1] == "This ROM is not supported right now."
    assert not romhandler.rom_is_loaded()
    rom = ROM(jpn)
    assert rom.rom_recognized() and not rom.rom_supported()
    with pytest.raises(RuntimeError):
        rom.get_main_fs()
