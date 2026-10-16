"""GameShark patches (routes/patches.py)."""

import pytest


@pytest.fixture
def gameshark():
    return pytest.importorskip("partyplanner64.lib.patches.gameshark.hook")


def test_no_rom(client):
    res = client.get("/api/patches")
    assert res["romOpen"] is False and res["supported"] is False and res["cheats"] == []
    assert client.post("/api/patches", {"text": "8105E418 2400"}, expect=409)


def test_parse(client, gameshark):
    codes = client.post("/api/patches/parse", {"text": "8105E418 2400\nD01F0000 0001"})["codes"]
    assert codes == [{"opcode": "WRITE16", "addr": 0x8005E418, "value": 0x2400},
                     {"opcode": "IF8", "addr": 0x801F0000, "value": 1}]
    assert "error parsing" in client.post("/api/patches/parse", {"text": "8105E418"}, expect=400)["error"]
    assert "Paste" in client.post("/api/patches/parse", {"text": "  "}, expect=400)["error"]


def test_add_delete_clear(client, fake_rom, gameshark):
    from partyplanner64.lib.patches.gameshark import cheats
    fake_rom(1)
    cheats.reset_cheats()
    res = client.get("/api/patches")
    assert res["supported"] is True and res["game"] == "MP1_USA" and res["cheats"] == []
    res = client.post("/api/patches", {"text": "8105E418   2400"})
    assert len(res["cheats"]) == 1 and len(cheats.current_cheats) == 1
    assert res["cheats"][0]["text"] == "8105E418 2400"
    assert res["cheats"][0]["codes"][0]["opcode"] == "WRITE16"
    assert res["cheats"][0]["size"] == len(cheats.current_cheats[0])
    res = client.post("/api/patches", {"text": "8005E418 0001"})
    assert [c["index"] for c in res["cheats"]] == [0, 1]
    res = client.post("/api/patches/0/delete")
    assert len(res["cheats"]) == 1 and res["cheats"][0]["text"] == "8005E418 0001"
    client.post("/api/patches/5/delete", expect=404)
    assert client.post("/api/patches/clear")["cheats"] == []
    # A new ROM resets the cheats; the listing follows.
    client.post("/api/patches", {"text": "8005E418 0001"})
    cheats.reset_cheats()
    assert client.get("/api/patches")["cheats"] == []


def test_unsupported_rom(client, fake_rom, gameshark, monkeypatch):
    from partyplanner64.lib.patches.gameshark import hook
    fake_rom(1)
    monkeypatch.setattr(hook, "rom_supports_cheats", lambda: False)
    assert client.get("/api/patches")["supported"] is False
    assert "not supported" in client.post("/api/patches", {"text": "8105E418 2400"}, expect=400)["error"]
