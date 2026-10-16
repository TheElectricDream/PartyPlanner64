"""overwrite_board end to end against the TypeScript, with a fake ROM.

Fixtures: overwrite_input.json (the boards) and overwrite.json (what the
TypeScript wrote, from gen_overwrite.ts). Image writing is skipped on both
sides (on_overwrite_promises): the TypeScript resamples with the canvas.
"""

import copy
import json

import pytest

from partyplanner64.lib.adapter.adapters import get_adapter

from . import fakerom
from .conftest import load_fixture

INPUT = load_fixture("overwrite_input.json")
REF = load_fixture("overwrite.json")
CASES = {case["name"]: case for case in INPUT["cases"]}


def run_overwrite(monkeypatch, case):
    rom = fakerom.install(monkeypatch, case["game"])
    adapter = get_adapter(case["game"], {})
    adapter.on_overwrite_promises = lambda *args: None
    adapter.overwrite_board(case["boardIndex"], copy.deepcopy(case["board"]))
    return rom


@pytest.mark.parametrize("name", sorted(CASES))
def test_overwrite_board(monkeypatch, name):
    ref = REF[name]
    assert "error" not in ref
    rom = run_overwrite(monkeypatch, CASES[name])

    log = json.loads(json.dumps(rom.log))
    assert [entry[0:2] for entry in log] == [entry[0:2] for entry in ref["log"]]
    for got, exp in zip(log, ref["log"]):
        assert got == exp, got[0:3]
    scenes = {str(i): fakerom.runs(buf) for i, buf in rom.scenes.bufs.items()}
    assert scenes == ref["scenes"]
    assert fakerom.runs(rom.rom_buffer) == ref["rom"]
