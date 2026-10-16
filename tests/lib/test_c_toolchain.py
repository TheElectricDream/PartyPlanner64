"""Tests of the C toolchain ports (cpp.js, c-preprocessor, c-compiler) against the TypeScript."""

import json
import os

import pytest

from partyplanner64.lib import cppjs
from partyplanner64.lib.utils.c_preprocessor import preprocess

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures", "ctool")

with open(os.path.join(FIXTURES, "cpp.json")) as f:
    CPP_CASES = json.load(f)


def _run_cpp(text):
    warns, errors, completed = [], [], []

    def include_func(file, is_global, resumer):
        if file == "test.h":
            resumer("int test = 0;")
        elif file.lower() == "ultra64.h":
            resumer("#define TRUE 1\n#define FALSE 0\ntypedef int s32;")
        else:
            resumer(None)

    inst = cppjs.create({
        "include_func": include_func,
        "completion_func": lambda t, *rest: completed.append(t),
        "warn_func": warns.append,
        "error_func": errors.append,
    })
    try:
        ret = inst.run(text)
        out = {"ret": ret}
    except cppjs.CppError as e:
        out = {"thrown": str(e)}
    out.update({"completed": completed[0] if completed else None, "warns": warns, "errors": errors})
    return out


@pytest.mark.parametrize("case", CPP_CASES, ids=[str(i) for i in range(len(CPP_CASES))])
def test_cppjs_matches_js(case):
    assert _run_cpp(case["text"]) == case["cpp"]


@pytest.mark.parametrize("case", CPP_CASES, ids=[str(i) for i in range(len(CPP_CASES))])
def test_preprocess_matches_ts(case):
    try:
        got = {"ok": preprocess(case["text"])}
    except ValueError as e:
        got = {"error": str(e)}
    assert got == case["pre"]


def test_cppjs_spec():
    # The cases of cppjs.spec.ts.
    instance = cppjs.create()
    assert instance.run("\n#define PI 3.14159\n\nint main () {\n    cout << \"Value of PI :\" << PI << endl;\n"
                        "    return 0;\n}\n") == ("\n\nint main () {\n    cout << \"Value of PI :\" << 3.14159"
                                                 " << endl;\n    return 0;\n}\n")
    done = []

    def include_func(file, is_global, resumer):
        assert file == "test.h"
        assert is_global is False
        resumer("int test = 0;")

    instance = cppjs.create({"include_func": include_func, "completion_func": lambda r, *a: done.append(r)})
    instance.run("\n#include \"test.h\"\n\nint main () {\n    return 0;\n}")
    assert done == ["int test = 0;\n\n\nint main () {\n    return 0;\n}"]


with open(os.path.join(FIXTURES, "compile.json")) as f:
    COMPILE_CASES = json.load(f)


@pytest.mark.parametrize("case", COMPILE_CASES, ids=[str(i) for i in range(len(COMPILE_CASES))])
def test_compile_matches_ts(case):
    pytest.importorskip("wasmtime")
    from partyplanner64.lib.utils.c_compiler import compile
    try:
        got = {"ok": compile(case["source"])}
    except ValueError as e:
        got = {"error": str(e)}
    expected = {k: v for k, v in case.items() if k != "source"}
    assert got == expected


def test_compile_assembles():
    """Compiled C assembles with the assembler port (as custom events do)."""
    pytest.importorskip("wasmtime")
    from partyplanner64.lib.mips import assemble
    from partyplanner64.lib.utils.c_compiler import compile
    asm = compile("int x = 5; float f = 2.0f; void main() { int i; for (i = 0; i < 3; i++) x += i; "
                  "f = f * x; }")
    out = assemble(".org 0x80100000\n" + asm)
    assert len(out) > 0 and len(out) % 4 == 0
