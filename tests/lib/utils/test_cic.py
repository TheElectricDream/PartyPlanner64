import json
import os
import time

import pytest

from partyplanner64.lib.utils.cic import _get_game_cic, fix_checksum

from .cic_data import make_rom

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "core")
with open(os.path.join(FIXTURES, "cic.json")) as f:
    CASES = json.load(f)


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["bootcode"]))
def test_fix_checksum_matches_typescript(case):
    rom = make_rom(case["seed"], case["bootcode"])
    expected_cic = case["bootcode"] or 6105  # Unknown bootcodes count as 6105.
    assert _get_game_cic(rom) == expected_cic
    before = bytes(rom)
    t0 = time.perf_counter()
    fix_checksum(rom)
    elapsed = time.perf_counter() - t0
    assert int.from_bytes(rom[0x10:0x14], "big") == case["crc1"]
    assert int.from_bytes(rom[0x14:0x18], "big") == case["crc2"]
    # Nothing else changes.
    assert rom[:0x10] == before[:0x10] and rom[0x18:] == before[0x18:]
    assert elapsed < 5
