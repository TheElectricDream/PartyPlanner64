"""The ROM's strings (routes/strings.py)."""


def test_no_rom(client):
    assert client.get("/api/strings", expect=409)["error"] == "Open a ROM first."


def test_mp1_strings(client, fake_rom):
    fake_rom(1)
    info = client.get("/api/strings")
    assert info["multi"] is False and info["game"] == "MP1_USA"
    assert info["directories"] == [{"index": 0, "count": 3}]
    res = client.get("/api/strings/list")
    assert [s["text"] for s in res["strings"]] == ["Hello <RED>World", "Get a Star!", "Coins"]
    one = client.get("/api/strings/1")
    assert one["text"] == "Get a Star!" and one["raw"].endswith("21 00")
    client.get("/api/strings/9", expect=404)


def test_write_keeps_terminator(client, fake_rom):
    rh = fake_rom(1)
    res = client.post("/api/strings/write", {"index": 2, "text": "Hi <RED>　"})
    # The MP1 character map: <RED> is 0x03, the A button 0x21; the NUL is kept.
    assert bytes(rh.rom.strings.strs[2]) == bytes([ord("H"), ord("i"), 0x10, 0x03, 0x21, 0])
    assert res["raw"] == "48 69 10 03 21 00"
    client.post("/api/strings/write", {"index": 2}, expect=400)


def test_search(client, fake_rom):
    fake_rom(1)
    res = client.get("/api/strings/search?q=Star")
    assert res["results"] == [{"dir": None, "index": 1, "text": "Get a Star!"}]
    raw = client.get("/api/strings/search?q=Coins&raw=1")["results"][0]
    assert raw["raw"].startswith("43 6F")


def test_mp3_strings(client, fake_rom):
    rh = fake_rom(3)
    info = client.get("/api/strings?locale=en")
    assert info["multi"] is True and info["locales"] == ["en", "de"] and info["locale"] == "en"
    assert info["directories"] == [{"index": 0, "count": 2}, {"index": 1, "count": 1}]
    assert client.get("/api/strings?locale=xx")["locale"] == "en"
    assert client.get("/api/strings/list?locale=en&dir=1")["strings"] == [{"index": 0, "text": "Coins"}]
    assert client.get("/api/strings/list?locale=de&dir=0")["strings"][0]["text"] == "Hallo"
    client.get("/api/strings/list?locale=en&dir=5", expect=404)
    client.post("/api/strings/write", {"locale": "en", "dir": 0, "index": 1, "text": "A Coin"})
    assert rh.rom.strings3.read("en", 0, 1, True).endswith(b"\x00")
    res = client.get("/api/strings/search?q=Coin&locale=en")["results"]
    assert [(r["dir"], r["index"]) for r in res] == [(0, 1), (1, 0)]
