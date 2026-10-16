import json
import os

import pytest

from partyplanner64.lib.fs.strings import StringTable, str_to_bytes
from partyplanner64.lib.romhandler import ROM, romhandler
from partyplanner64.lib.utils.dataview import DataView

from .. import rom_stubs

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "core")
with open(os.path.join(FIXTURES, "strings.json")) as f:
    DATA = json.load(f)


@pytest.mark.parametrize("game", sorted(DATA))
def test_str_to_bytes_matches_typescript(game, monkeypatch):
    char_map = {int(k): v for k, v in DATA[game]["map"].items()}
    rom_stubs.install(monkeypatch, char_map)
    buf = bytearray(0x40)
    buf[0:4] = b"\x80\x37\x12\x40"
    buf[0x3B:0x3F] = game.encode()
    romhandler._rom = ROM(buf)
    try:
        for text, expected in DATA[game]["results"]:
            assert str_to_bytes(text) == expected, text
    finally:
        romhandler.clear()


def _table(strs):
    out = bytearray(4 + 4 * len(strs))
    view = DataView(out)
    view.set_uint32(0, len(strs))
    for i, s in enumerate(strs):
        view.set_uint32(4 + 4 * i, len(out))
        out += len(s).to_bytes(2, "big") + s
        if len(out) % 2:
            out.append(0)
    return out


def test_string_table_round_trip(monkeypatch):
    rom_stubs.install(monkeypatch, {0x41: "A", 0x0A: "\n", 0x03: "<RED>"})
    buf = bytearray(0x40)
    buf[0x3B:0x3F] = b"NMWE"
    romhandler._rom = ROM(buf)
    try:
        strs = [b"ABC", b"", b"\x03A\x0a!", b"x" * 7]
        data = bytearray(b"\xEE" * 6) + _table(strs)
        table = StringTable(DataView(data, 6))
        assert table.get_string_count() == 4
        assert [bytes(table.read(i, True)) for i in range(4)] == strs
        assert table.read(2) == "<RED>A\n!"
        assert table.read(0) == "ABC"
        with pytest.raises(IndexError):
            table.read(4)
        table.write(1, b"zz")
        out = bytearray(table.get_byte_length())
        end = table.pack(out)
        assert end == len(out)
        assert out == _table([b"ABC", b"zz", b"\x03A\x0a!", b"x" * 7])
        assert table.get_byte_length(True) == len(out) + len(out) / 8 + 16
    finally:
        romhandler.clear()
