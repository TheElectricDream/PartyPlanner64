"""Audio: the ROM's songs (sequence tables) and sound effects (sound tables)
(apps/partyplanner64/views/audio.tsx).

The browser played them with WebAudio (midiplayer.ts, soundplayer.ts); here the
server renders a WAV that the page plays in an <audio> element.

    GET  /api/audio -> {songs: [{table, soundbankCount, items: [{index, name, soundbankIndex}]}],
                        sounds: [{table, items: [{index, name, sampleRate}]}]}
    GET  /api/audio/song/<t>/<i>.wav            the song rendered with its soundbank
    GET  /api/audio/song/<t>/<i>.mid            the song as a standard MIDI file (download)
    POST /api/audio/song/<t>/<i>/replace        a .mid file's bytes: replaces the song
    POST /api/audio/song/<t>/<i>/soundbank {soundbankIndex}
    GET  /api/audio/sound/<t>/<i>.wav           a sound effect (?download=1 to save it)
"""

import importlib
import re
import threading
from collections import OrderedDict

from ..http import ApiError, Response, route

_lock = threading.Lock()
_wav_cache = OrderedDict()      # (rom key, kind, t, i, revision) -> bytes
WAV_CACHE_SIZE = 12
_revision = [0]                 # bumped when a song changes

def _state_lock():
    """The app's lock (state.lock): held while changing the ROM."""
    from ... import state
    return state.lock



def _romhandler():
    from ...lib.romhandler import romhandler
    return romhandler


def _rom():
    rom = _romhandler().get_rom()
    if rom is None:
        raise ApiError("Open a ROM first.", 409)
    return rom


def _audio():
    return _rom().get_audio()


def _adapter():
    """The ROM's adapter (for the names of songs and sounds), or None."""
    try:
        from ...lib.adapter.adapters import get_rom_adapter
        return get_rom_adapter({})
    except Exception:  # noqa: BLE001 - names are a nicety
        return None


def _names(fn_name, table):
    adapter = _adapter()
    if adapter is None:
        return {}
    try:
        names = getattr(adapter, fn_name)(table)
    except Exception:  # noqa: BLE001
        return {}
    if isinstance(names, (list, tuple)):
        return {i: n for i, n in enumerate(names) if n}
    return {int(k): v for k, v in (names or {}).items() if v}


def _midi_get(midi, key):
    """A field of an IMidiInfo (a dict in the port; camelCase tolerated)."""
    if isinstance(midi, dict):
        if key in midi:
            return midi[key]
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), key)
        return midi.get(camel)
    return getattr(midi, key, None)


def _midi_set(midi, key, value):
    if isinstance(midi, dict):
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), key)
        midi[camel if camel in midi and key not in midi else key] = value
    else:
        setattr(midi, key, value)


def _seq_table(t):
    audio = _audio()
    if not 0 <= t < audio.get_sequence_table_count():
        raise ApiError("There is no song table %d." % t, 404)
    return audio.get_sequence_table(t)


def _song(t, i):
    table = _seq_table(t)
    if not 0 <= i < len(table.midis):
        raise ApiError("Song table %d has no song %d." % (t, i), 404)
    return table, table.midis[i]


def _sound(t, i):
    audio = _audio()
    if not 0 <= t < audio.get_sound_table_count():
        raise ApiError("There is no sound table %d." % t, 404)
    table = audio.get_sound_table(t)
    if not 0 <= i < len(table.sounds):
        raise ApiError("Sound table %d has no sound %d." % (t, i), 404)
    return table, table.sounds[i]


def _find_function(name, modules):
    """C's audio functions, wherever they ended up."""
    for mod in modules:
        try:
            m = importlib.import_module(mod, __package__)
        except ImportError:
            continue
        fn = getattr(m, name, None)
        if fn:
            return fn
    return None


_AUDIO_MODULES = ("...lib.audio", "...lib.audio.render", "...lib.audio.synth",
                  "...lib.audio.midiplayer", "...lib.audio.soundplayer", "...lib.audio.wav",
                  "...lib.audio.midi")


def _cached(key, make):
    with _lock:
        if key in _wav_cache:
            _wav_cache.move_to_end(key)
            return _wav_cache[key]
    data = bytes(make())
    with _lock:
        _wav_cache[key] = data
        while len(_wav_cache) > WAV_CACHE_SIZE:
            _wav_cache.popitem(last=False)
    return data


def _safe_name(name, fallback):
    name = re.sub(r'[\\/:*?"<>|]+', "", str(name or "")).strip()
    return name or fallback


@route("GET", "/api/audio")
def get_audio(req):
    audio = _audio()
    songs = []
    for t in range(audio.get_sequence_table_count()):
        table = audio.get_sequence_table(t)
        names = _names("get_audio_map", t)
        banks = getattr(getattr(table, "soundbanks", None), "banks", None) or []
        songs.append({"table": t, "soundbankCount": len(banks), "items": [
            {"index": i, "name": names.get(i), "soundbankIndex": _midi_get(m, "soundbank_index")}
            for i, m in enumerate(table.midis)]})
    sounds = []
    for t in range(audio.get_sound_table_count()):
        table = audio.get_sound_table(t)
        names = _names("get_sound_effect_map", t)
        sounds.append({"table": t, "items": [
            {"index": i, "name": names.get(i), "sampleRate": getattr(s, "sample_rate", None)}
            for i, s in enumerate(table.sounds)]})
    canRender = _find_function("render_sequence_wav", _AUDIO_MODULES) is not None
    return {"songs": songs, "sounds": sounds, "canRenderSongs": canRender}


@route("GET", "/api/audio/song/<int:t>/<int:i>.wav")
def get_song_wav(req, t, i):
    _song(t, i)
    render = _find_function("render_sequence_wav", _AUDIO_MODULES)
    if render is None:
        raise ApiError("Playing songs isn't available yet: this installation can't render "
                       "MIDI with the game's soundbanks. Download the MIDI instead.", 501)
    wav = _cached((id(_rom()), "song", t, i, _revision[0]), lambda: render(t, i))
    return Response(wav, "audio/wav")


@route("GET", "/api/audio/song/<int:t>/<int:i>.mid")
def get_song_midi(req, t, i):
    table, midi = _song(t, i)
    export = _find_function("export_midi", _AUDIO_MODULES)
    if export is not None:
        data = export(t, i)
    else:
        from ...lib.audio.midi import parse_game_midi
        from ...lib.utils.dataview import DataView
        buf = _midi_get(midi, "buffer")
        data = parse_game_midi(DataView(buf), len(buf))
    name = _safe_name(_names("get_audio_map", t).get(i), "music")
    return Response(bytes(data), "audio/midi", filename="%s.mid" % name)


@route("POST", "/api/audio/song/<int:t>/<int:i>/replace")
def replace_song(req, t, i):
    table, midi = _song(t, i)
    if not req.body:
        raise ApiError("Send a MIDI file.")
    if not req.body.startswith(b"MThd"):
        raise ApiError("That isn't a MIDI file (.mid).")
    from ...lib.audio.midi import create_game_midi
    game_midi = create_game_midi(bytearray(req.body), {"loop": True})
    if not game_midi:
        raise ApiError("Could not process the MIDI for insertion into the game.")
    with _state_lock():
        _midi_set(midi, "buffer", game_midi)
        _revision[0] += 1
    return {"table": t, "index": i}


@route("POST", "/api/audio/song/<int:t>/<int:i>/soundbank")
def set_soundbank(req, t, i):
    table, midi = _song(t, i)
    banks = getattr(getattr(table, "soundbanks", None), "banks", None) or []
    try:
        value = int(req.arg("soundbankIndex"))
    except (TypeError, ValueError):
        raise ApiError("Invalid soundbank index.")
    if not 0 <= value < len(banks):
        raise ApiError("Invalid soundbank index: enter 0 through %d." % (len(banks) - 1))
    with _state_lock():
        _midi_set(midi, "soundbank_index", value)
        _revision[0] += 1
    return {"table": t, "index": i, "soundbankIndex": value}


@route("GET", "/api/audio/sound/<int:t>/<int:i>.wav")
def get_sound_wav(req, t, i):
    table, sound = _sound(t, i)
    make = _find_function("sound_wav", _AUDIO_MODULES)
    if make is not None:
        wav = _cached((id(_rom()), "sound", t, i, 0), lambda: make(t, i))
    else:
        from ...lib.audio.wav import extract_wav_from_sound
        wav = _cached((id(_rom()), "sound", t, i, 0),
                      lambda: extract_wav_from_sound(table.tbl, sound, sound.sample_rate))
    name = None
    if req.query.get("download"):
        name = "%s.wav" % _safe_name(_names("get_sound_effect_map", t).get(i), str(i))
    return Response(wav, "audio/wav", filename=name)
