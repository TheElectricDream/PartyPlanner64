"""Differential tests of the mips-inst port against outputs of the JS package."""

import json
import os

import pytest

from partyplanner64.lib.mips import parse, print_inst

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "mips", "inst.json")


@pytest.fixture(scope="module")
def ref():
    with open(FIXTURE) as f:
        return json.load(f)


_OPT_NAMES = {"casing": "casing", "commas": "commas", "include$": "include_dollar",
              "numBase": "num_base", "intermediate": "intermediate"}


def _opts(js_opts):
    return {_OPT_NAMES[k]: v for k, v in js_opts.items()}


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def test_print_matches_js(ref):
    failures = []
    for case in ref["printCases"]:
        got = _call(print_inst, case["w"], **_opts(ref["optSets"][case["o"]]))
        if got != case["out"]:
            failures.append((hex(case["w"]), case["o"], case["out"], got))
    assert not failures[:20], "%d mismatches: %r" % (len(failures), failures[:20])


def test_parse_matches_js(ref):
    failures = []
    for case in ref["parseCases"]:
        got = _call(parse, case["s"])
        if got != case["out"]:
            failures.append((case["s"], case["out"], got))
    assert not failures[:20], "%d mismatches: %r" % (len(failures), failures[:20])


def test_every_opcode_is_covered(ref):
    from partyplanner64.lib.mips.inst.opcodes import opcode_details
    printed = {c["out"].split(" ")[0].lower() for c in ref["printCases"] if isinstance(c["out"], str)}
    generic = set()
    from partyplanner64.lib.mips.inst.regex import get_opcode
    for p in printed:
        generic.add(get_opcode(p))
    # pref has the same encoding as lwc3, which comes first and wins when printing.
    assert set(opcode_details) - generic == {"pref"}
    parsed = {get_opcode(c["s"]) for c in ref["parseCases"] if isinstance(c["out"], int)}
    assert set(opcode_details) - parsed <= {"madd.fmt", "msub.fmt", "nmadd.fmt", "nmsub.fmt"}


def test_multiline_objects_and_buffers(ref):
    for case in ref["multi"]:
        assert _call(parse, case["s"]) == case["out"]
    for case in ref["objCases"]:
        assert _call(parse, dict(case["o"])) == case["parse"]
        assert _call(print_inst, dict(case["o"])) == case["print"]
        assert _call(lambda o: print_inst(parse(o), intermediate=True), dict(case["o"])) == case["inter"]
    for case in ref["interCases"]:
        assert _call(parse, case["s"], intermediate=True) == case["out"]
    words = ref["bufCase"]["words"]
    data = b"".join(w.to_bytes(4, "big") for w in words)
    assert print_inst(data) == ref["bufCase"]["out"]
    assert print_inst(bytearray(data)) == ref["bufCase"]["out"]
    from partyplanner64.lib.utils.dataview import DataView
    assert print_inst(DataView(bytearray(data))) == ref["bufCase"]["out"]
