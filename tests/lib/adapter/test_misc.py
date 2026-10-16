"""The rest of the adapters against the TypeScript (fixture misc.json, gen_misc.ts):
the space writers, custom audio, hydrate_space, address helpers, parsing images
from packs, animation backgrounds and the name maps."""

import json

import pytest

from partyplanner64.lib.adapter import adapters
from partyplanner64.lib.adapter.adapters import get_adapter
from partyplanner64.lib.adapter.boardinfo import get_arrow_rotation_limit, get_board_infos
from partyplanner64.lib.utils import canvas

from . import fakerom
from .conftest import as_json, load_fixture

INPUT = load_fixture("misc_input.json")
REF = load_fixture("misc.json")


class SeqTable:
    def __init__(self):
        self.midis = []


def _sp(x, y, **extra):
    return dict({"x": x, "y": y, "z": 0, "type": 1}, **extra)


@pytest.mark.parametrize("game", [1, 2, 3])
def test_misc(monkeypatch, game):
    from partyplanner64.lib.boards import add_space_internal
    from partyplanner64.lib.events.event_library import get_events_in_library
    from partyplanner64.lib.utils.img.img_pack import to_pack

    ref = REF[str(game)]
    rom = fakerom.install(monkeypatch, game)
    seq_table = SeqTable()
    rom.audio.get_sequence_table = lambda index: seq_table
    rom.animationfs.write_animation_background = lambda s, i, main, anim, w, h: rom.log.append(
        ["animationfs.writeAnimationBackground", s, i, fakerom.blob(main.data), fakerom.blob(anim.data), w, h])
    adapter = get_adapter(game, {})
    infos = get_board_infos(fakerom.GAME_IDS[game])

    board = {
        "game": game, "type": "NORMAL", "bg": {"width": 960, "height": 720}, "events": {}, "links": {},
        "spaces": [_sp(10, 10, star=True), _sp(50, 50, subtype=0), _sp(400, 400, star=True),
                   _sp(300, 310, subtype=0), _sp(5, 600, subtype=3), _sp(700, 20, subtype=5),
                   _sp(800, 30, subtype=6), _sp(100, 650, subtype=7), _sp(900, 700, subtype=8),
                   _sp(450, 450, subtype=2), _sp(460, 460, subtype=1)],
    }

    def attempt(name, fn):
        try:
            fn()
        except Exception:
            rom.log.append(["error", name])

    for j, info in enumerate(infos):
        attempt("_writeStarInfo%d" % j, lambda: adapter._write_star_info(board, info))
        attempt("_writeBoos%d" % j, lambda: adapter._write_boos(board, info))
        attempt("_writeBanks%d" % j, lambda: adapter._write_banks(board, info))
        attempt("_writeItemShops%d" % j, lambda: adapter._write_item_shops(board, info))
        attempt("_writeGates%d" % j, lambda: adapter._write_gates(board, info))
        if game == 1:
            attempt("_writeKoopa%d" % j, lambda: adapter._write_koopa(board, info))
            attempt("_writeBowser%d" % j, lambda: adapter._write_bowser(board, info))
    empty = {"game": game, "bg": {"width": 960, "height": 720}, "spaces": [_sp(1, 1)], "links": {}}
    attempt("emptyStarInfo", lambda: adapter._write_star_info(empty, infos[0]))
    attempt("emptyBoos", lambda: adapter._write_boos(empty, infos[0]))
    assert as_json(board) == ref["board"]
    assert as_json(empty) == ref["empty"]
    assert {str(i): fakerom.runs(buf) for i, buf in rom.scenes.bufs.items()} == ref["scenes"]

    # Custom audio.
    audio_data = [{"name": "a", "data": INPUT["midi"], "soundbankIndex": 3},
                  {"name": "b", "data": INPUT["midi"], "soundbankIndex": 1}]
    assert adapter.on_write_audio({"audioType": 1, "audioData": audio_data}, infos[0], 0) == ref["audio"]
    assert [[fakerom.blob(m["buffer"]), m["soundbank_index"]] for m in seq_table.midis] == ref["midis"]
    assert [adapter.on_write_audio({"audioIndex": 9}, infos[0], 0),
            adapter.on_write_audio({}, infos[0], 0)] == ref["audioInGame"]

    # hydrate_space through add_space_internal.
    hb = {"game": game, "spaces": [], "links": {}, "events": {}}
    for space_type in (5, 6, 12, 1):
        add_space_internal(10, 20, space_type, None, hb, get_events_in_library())
    assert as_json(hb) == ref["hydrated"]

    assert [adapter._offset_to_addr(o, {"scene_index": 4}) for o in (0x1234, 0x300000, 0x210000)] == \
        ref["offsetToAddr"]
    assert [adapter._offset_to_addr_base(0x10, 0x807B0000),
            adapter._addr_to_offset_base(0x807B0040, 0x807B0000),
            adapter._addr_to_offset_base(0x00100010, 0x80100020)] == ref["offsetBase"]

    assert adapter.get_audio_map(0) == ref["maps"]["audio"]
    assert adapter.get_sound_effect_map(0) == ref["maps"]["sfx"]
    assert {str(k): v for k, v in adapter.get_character_map().items()} == ref["maps"]["chars"]

    # Parse board select images and logos from image packs.
    packs = {1: [[10, 276]], 2: [[9, 30], [10, 406]], 3: [[20, 72], [19, 22], [19, 28]]}[game]
    for n, (d, f) in enumerate(packs):
        rom.mainfs.files["%d/%d" % (d, f)] = to_pack(
            [{"src": fakerom.pattern(24 + n * 8, 16, n), "width": 24 + n * 8, "height": 16, "bpp": 32}], 16, 0)
    pb = {"otherbg": {}}
    if game != 1:
        adapter.on_parse_board_select_img(pb, infos[0])
    adapter.on_parse_board_logo_img(pb, infos[0])
    assert sorted(pb["otherbg"]) == sorted(ref["parsedImages"])
    for key, url in pb["otherbg"].items():
        got = canvas.open_image(url)
        exp = canvas.open_image(ref["parsedImages"][key])
        assert got.size == exp.size and got.tobytes() == exp.tobytes(), key

    if game == 2:
        adapter._write_animation_backgrounds(1, 96, 72, INPUT["bg"], [INPUT["bg"], INPUT["bg"]])
        adapter._write_animation_backgrounds(None, 96, 72, INPUT["bg"], [INPUT["bg"]])
        adapter._write_animation_backgrounds(2, 96, 72, INPUT["bg"], [])
    assert json.loads(json.dumps(rom.log)) == ref["log"]


def test_lookups(monkeypatch):
    assert get_arrow_rotation_limit() == REF["arrowRotationLimit"]
    assert [get_adapter(4, {}), get_board_infos("NMVJ")] == REF["noAdapter"]
    from partyplanner64.lib.romhandler import romhandler
    monkeypatch.setattr(romhandler, "get_game_version", lambda: None)
    assert adapters.get_rom_adapter({}) is REF["noRomAdapter"] is None
    monkeypatch.setattr(romhandler, "get_game_version", lambda: 3)
    assert type(adapters.get_rom_adapter({})).__name__ == "MP3Adapter"


def test_options():
    assert get_adapter(1).options == {"write_branding": True}
    assert get_adapter(2, {"write_branding": False}).options == {"write_branding": False}
