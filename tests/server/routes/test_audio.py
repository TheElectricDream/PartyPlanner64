"""Audio: songs and sound effects (routes/audio.py)."""

import pytest

from partyplanner64.server.routes import audio


@pytest.fixture
def renderers(monkeypatch):
    """Stand-ins for the audio library's WAV and MIDI functions."""
    calls = []

    def fake(name):
        def fn(t, i):
            calls.append((name, t, i))
            return b"RIFF" + name.encode() + bytes([t, i])
        return fn
    monkeypatch.setattr(audio, "_find_function", lambda name, mods: fake(name))
    return calls


def test_no_rom(client):
    client.get("/api/audio", expect=409)


def test_listing(client, fake_rom):
    fake_rom(1)
    res = client.get("/api/audio")
    songs = res["songs"][0]
    assert songs["table"] == 0 and songs["soundbankCount"] == 2
    assert [s["soundbankIndex"] for s in songs["items"]] == [0, 0, 0]
    # Names come from the MP1 adapter's audio map.
    assert all("name" in s for s in songs["items"])
    assert res["sounds"][0]["items"][1] == {"index": 1, "name": res["sounds"][0]["items"][1]["name"],
                                            "sampleRate": 22050}


def test_wavs_and_midi(client, fake_rom, renderers):
    fake_rom(1)
    status, headers, body = client.call("GET", "/api/audio/song/0/2.wav")
    assert status == 200 and headers["Content-Type"] == "audio/wav"
    assert body == b"RIFFrender_sequence_wav\x00\x02"
    client.call("GET", "/api/audio/song/0/2.wav")
    assert renderers.count(("render_sequence_wav", 0, 2)) == 1      # cached
    status, headers, body = client.call("GET", "/api/audio/sound/0/1.wav?download=1")
    assert status == 200 and body == b"RIFFsound_wav\x00\x01"
    assert ".wav" in headers["Content-Disposition"]
    status, headers, body = client.call("GET", "/api/audio/song/0/1.mid")
    assert status == 200 and headers["Content-Type"] == "audio/midi" and body == b"RIFFexport_midi\x00\x01"
    client.get("/api/audio/song/0/7.wav", expect=404)
    client.get("/api/audio/sound/3/0.wav", expect=404)


def test_song_rendering_unavailable(client, fake_rom, monkeypatch):
    fake_rom(1)
    monkeypatch.setattr(audio, "_find_function", lambda name, mods: None)
    assert "MIDI" in client.get("/api/audio/song/0/0.wav", expect=501)["error"]
    assert client.get("/api/audio")["canRenderSongs"] is False


def test_soundbank(client, fake_rom):
    rh = fake_rom(1)
    assert client.post("/api/audio/song/0/1/soundbank", {"soundbankIndex": 1})["soundbankIndex"] == 1
    assert rh.rom.audio.seq[0].midis[1]["soundbank_index"] == 1
    assert "0 through 1" in client.post("/api/audio/song/0/1/soundbank", {"soundbankIndex": 2},
                                        expect=400)["error"]
    client.post("/api/audio/song/0/1/soundbank", {"soundbankIndex": "x"}, expect=400)


def test_replace(client, fake_rom, monkeypatch):
    rh = fake_rom(1)
    from partyplanner64.lib.audio import midi
    assert "isn't a MIDI" in client.post("/api/audio/song/0/0/replace", b"RIFF....", expect=400)["error"]
    monkeypatch.setattr(midi, "create_game_midi", lambda data, opts: bytearray(b"converted"))
    client.post("/api/audio/song/0/0/replace", b"MThd\x00\x00\x00\x06")
    assert rh.rom.audio.seq[0].midis[0]["buffer"] == b"converted"
    monkeypatch.setattr(midi, "create_game_midi", lambda data, opts: None)
    assert "Could not process" in client.post("/api/audio/song/0/0/replace", b"MThd", expect=400)["error"]
