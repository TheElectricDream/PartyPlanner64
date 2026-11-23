"""Custom soundbank routes (server/routes/soundbanks.py) and the board's soundbank ops."""

import io
import math
import struct
import wave


def _wav(samples, rate=32000):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return out.getvalue()


def _midi_data_url():
    import base64
    ev = b"\x00\xc0\x02\x00\x90\x45\x6e\x60\x80\x45\x00\x00\xff\x2f\x00"
    midi = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) + b"MTrk" + struct.pack(">I", len(ev)) + ev
    return "data:audio/midi;base64," + base64.b64encode(midi).decode()


def test_gameboy_info_and_note(client):
    bank = client.get("/api/soundbanks/gameboy")
    assert bank["name"] == "Game Boy" and len(bank["instruments"]) == 8
    info = client.post("/api/soundbanks/info", {"soundbank": bank})
    assert 0 < info["bytes"] < info["budget"] and info["problem"] is None
    status, headers, body = client.call("POST", "/api/soundbanks/note",
                                        {"instrument": bank["instruments"][2], "key": 69, "seconds": 0.5})
    assert status == 200 and headers["Content-Type"] == "audio/wav" and body[:4] == b"RIFF"
    assert client.post("/api/soundbanks/info", {"soundbank": {"name": "x", "instruments": []}}, expect=400)


def test_import_wav(client):
    samples = [int(9000 * math.sin(i / 5)) for i in range(4000)]
    status, _, body = client.call("POST", "/api/soundbanks/import-wav?name=Bell.wav&key=72", _wav(samples))
    assert status == 200
    import json
    inst = json.loads(body)["instrument"]
    assert inst["name"] == "Bell" and inst["source"]["key"] == 72
    assert client.call("POST", "/api/soundbanks/import-wav", b"nope")[0] == 400


def test_preview(client):
    bank = client.get("/api/soundbanks/gameboy")
    status, headers, body = client.call("POST", "/api/soundbanks/preview",
                                        {"soundbank": bank, "midi": _midi_data_url()})
    assert status == 200 and body[:4] == b"RIFF" and len(body) > 10000


def test_board_soundbank_ops(client):
    bank = client.get("/api/soundbanks/gameboy")
    client.op("setBoardAudio", {"audioChanges": {"audioType": 1, "customAudioIndex": 0,
                                                 "midiName": "song.mid", "midiData": _midi_data_url()}})
    client.op("setBoardSoundbank", {"index": 0, "soundbank": bank})
    client.op("setBoardSoundbank", {"index": 1, "soundbank": dict(bank, name="Second")})
    client.op("setBoardAudio", {"audioChanges": {"customAudioIndex": 0, "customSoundbank": 1}})
    board = client.get("/api/board")["board"]
    assert [b["name"] for b in board["soundbanks"]] == ["Game Boy", "Second"]
    assert board["audioData"][0]["customSoundbank"] == 1
    # Deleting a soundbank before it moves the song's index down; deleting it unlinks the song.
    client.op("setBoardSoundbank", {"index": 0, "delete": True})
    assert client.get("/api/board")["board"]["audioData"][0]["customSoundbank"] == 0
    client.op("setBoardSoundbank", {"index": 0, "delete": True})
    board = client.get("/api/board")["board"]
    assert "customSoundbank" not in board["audioData"][0] and "soundbanks" not in board
    # A game soundbank index unlinks too.
    client.op("setBoardSoundbank", {"index": 0, "soundbank": bank})
    client.op("setBoardAudio", {"audioChanges": {"customAudioIndex": 0, "customSoundbank": 0}})
    client.op("setBoardAudio", {"audioChanges": {"customAudioIndex": 0, "soundbankIndex": 4}})
    entry = client.get("/api/board")["board"]["audioData"][0]
    assert entry["soundbankIndex"] == 4 and "customSoundbank" not in entry
    # Bad soundbanks are refused.
    r = client.op("setBoardSoundbank", {"index": 1, "soundbank": {"name": "x", "instruments": []}}, expect=400)
    assert r is None or "instruments" in str(r)
