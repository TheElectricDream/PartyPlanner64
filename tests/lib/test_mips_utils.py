"""Tests of partyplanner64.lib.utils.mips against outputs of utils/MIPS.ts."""

import json
import os

import pytest

from partyplanner64.lib.utils.dataview import DataView
from partyplanner64.lib.utils.mips import (
    REG, find_calls, find_calls_in_function, get_function_length, get_jal_addr,
    get_reg_set_address, get_reg_set_upper_and_lower, make_inst,
)

with open(os.path.join(os.path.dirname(__file__), "..", "fixtures", "mips", "utils.json")) as f:
    REF = json.load(f)


def test_make_inst():
    for case in REF["makeInst"]:
        assert make_inst(case["op"], *case["args"]) == case["out"], case
    assert make_inst() is None
    with pytest.raises(ValueError, match="Unrecognized instruction"):
        make_inst("mult", 1, 2)


def test_reg():
    assert REG["A0"] == 4 and REG.SP == 29 and REG.RA == 31 and REG.S8 == 30


def test_reg_set_helpers():
    for case in REF["upperLower"]:
        assert get_reg_set_upper_and_lower(case["a"]) == case["out"]
    for case in REF["regSet"]:
        assert get_reg_set_address(case["u"], case["l"]) == case["out"]
    for case in REF["jal"]:
        assert get_jal_addr(case["w"]) == case["out"]
    with pytest.raises(ValueError) as e:
        get_jal_addr(0x27BDFFE0)
    assert str(e.value) == REF["jalErr"]


def test_calls_and_lengths():
    dv = DataView(bytearray.fromhex(REF["bufHex"]))
    assert find_calls(dv, 0x80104320) == REF["findCalls"]
    assert [find_calls_in_function(dv, 0, 0x80104320),
            find_calls_in_function(dv, 24, 0x80104320)] == REF["findCallsInFunction"]
    assert [get_function_length(dv, 0), get_function_length(dv, 20),
            get_function_length(dv, 24)] == REF["getFunctionLength"]
