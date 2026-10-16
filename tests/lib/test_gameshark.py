"""Tests of the Gameshark patch port against outputs of patches/gameshark (TypeScript)."""

import json
import os

import pytest

from partyplanner64.lib.patches.gameshark import cheats
from partyplanner64.lib.patches.gameshark.compiler import Compiler
from partyplanner64.lib.patches.gameshark.hook import apply_hook, rom_supports_cheats
from partyplanner64.lib.patches.gameshark.parser import Parser

with open(os.path.join(os.path.dirname(__file__), "..", "fixtures", "gameshark", "gameshark.json")) as f:
    REF = json.load(f)


@pytest.mark.parametrize("case", REF["parsed"], ids=[str(i) for i in range(len(REF["parsed"]))])
def test_parse_and_compile(case):
    codes = Parser.parse(case["s"])
    assert codes == case["codes"]
    if codes:
        try:
            buf = Compiler().compile(codes)
            compiled = buf.hex() if buf is not None else None
        except ValueError as e:
            compiled = {"error": str(e)}
        assert compiled == case["compiled"]


@pytest.mark.parametrize("case", REF["hooks"], ids=[h["game"] for h in REF["hooks"]])
def test_apply_hook(case, monkeypatch):
    from partyplanner64.lib.romhandler import romhandler
    from partyplanner64.lib.types import Game

    writes = []

    class FakeMainFS:
        def write(self, d, f, buf):
            writes.append({"d": d, "f": f, "hex": bytes(buf).hex()})

    class FakeRom:
        def get_main_fs(self):
            return FakeMainFS()

    monkeypatch.setattr(romhandler, "get_game_version", lambda: case["version"], raising=False)
    monkeypatch.setattr(romhandler, "get_rom_game", lambda: Game(case["game"]), raising=False)
    monkeypatch.setattr(romhandler, "get_rom", lambda: FakeRom(), raising=False)

    rom = bytearray(((i * 13 + (i >> 8)) & 0xFF) for i in range(0xE0000))
    before = bytes(rom)
    cheats.reset_cheats()
    try:
        apply_hook(rom)  # No cheats: nothing happens.
        assert rom == before
        for s in (REF["parsed"][1]["s"], REF["parsed"][2]["s"]):
            cheats.current_cheats.append(Compiler().compile(Parser.parse(s)))
        apply_hook(rom)
    finally:
        cheats.reset_cheats()

    diffs = []
    for i in range(len(rom)):
        if rom[i] != before[i]:
            if diffs and diffs[-1]["offset"] + len(diffs[-1]["bytes"]) // 2 == i:
                diffs[-1]["bytes"] += "%02x" % rom[i]
            else:
                diffs.append({"offset": i, "bytes": "%02x" % rom[i]})
    assert diffs == case["diffs"]
    assert writes == case["writes"]
    assert rom_supports_cheats() == case["supported"]
