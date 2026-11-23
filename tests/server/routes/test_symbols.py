"""GET /api/symbols: the games' symbols for the MIPS completion (routes/symbols.py)."""


def test_symbols_for_one_game(client):
    res = client.get("/api/symbols?games=MP1_USA")
    assert res["games"] == ["MP1_USA"] and res["missing"] == []
    names = [s["name"] for s in res["symbols"]]
    assert names == sorted(names)
    assert not any(n.startswith(("_", "?")) for n in names)
    sym = next(s for s in res["symbols"] if s["name"] == "AdjustPlayerCoins")
    assert sym["type"] == "code" and sym["addr"] > 0x80000000


def test_symbols_by_id_and_type(client):
    by_name = client.get("/api/symbols?games=MP3_USA&type=code")
    by_id = client.get("/api/symbols?games=NMVE&type=code")
    assert by_name["symbols"] == by_id["symbols"]
    assert by_name["symbols"] and all(s["type"] == "code" for s in by_name["symbols"])


def test_symbols_intersection(client):
    mp1 = {s["name"] for s in client.get("/api/symbols?games=MP1_USA")["symbols"]}
    mp3 = {s["name"] for s in client.get("/api/symbols?games=MP3_USA")["symbols"]}
    both = {s["name"] for s in client.get("/api/symbols?games=MP1_USA,MP3_USA")["symbols"]}
    assert both == mp1 & mp3


def test_symbols_missing_and_unknown(client):
    res = client.get("/api/symbols?games=MP2_PAL")
    assert res["missing"] == ["MP2_PAL"] and res["symbols"] == []
    assert client.get("/api/symbols")["symbols"] == []
    assert "Unknown game" in client.get("/api/symbols?games=MP9", expect=400)["error"]


def test_symbols_note_has_the_whole_comment(client):
    syms = {s["name"]: s for s in client.get("/api/symbols?games=MP3_USA")["symbols"]}
    coins = syms["AdjustPlayerCoins"]
    assert coins["desc"] == "A0=player_index"
    assert coins["note"] == "A0=player_index,A1=amount (signed), ensures 0 <= coins <= 999"
    assert "note" not in syms["GetCurrentPlayerIndex"]      # no comment at all
    assert "note" not in syms["PlayMusic"]                  # "A0=index": desc says it all


def test_reference(client):
    res = client.get("/api/reference")
    assert res["categories"][0] == "Events"
    by_id = {e["id"]: e for e in res["entries"]}
    assert by_id["mips:addiu"]["examples"] and by_id["reg:a0"]["words"] == ["a0", "$a0"]
    assert by_id["game:AdjustPlayerCoins"]["games"] == ["MP1_USA", "MP2_USA", "MP3_USA"]
    assert res["functions"]["InitCameras"] == "Creates the given number of cameras."
