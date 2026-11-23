"""Custom soundbanks (lib/audio/custom_bank): presets, importing recordings, sizes and previews.
A board's soundbanks themselves are board data (the setBoardSoundbank op).

    GET  /api/soundbanks/gameboy             -> a Game Boy soundbank
    POST /api/soundbanks/import-wav?name=&key=   (body: a .wav file) -> {instrument}
    POST /api/soundbanks/info    {soundbank} -> {bytes, budget, problem}
    POST /api/soundbanks/preview {soundbank, midi (data URL or base64)} -> audio/wav
    POST /api/soundbanks/note    {instrument, key, seconds} -> audio/wav (one note)
"""

import base64

from ..http import ApiError, Response, route


def _bank_module():
    from ...lib.audio import custom_bank
    return custom_bank


def _soundbank(req):
    bank = req.arg("soundbank")
    problem = _bank_module().check_soundbank(bank)
    if problem:
        raise ApiError(problem)
    return bank


def _game():
    """The open ROM's game ("NMVE"), or Mario Party 3's when no ROM is open."""
    from ...lib.romhandler import romhandler
    return romhandler.get_rom_game() or "NMVE"


@route("GET", "/api/soundbanks/gameboy")
def gameboy(req):
    return _bank_module().game_boy_bank()


@route("POST", "/api/soundbanks/import-wav")
def import_wav(req):
    cb = _bank_module()
    if not req.body:
        raise ApiError("Send a .wav file.")
    try:
        key = int(req.query.get("key", 60))
    except ValueError:
        raise ApiError("key must be a MIDI note number (0-127).")
    if not 0 <= key <= 127:
        raise ApiError("key must be a MIDI note number (0-127).")
    name = (req.query.get("name") or "Sample").rsplit(".", 1)[0][:40]
    try:
        inst = cb.import_wav(req.body, name, key)
    except (cb.SoundbankError, ValueError, IndexError) as e:
        raise ApiError("The WAV file could not be read: %s" % e)
    return {"instrument": inst}


@route("POST", "/api/soundbanks/info")
def info(req):
    cb = _bank_module()
    bank = _soundbank(req)
    game = cb._game_name(_game())
    return {"bytes": cb.bank_bytes(bank), "budget": cb.BANK_BUDGET.get(game),
            "problem": cb.budget_problem(game, [bank])}


def _midi_bytes(value):
    if not isinstance(value, str) or not value:
        raise ApiError("Send the song's MIDI file.")
    try:
        return base64.b64decode(value.split(",", 1)[1] if value.startswith("data:") else value)
    except ValueError:
        raise ApiError("The MIDI file could not be read.")


@route("POST", "/api/soundbanks/preview")
def preview(req):
    from ...lib.audio.midiplayer import render_with_soundbank
    bank = _soundbank(req)
    try:
        wav = render_with_soundbank(_midi_bytes(req.arg("midi")), bank)
    except ValueError as e:
        raise ApiError(str(e))
    return Response(wav, "audio/wav")


def _one_note_midi(key, seconds):
    """A standard MIDI file: program 0 plays one note (velocity 110) for `seconds` at 120 bpm."""
    ticks = max(1, int(seconds * 2 * 96))

    def vl(v):
        out = [v & 0x7F]
        v >>= 7
        while v:
            out.insert(0, (v & 0x7F) | 0x80)
            v >>= 7
        return bytes(out)
    events = (b"\x00\xc0\x00" + b"\x00\x90" + bytes([key, 110]) + vl(ticks) + b"\x80" + bytes([key, 0])
              + vl(96) + b"\xb0\x07\x7f" + b"\x00\xff\x2f\x00")
    return (b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big")
            + (96).to_bytes(2, "big") + b"MTrk" + len(events).to_bytes(4, "big") + events)


@route("POST", "/api/soundbanks/note")
def note(req):
    from ...lib.audio.midiplayer import render_with_soundbank
    cb = _bank_module()
    inst = req.arg("instrument")
    bank = {"name": "Preview", "instruments": [inst]}
    problem = cb.check_soundbank(bank)
    if problem:
        raise ApiError(problem)
    try:
        key = int(req.arg("key", 60))
        seconds = float(req.arg("seconds", 1.0))
    except (TypeError, ValueError):
        raise ApiError("key and seconds must be numbers.")
    if not 0 <= key <= 127 or not 0 < seconds <= 10:
        raise ApiError("key must be 0-127 and seconds 0-10.")
    return Response(render_with_soundbank(_one_note_midi(key, seconds), bank), "audio/wav")
