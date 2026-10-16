"""Song names without a ROM, and the compiled assembly of C events."""

import importlib.util

import pytest


def test_song_names_need_no_rom(client):
    for game, first in ((1, "Peaceful Mushroom Village"), (2, "Story One"), (3, "Opening")):
        names = client.get("/api/songs/%d" % game)["names"]
        assert first in names.values()
        assert all(names.values())
    client.get("/api/songs/4", expect=400)


@pytest.mark.skipif(importlib.util.find_spec("wasmtime") is None, reason="needs wasmtime")
def test_c_event_test_sends_its_assembly(client):
    code = ("// NAME: Test C\n// GAMES: MP1_USA,MP3_USA\n// EXECUTION: Direct\n"
            "void main() { int x = 1; }\n")
    res = client.post("/api/events/test", {"code": code, "language": 1})
    assert [r["ok"] for r in res["results"]] == [True, True]
    for r in res["results"]:
        assert "main:" in r["asm"]
    mips = client.post("/api/events/test", {
        "code": "; NAME: Test S\n; GAMES: MP3_USA\n; EXECUTION: Direct\nJR RA\nNOP\n",
        "language": 0})
    assert mips["results"][0]["ok"] and "asm" not in mips["results"][0]
