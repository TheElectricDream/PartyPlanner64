"""The adapters' image writing against the TypeScript (fixture images.json, gen_images.ts).

The images need no resampling, so the canvas and Pillow give the same pixels.
"""

import json

import pytest

from partyplanner64.lib.adapter.adapters import get_adapter
from partyplanner64.lib.utils import canvas

from . import fakerom
from .conftest import load_fixture

IMGS = load_fixture("images_input.json")
REF = load_fixture("images.json")


def _sorted_log(log):
    # The order of writes to different files does not matter (the canvas in node
    # loads images synchronously, a browser does not).
    return sorted(json.loads(json.dumps(log)), key=lambda entry: (entry[0], entry[1], entry[2]))


def _setup(monkeypatch, game, options=None):
    rom = fakerom.install(monkeypatch, game)
    return rom, get_adapter(game, options if options is not None else {})


def _logo_pack(seed):
    from partyplanner64.lib.utils.img.img_pack import to_pack
    pack = bytearray(to_pack([{"src": fakerom.pattern(320, 240, seed), "width": 320, "height": 240,
                               "bpp": 32}], 16, 0))
    pack[0x1A] = 0x20
    return pack


@pytest.mark.parametrize("game", [1, 2, 3])
def test_brand_boot_splashscreen(monkeypatch, game):
    rom, adapter = _setup(monkeypatch, game)
    n, h = adapter.nintendo_logo_fs_entry, adapter.hudson_logo_fs_entry
    n_pack, h_pack = _logo_pack(1), _logo_pack(2)
    assert [fakerom.blob(n_pack), fakerom.blob(h_pack)] == REF["brand%d" % game]["packs"]
    rom.mainfs.files["%d/%d" % tuple(n)] = n_pack
    rom.mainfs.files["%d/%d" % tuple(h)] = h_pack
    adapter._brand_boot_splashscreen()
    assert _sorted_log(rom.log) == _sorted_log(REF["brand%d" % game]["log"])

    # Already branded: the NINTENDO logo is left alone.
    del rom.log[:]
    adapter._combine_splashcreen_logos()
    assert rom.log == []

    rom2, off = _setup(monkeypatch, game, {"write_branding": False})
    off._brand_boot_splashscreen()
    assert rom2.log == REF["brandOff%d" % game] == []


@pytest.mark.parametrize("icon", ["icon", "icon_opaque"])
def test_mp2_board_select_icon(monkeypatch, icon):
    from partyplanner64.lib.utils.img.img_pack import to_pack

    ref = REF["icon_" + icon]
    rom, adapter = _setup(monkeypatch, 2)
    select_pack = bytearray(to_pack([{"src": fakerom.pattern(200, 120, 3), "width": 200, "height": 120,
                                      "bpp": 32}], 16, 0))
    assert fakerom.blob(select_pack) == ref["pack"]
    rom.mainfs.files["9/15"] = select_pack
    info = {"name": "x", "img": {"board_select_icon_coords": [39, 20], "board_select_icon_mask": 20}}
    adapter._write_board_select_icon({"otherbg": {"boardselecticon": IMGS[icon]}}, info)
    assert _sorted_log(rom.log) == _sorted_log(ref["log"])

    board = {"otherbg": {}}
    rom.mainfs.files["9/15"] = select_pack
    adapter._parse_board_select_icon(board, info)
    got = canvas.get_image_data(board["otherbg"]["boardselecticon"], 32, 32)
    exp = canvas.get_image_data(ref["parsedIcon"], 32, 32)
    assert got.data == exp.data


def test_mp2_images(monkeypatch):
    rom, adapter = _setup(monkeypatch, 2)
    adapter._write_overview_background(8, IMGS["bg320"])
    adapter.on_write_board_logo_img({"otherbg": {"boardlogo": IMGS["mp2_logo"]}},
                                    {"name": "x", "img": {"intro_logo_img": 406, "pause_logo_img": 380}})
    adapter.on_write_board_select_img({"otherbg": {"boardselect": IMGS["mp2_select"]}},
                                      {"name": "x", "img": {"board_select_img": 30}})
    adapter._write_background(5, IMGS["bg320"], 320, 240)
    adapter._write_additional_backgrounds({"additionalbg": [IMGS["bg_small"], IMGS["bg_small"]],
                                           "bg": {"width": 96, "height": 72}})
    assert _sorted_log(rom.log) == _sorted_log(REF["mp2"])


def test_mp3_images(monkeypatch):
    rom, adapter = _setup(monkeypatch, 3)
    info = {"name": "x", "img": {"splash_logo_img": 22, "splash_logo_text_img": 28, "pause_logo_img": 125,
                                 "stats_logo_img": [19, 105], "board_select_img": 72}}
    adapter.on_write_board_logo_img({"otherbg": {
        "boardlogo": IMGS["logo_large"], "boardlogotext": IMGS["logo_text"],
        "boardlogomedium": IMGS["logo_medium"], "boardlogosmall": IMGS["logo_small"]}}, info)
    adapter.on_write_board_logo_img({"otherbg": {}}, info)
    adapter.on_write_board_select_img({"otherbg": {"boardselect": IMGS["mp3_select"]}}, info)
    assert json.loads(json.dumps(rom.log)) == REF["mp3"]


def test_mp1_logo(monkeypatch):
    rom, adapter = _setup(monkeypatch, 1)
    adapter.on_write_board_logo_img({"otherbg": {"boardlogo": IMGS["mp1_intro"]}},
                                    {"name": "x", "img": {"intro_logo_img": [356, 357],
                                                          "intro_logo_img_dimens": [272, 112]}})
    assert json.loads(json.dumps(rom.log)) == REF["mp1"]
