"""Image codecs against reference outputs of the TypeScript (gen_images.ts)."""

import base64
import json
import os

import pytest

from partyplanner64.lib.utils.arrays import hash, read_bit_at_offset, read_byte_at_bit_offset, to_hex_string
from partyplanner64.lib.utils.canvas import ImageData
from partyplanner64.lib.utils.dataview import DataView
from partyplanner64.lib.utils.image import cut_from_whole, invert_color
from partyplanner64.lib.utils.img.bmp import bm_pfrom_rgba, bm_pto_rgba
from partyplanner64.lib.utils.img.font_pack import font_pack_to_rgba32, is_font_pack
from partyplanner64.lib.utils.img.get_image_data import resize_image_data
from partyplanner64.lib.utils.img.grayscale import grayscale_to_rgba32
from partyplanner64.lib.utils.img.hvq import decode
from partyplanner64.lib.utils.img.img_pack import from_pack, to_pack
from partyplanner64.lib.utils.img.rgba32 import make8_bit
from partyplanner64.lib.utils.img.rgba5551 import rgba5551from_rgba32, rgba5551to_rgba32
from partyplanner64.lib.utils.img.tiler import from_tiles, to_tiles
from partyplanner64.lib.utils.string import from_u32, mp_format_to_plain_text, to_u32

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "..", "fixtures", "core")
with open(os.path.join(FIXTURES, "images.json")) as f:
    DATA = json.load(f)


def b(s):
    return base64.b64decode(s)


def e(data):
    return base64.b64encode(bytes(data)).decode()


@pytest.mark.parametrize("case", DATA["rgba5551to"])
def test_rgba5551_to_rgba32(case):
    assert e(rgba5551to_rgba32(bytearray(b(case["input"])), case["w"], case["h"])) == case["output"]


@pytest.mark.parametrize("case", DATA["rgba5551from"])
def test_rgba5551_from_rgba32(case):
    assert e(rgba5551from_rgba32(bytearray(b(case["input"])), case["w"], case["h"])) == case["output"]


@pytest.mark.parametrize("case", DATA["grayscale"])
def test_grayscale(case):
    out = grayscale_to_rgba32(bytearray(b(case["input"])), case["w"], case["h"], case["bpp"])
    assert e(out) == case["output"]


def _check(result_fn, expected):
    if isinstance(expected, dict) and "error" in expected:
        with pytest.raises(Exception):
            result_fn()
        return None
    return result_fn()


@pytest.mark.parametrize("case", DATA["bmpTo"])
def test_bmp_to_rgba(case):
    out = _check(lambda: bm_pto_rgba(bytearray(b(case["input"])), case["palette"], case["inBpp"], case["outBpp"]),
                 case["output"])
    if out is not None:
        assert e(out) == case["output"]


@pytest.mark.parametrize("case", DATA["bmpFrom"])
def test_bmp_from_rgba(case):
    out = _check(lambda: bm_pfrom_rgba(bytearray(b(case["input"])), case["inBpp"], case["outBpp"]), case["output"])
    if out is not None:
        bmp, palette = out
        assert e(bmp) == case["output"]["bmp"]
        assert palette == case["output"]["palette"]


@pytest.mark.parametrize("case", DATA["tiles"])
def test_tiles(case):
    img = bytearray(b(case["input"]))
    tiles = to_tiles(img, case["xc"], case["yc"], case["xw"], case["yw"])
    assert [e(t) for t in tiles] == case["tiles"]
    back = from_tiles([DataView(t) for t in tiles], case["xc"], case["yc"], case["xw"], case["yw"])
    assert e(back) == case["back"]
    # Lists of values are accepted too.
    assert [e(t) for t in to_tiles(list(img), case["xc"], case["yc"], case["xw"], case["yw"])] == case["tiles"]


@pytest.mark.parametrize("case", DATA["tilesOdd"])
def test_tiles_unaligned(case):
    tiles = [DataView(bytearray(b(t))) for t in case["tiles"]]
    out = _check(lambda: from_tiles(tiles, case["xc"], case["yc"], case["xw"], case["yw"]), case["output"])
    if out is not None:
        assert e(out) == case["output"]


def _infos(inputs):
    return [{"width": i["width"], "height": i["height"], "bpp": i["bpp"], "src": bytearray(b(i["src"]))}
            for i in inputs]


@pytest.mark.parametrize("case", DATA["packs"], ids=lambda c: c["name"])
def test_img_pack(case):
    infos = _infos(case["inputs"])
    old = bytearray(b(case["old"])) if case["old"] else None
    if "error" in case["output"]:
        with pytest.raises(Exception):
            to_pack(infos, case["outBpp"], case["bmpBpp"], old)
        return
    pack = to_pack(infos, case["outBpp"], case["bmpBpp"], old)
    assert e(pack) == case["output"]["pack"]
    if isinstance(case["output"]["back"], dict):
        # (from_pack can't read packs with several images that to_pack made:
        # to_pack puts each image right after its entry.)
        with pytest.raises(Exception):
            from_pack(pack)
        return
    back = [{"width": i["width"], "height": i["height"], "src": e(i["src"]) if "src" in i else None}
            for i in from_pack(pack)]
    assert back == case["output"]["back"]


@pytest.mark.parametrize("case", DATA["rawPacks"])
def test_img_pack_raw(case):
    pack = bytearray(b(case["pack"]))
    if isinstance(case["output"], dict):
        with pytest.raises(Exception):
            from_pack(pack)
        return
    back = [{"width": i["width"], "height": i["height"], "src": e(i["src"]) if "src" in i else None}
            for i in from_pack(pack)]
    assert back == case["output"]


@pytest.mark.parametrize("case", DATA["fonts"] + DATA["fontsSmall"])
def test_font_pack(case):
    pack = bytearray(b(case["pack"]))
    assert is_font_pack(pack) == case["isFontPack"]
    if "output" not in case:
        return
    out = _check(lambda: font_pack_to_rgba32(pack), case["output"])
    if out is not None:
        assert [e(i) for i in out["images"]] == case["output"]["images"]
        assert [e(i) for i in out["chars"]] == case["output"]["chars"]
        assert (out["char_width"], out["char_height"], out["bpp"]) == (
            case["output"]["charWidth"], case["output"]["charHeight"], case["output"]["bpp"])


@pytest.mark.parametrize("case", DATA["hvq"])
def test_hvq_decode(case):
    assert e(decode(DataView(bytearray(b(case["input"]))))) == case["output"]


@pytest.mark.parametrize("case", DATA["resize"])
def test_resize_image_data(case):
    img = ImageData(case["sw"], case["sh"], bytearray(b(case["input"])))
    out = resize_image_data(img, case["dw"], case["dh"], case["alg"])
    assert e(out.data) == case["output"]


def test_make8_bit_and_image_helpers():
    data = bytearray(b(DATA["make8Bit"]["input"]))
    make8_bit(data, 4, 3)
    assert e(data) == DATA["make8Bit"]["output"]
    src = bytearray(b(DATA["cutSrc"]))
    for c in DATA["cut"]:
        width = {32: 10, 16: 20, 8: 40}[c["bpp"]]
        assert e(cut_from_whole(src, width, 6, c["bpp"], c["x"], c["y"], c["w"], c["h"])) == c["output"]
    for color, inverted in DATA["invert"]:
        assert invert_color(color) == inverted


def test_arrays_and_strings():
    a = DATA["arrays"]
    data = bytearray(b(a["input"]))
    assert to_hex_string(data) == a["hex"]
    assert to_hex_string(data, 20, 8) == a["hex8"]
    assert [read_bit_at_offset(data, i * 7) for i in range(30)] == a["bits"]
    assert [read_byte_at_bit_offset(data, i * 9) for i in range(30)] == a["bytes"]
    assert hash(data, 3, 20) == a["hash"]
    assert hash(data, 30, 20) == a["hashOob"] == ""
    s = DATA["strings"]
    assert [mp_format_to_plain_text(x) for x in
            ["<RED>Hi　 and 　<BLUE>〇〉", "", "【】〈"]] == s["plain"]
    assert [to_u32(x) for x in ["FORM", "ÿþýü", "HVQ2"]] == s["u32"]
    assert [from_u32(x) for x in [0x464F524D, 0xFFFEFDFC]] == s["from"]
