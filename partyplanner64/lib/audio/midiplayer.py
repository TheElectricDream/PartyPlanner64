"""Song playback and the audio page's song actions (stands in for audio/midiplayer.ts).

The browser parsed the game MIDI into a standard MIDI (parseGameMidi), played
it with midi-player-js, and started a WebAudio buffer source for each note:
the soundbank sound whose key map covers the note, pitched by detune
(the key map's detune plus 100 cents per semitone away from its key base),
through a gain of instrument volume x sound volume x channel volume (controller
7) x velocity, each over 127. A note off stopped the note's source; a note
without one played its sample to the end. Samples did not loop, and the
envelopes and pan were not used. render_midi does the same, offline, and mixes
the notes into a mono WAV.

Deviations from the browser: events are read with standard MIDI running
status (midi-player-js read running-status controller, program and pitch bend
values from the wrong bytes and started notes on running pitch bends), and
velocities are used as stored (midi-player-js scaled non-running velocities by
100/127). Event times are exact rather than on a 5 ms timer.
"""

import logging
from array import array

from .midi import create_game_midi, parse_game_midi
from .playershared import Mixer, PackedVoice, pcm16_wav, resample_linear, resampled_length
from .wav import extract_wav_sound, read_wav_samples
from ..utils.dataview import DataView

logger = logging.getLogger("partyplanner64")

VELOCITY_MAX = 0x7F
CHANNEL_COUNT = 16


def _get_rom_audio():
    from ..romhandler import romhandler

    rom = romhandler.get_rom()
    if rom is None:
        raise ValueError("No ROM is loaded")
    return rom.get_audio()


def _get_sequence_table(table):
    seq_table = _get_rom_audio().get_sequence_table(table)
    if seq_table is None:
        raise ValueError("There is no sequence table %s" % table)
    return seq_table


def _get_midi_info(seq_table, index):
    if index < 0 or index >= len(seq_table.midis):
        raise ValueError("There is no song %s in this sequence table" % index)
    return seq_table.midis[index]


def export_midi(table, index):
    """Return song `index` of sequence table `table` as a standard .mid file (bytes)."""
    midi_info = _get_midi_info(_get_sequence_table(table), index)
    game_midi_buffer = midi_info["buffer"]
    return bytes(parse_game_midi(DataView(game_midi_buffer), len(game_midi_buffer)))


def replace_midi(table, index, midi_file):
    """Replace song `index` of sequence table `table` with a standard MIDI file (bytes).

    As the audio page did, the song is converted with looping on.

    Raises:
        ValueError: The MIDI could not be converted.
    """
    seq_table = _get_sequence_table(table)
    midi_info = _get_midi_info(seq_table, index)
    try:
        game_midi = create_game_midi(bytes(midi_file), {"loop": True})
    except (IndexError, TypeError):
        game_midi = None
    if not game_midi:
        raise ValueError("Could not process midi for insertion into the game")
    midi_info["buffer"] = game_midi


def get_soundbank_count(table):
    """Return how many soundbanks sequence table `table` has."""
    return len(_get_sequence_table(table).soundbanks.banks)


def change_soundbank_index(table, index, soundbank_index):
    """Set the soundbank song `index` of sequence table `table` plays with.

    Raises:
        ValueError: "Invalid soundbank index." when out of range.
    """
    seq_table = _get_sequence_table(table)
    midi_info = _get_midi_info(seq_table, index)
    bank_count = len(seq_table.soundbanks.banks)
    try:
        new_soundbank_index = int(soundbank_index)
    except (TypeError, ValueError):
        raise ValueError("Invalid soundbank index.")
    if new_soundbank_index < 0 or new_soundbank_index >= bank_count:
        raise ValueError("Invalid soundbank index.")
    midi_info["soundbank_index"] = new_soundbank_index


def render_sequence_wav(table, index, sample_rate=22050):
    """Render song `index` of sequence table `table` of the open ROM to a .wav file (bytes)."""
    seq_table = _get_sequence_table(table)
    midi_info = _get_midi_info(seq_table, index)
    bank = seq_table.soundbanks.banks[midi_info["soundbank_index"]]
    game_midi_buffer = midi_info["buffer"]
    midi = parse_game_midi(DataView(game_midi_buffer), len(game_midi_buffer))
    return render_midi(midi, bank, seq_table.tbl, sample_rate)


# --- Standard MIDI reading -------------------------------------------------


def _var_int(data, pos):
    """Read a MIDI variable-length number. Returns (value, new position) or (None, pos)."""
    value = 0
    while True:
        if pos >= len(data):
            return None, pos
        b = data[pos]
        pos += 1
        if b & 0x80:
            value = (value + (b & 0x7F)) << 7
        else:
            return value + b, pos


def read_midi(midi):
    """Read a standard MIDI file into (division, tracks).

    Chunks are walked as midi-player-js did (from offset 0, by each chunk's
    length). Each track is a list of events: dicts with "tick" and "type"
    ("note" with channel/note/velocity, "program" with channel/value,
    "controller" with channel/number/value, "tempo" with bpm, "end", or
    "other").
    """
    midi = bytes(midi)
    if midi[:4] != b"MThd":
        raise ValueError("Invalid MIDI file; should start with MThd")
    division = int.from_bytes(midi[12:14], "big")
    tracks = []
    offset = 0
    while offset < len(midi):
        length = int.from_bytes(midi[offset + 4:offset + 8], "big")
        if midi[offset:offset + 4] == b"MTrk":
            tracks.append(_read_track(midi[offset + 8:offset + 8 + length]))
        offset += length + 8
    return division, tracks


_DATA_LENGTHS = {0x8: 2, 0x9: 2, 0xA: 2, 0xB: 2, 0xC: 1, 0xD: 1, 0xE: 2}


def _read_track(data):
    events = []
    pos = 0
    tick = 0
    last_status = 0
    while pos < len(data):
        delta, pos = _var_int(data, pos)
        if delta is None or pos >= len(data):
            break
        tick += delta
        status = data[pos]
        if status == 0xFF:
            if pos + 1 >= len(data):
                break
            meta_type = data[pos + 1]
            length, payload = _var_int(data, pos + 2)
            if length is None:
                break
            body = data[payload:payload + length]
            pos = payload + length
            if meta_type == 0x51 and len(body) >= 3:
                us = int.from_bytes(body[:3], "big")
                # midi-player-js kept the tempo as rounded beats per minute.
                bpm = int(60000000 / us + 0.5) if us else 120
                events.append({"tick": tick, "type": "tempo", "bpm": bpm})
            elif meta_type == 0x2F:
                events.append({"tick": tick, "type": "end"})
            else:
                events.append({"tick": tick, "type": "other"})
            continue
        if status in (0xF0, 0xF7):
            length, payload = _var_int(data, pos + 1)
            if length is None:
                break
            pos = payload + length
            events.append({"tick": tick, "type": "other"})
            continue
        if status < 0x80:
            if last_status < 0x80:
                break  # Running status without a previous status.
            status = last_status
        else:
            pos += 1
            last_status = status
        kind = status >> 4
        count = _DATA_LENGTHS.get(kind)
        if count is None:
            break
        values = data[pos:pos + count]
        pos += count
        if len(values) < count:
            break
        channel = status & 0xF
        if kind == 0x9:
            events.append({"tick": tick, "type": "note", "channel": channel,
                           "note": values[0], "velocity": values[1]})
        elif kind == 0x8:
            events.append({"tick": tick, "type": "note", "channel": channel,
                           "note": values[0], "velocity": 0})
        elif kind == 0xC:
            events.append({"tick": tick, "type": "program", "channel": channel, "value": values[0]})
        elif kind == 0xB:
            events.append({"tick": tick, "type": "controller", "channel": channel,
                           "number": values[0], "value": values[1]})
        else:
            events.append({"tick": tick, "type": "other", "channel": channel})
    return events


def _schedule(division, tracks):
    """Return the events of all tracks in play order, each with a "time" in seconds."""
    # midi-player-js handled one event per track per step, track by track.
    ordered = []
    for track_index, events in enumerate(tracks):
        rank_in_tick = 0
        last_tick = None
        for event_index, event in enumerate(events):
            rank_in_tick = rank_in_tick + 1 if event["tick"] == last_tick else 0
            last_tick = event["tick"]
            ordered.append(((event["tick"], rank_in_tick, track_index), event_index, track_index, event))

    # Its dry run left the tempo at the last Set Tempo it read (one event per track per step).
    bpm = 120
    dry_run = sorted((e[1], e[2]) for e in ordered if e[3]["type"] == "tempo")
    if dry_run:
        event_index, track_index = dry_run[-1]
        bpm = tracks[track_index][event_index]["bpm"]

    ordered.sort(key=lambda e: e[0])
    division = division or 96
    time = 0.0
    tick = 0
    result = []
    for _key, _ei, track_index, event in ordered:
        time += (event["tick"] - tick) * 60.0 / (bpm * division)
        tick = event["tick"]
        if event["type"] == "tempo" and event["bpm"] > 0:
            bpm = event["bpm"]
        result.append((time, track_index, event))
    return result


# --- Rendering -------------------------------------------------------------


class _SampleInfo:
    __slots__ = ("samples", "rate", "keymap", "instrument_volume", "sound_volume")


def _load_samples(tbl, bank, instrument_index, cache):
    infos = cache.get(instrument_index)
    if infos is None:
        infos = []
        instrument = bank.instruments[instrument_index]
        for s, sound in enumerate(instrument.sounds):
            info = _SampleInfo()
            try:
                rate, pcm = read_wav_samples(extract_wav_sound(tbl, bank, instrument_index, s))
            except (ValueError, IndexError) as e:
                logger.warning("Could not decode instrument %d sound %d: %s", instrument_index, s, e)
                rate, pcm = bank.sample_rate, ()
            info.samples = array("f", pcm)
            info.rate = rate
            info.keymap = sound.keymap
            info.instrument_volume = instrument.volume
            info.sound_volume = sound.sample_volume
            infos.append(info)
        cache[instrument_index] = infos
    return infos


def _find_sample_to_play(infos, note_number):
    for info in infos:
        if info.keymap.key_min <= note_number <= info.keymap.key_max:
            return info
    return None


def render_midi(midi, bank, tbl, sample_rate=22050):
    """Render a standard MIDI file with a soundbank to a mono 16-bit .wav file (bytes).

    Args:
        midi: The standard MIDI file (as parse_game_midi makes).
        bank: The ALBank to play with.
        tbl: The sound data the bank's waves point into.
        sample_rate: The output sample rate.
    """
    division, tracks = read_midi(midi)
    schedule = _schedule(division, tracks)

    sample_cache = {}
    channel_instrument_map = {}
    channel_volumes = [127] * (CHANNEL_COUNT + 1)
    active_nodes = {}  # (channel, track, note) -> voice
    voices = []  # [start, stop or None, info, step, gain]

    for time, track, event in schedule:
        kind = event["type"]
        if kind == "program":
            channel_instrument_map[event["channel"]] = event["value"]
        elif kind == "controller":
            if event["number"] == 7:
                channel_volumes[event["channel"]] = event["value"]
        elif kind == "note":
            channel = event["channel"]
            note_number = event["note"]
            inst = channel_instrument_map.get(channel)
            if inst is None or inst >= len(bank.instruments):
                logger.debug("Instrument %s is unrecognized", inst)
                continue
            infos = _load_samples(tbl, bank, inst, sample_cache)
            sample_info = _find_sample_to_play(infos, note_number)
            if sample_info is None:
                logger.debug("No note for channel %d instrument %d note number %d",
                             channel, inst, note_number)
                continue

            key = (channel, track, note_number)
            start = int(round(time * sample_rate))
            playing = active_nodes.get(key)
            if not event["velocity"]:
                if playing is not None and (playing[1] is None or playing[1] > start):
                    playing[1] = start
                active_nodes[key] = None
            else:
                keymap = sample_info.keymap
                cents = keymap.detune + (note_number - keymap.key_base) * 100
                step = sample_info.rate * (2.0 ** (cents / 1200.0)) / sample_rate
                gain = (sample_info.instrument_volume / VELOCITY_MAX
                        * sample_info.sound_volume / VELOCITY_MAX
                        * channel_volumes[channel] / VELOCITY_MAX
                        * event["velocity"] / VELOCITY_MAX)
                voice = [start, None, sample_info, step, gain]
                voices.append(voice)
                active_nodes[key] = voice

    # How much of each pitched sample is heard, so each is resampled once.
    needed = {}
    for start, stop, info, step, gain in voices:
        full = resampled_length(len(info.samples), step)
        length = full if stop is None else min(full, stop - start)
        key = (id(info), step)
        if length > needed.get(key, 0):
            needed[key] = length

    resampled = {}
    mixer = Mixer()
    for start, stop, info, step, gain in voices:
        key = (id(info), step)
        voice = resampled.get(key)
        if voice is None:
            voice = resampled[key] = PackedVoice(resample_linear(info.samples, step, needed[key]))
        length = voice.length if stop is None else min(voice.length, stop - start)
        mixer.add(start, voice, gain, length)

    return pcm16_wav(mixer.render(), sample_rate)
