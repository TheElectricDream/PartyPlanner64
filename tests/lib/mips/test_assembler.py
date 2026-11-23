"""Differential tests of the mips-assembler port against outputs of the JS package."""

import base64
import gzip
import hashlib
import json
import os
import time

import pytest

from partyplanner64.lib.mips import assemble

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "mips")


def _load(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


ASM_CASES = _load("asm.json")
CORPUS = _load("corpus.json")


def _run(prog):
    opts = dict(prog.get("opts") or {})
    kwargs = {}
    if "files" in opts:
        kwargs["files"] = opts["files"]
    if opts.get("text"):
        kwargs["text"] = True
    if "symbolOutputMap" in opts:
        kwargs["symbol_output_map"] = {}
    buf = None
    if prog.get("bufLen"):
        buf = bytearray((i * 37 + 11) & 0xFF for i in range(prog["bufLen"]))
        kwargs["buffer"] = buf
    try:
        result = assemble(prog["asm"], **kwargs)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    out = {"text": result} if kwargs.get("text") else {"hex": bytes(result).hex()}
    if "symbol_output_map" in kwargs:
        out["syms"] = kwargs["symbol_output_map"]
    if buf is not None:
        out["same"] = result is buf
    return out


# Where the port deliberately differs from the JS package: the original read a number's leading
# digits and ignored the rest, so values that aren't numbers became wrong numbers silently
# ("0-toll" and "0X10" were 0, ".float 1.5" was 1.0, "1F" was 1). They are errors now, and
# decimals are read whole (for .float).
_NOT_A_NUMBER = '"{}" is not a number. Numbers are written 10, -10, 0x0A, 0b1010 or 0o12, ' \
    "and operands can't do arithmetic (0-toll, toll+1).\nLine: "
DIFFERENCES = {
    # .float 1.5, 2, -0.25, 3: 1.5 and -0.25 (0x3FC00000, 0xBE800000), not 1.0 and -0.0.
    "data": lambda out: {"hex": out["hex"].replace("3f8000004000000080000000", "3fc0000040000000be800000")},
    "numbers_ok": lambda out: {"error": _NOT_A_NUMBER.format("1F") + ".word 10, 0x10, 0b101, 0o17, x10, b11, "
                               "-0x10, 1F, 010, 0, -0, 0x7fffffff, 0xffffffff"},
    "numbers": lambda out: {"error": _NOT_A_NUMBER.format("1F") + ".word 10, 0x10, 0b101, 0o17, x10, b11, o7, "
                            "-0x10, 1F, 010, -b1, 0, -0"},
    # x10 is left for the instruction parser (which reads it as hex), not made 0.
    "numbers_ok_text": lambda out: {"text": out["text"][:-1] + ["addiu a0 a0 x10"]},
}


@pytest.mark.parametrize("prog", ASM_CASES, ids=[p["name"] for p in ASM_CASES])
def test_programs_match_js(prog):
    expected = prog["out"]
    if prog["name"] in DIFFERENCES:
        expected = DIFFERENCES[prog["name"]](expected)
    assert _run(prog) == expected


def test_silent_numbers_are_errors():
    """Values that only start like numbers were silently read as their leading digits."""
    for value in ("0-toll", "5-toll", "0X10", "10000b", "1F", "1.5"):
        with pytest.raises(Exception, match="is not a number|Could not parse instruction"):
            assemble(".definelabel toll,5\nADDIU A1 R0 " + value)
    word = lambda src: bytes(assemble(src)).hex()  # noqa: E731
    assert word("ADDIU A1 R0 b10000") == word("ADDIU A1 R0 0b10000") == word("ADDIU A1 R0 16")
    assert word("ADDIU A1 R0 o20") == word("ADDIU A1 R0 16")
    assert word(".float 1.5") == "3fc00000"
    # offset($reg): the original read "0x10($a1)" as 0x10 and dropped the register.
    assert word("LW A0 0x10($a1)") == word("LW A0 0x10(A1)")


@pytest.mark.parametrize("case", CORPUS, ids=[c["name"] for c in CORPUS])
def test_corpus_matches_js(case):
    asm = gzip.decompress(base64.b64decode(case["asmGz"])).decode("utf-8")
    expected = case["out"]
    syms = {}
    try:
        buf = assemble(asm, symbol_output_map=syms)
    except Exception as e:  # noqa: BLE001
        assert {"error": str(e)} == expected
        return
    assert "error" not in expected, expected
    assert len(buf) == expected["len"]
    assert hashlib.sha256(buf).hexdigest() == expected["sha256"]
    assert syms == expected["syms"]
    text = assemble(asm, text=True)
    assert hashlib.sha256("\n".join(text).encode("utf-8")).hexdigest() == expected["textSha256"]


def test_overlay_speed():
    """The biggest board overlay (MP3, ~20k lines) should assemble quickly."""
    case = next(c for c in CORPUS if c["name"] == "overlay_3_0")
    asm = gzip.decompress(base64.b64decode(case["asmGz"])).decode("utf-8")
    start = time.perf_counter()
    assemble(asm)
    elapsed = time.perf_counter() - start
    assert elapsed < 4, "assembling took %.2fs" % elapsed


def test_single_lines_match_js():
    """Every printed instruction form, assembled on its own (gen_lines.ts)."""
    failures = []
    for line, hex_out, text in _load("lines.json"):
        src = ".org 0x80001000\n" + line
        try:
            got = [line, bytes(assemble(src)).hex(), "|".join(assemble(src, text=True))]
        except Exception as e:  # noqa: BLE001
            got = [line, None, str(e)]
        if got != [line, hex_out, text]:
            if hex_out is None and got[1] is not None:
                # The original failed on offset($reg) forms (see test_silent_numbers_are_errors);
                # they now assemble as the same line without "$" does.
                plain = ".org 0x80001000\n" + line.replace("$", "")
                if got[1] == bytes(assemble(plain)).hex():
                    continue
            if "0X" in line and got[1] is None and "is not a number" in got[2]:
                continue  # "0X10" was silently 0.
            failures.append((got, [line, hex_out, text]))
    assert not failures[:10], "%d mismatches: %r" % (len(failures), failures[:10])
