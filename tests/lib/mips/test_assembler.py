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


@pytest.mark.parametrize("prog", ASM_CASES, ids=[p["name"] for p in ASM_CASES])
def test_programs_match_js(prog):
    assert _run(prog) == prog["out"]


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
