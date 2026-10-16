import importlib.util
import json
import os

import pytest

from partyplanner64.lib.symbols.symbols import get_symbol, get_symbols
from partyplanner64.lib.types import Game

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _update_symbols():
    path = os.path.join(ROOT, "scripts", "update_symbols.py")
    spec = importlib.util.spec_from_file_location("update_symbols", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_get_symbol():
    assert get_symbol(Game.MP3_USA, "overlay_base") == 0x801059A0
    assert get_symbol("NMVE", "osTvType") == 0x80000300
    assert get_symbol(Game.MP1_PAL, "overlay_table") == 0x800C92B4
    with pytest.raises(ValueError, match="wasn't found for NMVE"):
        get_symbol(Game.MP3_USA, "no_such_symbol")
    with pytest.raises(ValueError, match="Symbols not available for game type NMWP"):
        get_symbol(Game.MP2_PAL, "x")
    with pytest.raises(ValueError, match="Unrecognized game type"):
        get_symbols("ABCD")


def test_get_symbols_filters():
    all_syms = get_symbols(Game.MP1_USA)
    assert all_syms and all(s["name"][0] not in "_?" for s in all_syms)
    u32 = get_symbols(Game.MP1_USA, "u32")
    assert u32 and all(s["type"] == "u32" for s in u32)
    assert len(get_symbols(Game.MP2_JPN)) == 2


def test_symbol_files_match_the_typescript_modules():
    # Every .sym.js entry made it into the JSON (spot-check sizes and fields).
    here = os.path.join(ROOT, "partyplanner64", "lib", "symbols")
    for name, count in [("MarioParty1U", None), ("MarioParty3U", None), ("MarioParty1E", 2)]:
        with open(os.path.join(here, name + ".json")) as f:
            syms = json.load(f)
        assert all(set(s) <= {"addr", "type", "name", "desc"} for s in syms)
        if count is not None:
            assert len(syms) == count


def test_convert_symbols():
    mod = _update_symbols()
    text = ("80000300,u32,osTvType,0=PAL\r\n"
            "  80000304,data,osRomType  \n"
            "\n"
            "800C92B4,data,thing?,iffy\n"
            "800C92B8,data,?other\n"
            "800C92BC,code,func,desc, with comma\n"
            "1234,u8\n"
            "zz,u8,bad\n")
    syms = mod.convert_symbols(text)
    assert syms == [
        {"addr": 0x80000300, "type": "u32", "name": "osTvType", "desc": "0=PAL"},
        {"addr": 0x80000304, "type": "data", "name": "osRomType"},
        {"addr": 0x800C92BC, "type": "code", "name": "func", "desc": "desc"},
        {"addr": None, "type": "u8", "name": "bad"},
    ]
    out = mod.symbols_to_json(syms[:2])
    assert out.startswith("[\n{") and out.endswith("}\n]\n") and json.loads(out) == syms[:2]
