"""WAV extraction of soundbank sounds (port of audio/wav.ts)."""

import struct

from ..utils.dataview import DataView
from .al_wave_table import ALWaveType
from .vadpcm import decode_vadpcm_samples

RIFF_CHUNK_HEADER_SIZE = 0x8
WAV_FMT_CHUNK_SIZE = 0x18
WAV_DATA_CHUNK_HEADER_SIZE = 0x8
WAV_SMPL_CHUNK_SIZE = 0x44


def extract_wav_sound(tbl, bank, instrument_index, sound_index):
    """Extracts a particular sound from a bank/instrument into wav format.

    See Subdrag's CN64AIFCAudio::ExtractRawSound
    https://github.com/derselbst/N64SoundTools/blob/master/N64SoundListTool/N64SoundLibrary/N64AIFCAudio.cpp#L2361

    Args:
        tbl: The sound data (bytes).
        bank: ALBank
        instrument_index: Instrument index
        sound_index: Sound index
    """
    if instrument_index >= len(bank.instruments) or not bank.instruments:
        raise ValueError("Invalid bank instrument index" + str(instrument_index))

    instrument = bank.instruments[instrument_index]

    if sound_index >= len(instrument.sounds) or not instrument.sounds:
        raise ValueError("Invalid sound instrument index" + str(sound_index))

    sound = instrument.sounds[sound_index]
    return extract_wav_from_sound(tbl, sound, bank.sample_rate)


def _write_header(out_view, sampling_rate, data_chunk_size, fmt_size):
    out_view.set_uint32(0, 0x52494646)  # "RIFF"
    out_view.set_uint32(4, len(out_view) - RIFF_CHUNK_HEADER_SIZE, True)
    out_view.set_uint32(8, 0x57415645)  # "WAVE"

    # fmt section
    out_view.set_uint32(12, 0x666D7420)  # "fmt "

    out_view.set_uint32(0x10, fmt_size, True)  # Subchunk "fmt " size
    out_view.set_uint16(0x14, 1, True)  # Audio format (PCM = 1)
    out_view.set_uint16(0x16, 1, True)  # Num Channels (Mono = 1, Stereo = 2)
    out_view.set_uint32(0x18, sampling_rate, True)  # Sample Rate
    out_view.set_uint32(0x1C, sampling_rate * 2, True)  # Byte rate
    out_view.set_uint16(0x20, 2, True)  # Block align
    out_view.set_uint16(0x22, 16, True)  # Bits per sample

    # data section
    out_view.set_uint32(0x24, 0x64617461)  # "data"
    out_view.set_uint32(0x28, data_chunk_size, True)


def _write_smpl(out_view, position, sound, loop):
    # smpl section
    out_view.set_uint32(position, 0x736D706C)  # "smpl"
    position += 4

    out_view.set_uint32(position, 0x3C, True)  # smpl chunk size
    position += 4

    out_view.set_uint32(position, 0)  # Manufacturer
    position += 4
    out_view.set_uint32(position, 0)  # Product
    position += 4
    out_view.set_uint32(position, 0)  # Sample Period
    position += 4

    key_base = 0x3C
    keymap = getattr(sound, "keymap", None)
    if keymap and keymap.key_base != 0:
        key_base = keymap.key_base
    out_view.set_uint32(position, key_base, True)  # MIDI Unity Note
    position += 4

    # If we don't have a loop, everything following is zero
    if loop is not None:
        out_view.set_uint32(position, 0)  # MIDI Pitch Fraction
        position += 4

        out_view.set_uint32(position, 0)  # SMPTE Format
        position += 4
        out_view.set_uint32(position, 0)  # SMPTE Offset
        position += 4

        # wavHeader[0x24]
        out_view.set_uint32(position, 1, True)  # Number Sample Loops
        position += 4

        out_view.set_uint32(position, 0)  # Sampler data
        position += 4

        if loop.count > 0:
            out_view.set_uint32(position, 0)  # Cue Point ID
            position += 4
            out_view.set_uint32(position, 0)  # Type 0 - Loop forward (normal)
            position += 4

            # wavHeader[0x34]
            out_view.set_uint32(position, loop.start, True)
            position += 4
            out_view.set_uint32(position, loop.end, True)
            position += 4

            out_view.set_uint32(position, 0)  # Fraction
            position += 4

            # wavHeader[0x40] Play Count
            if loop.count == 0xFFFFFFFF:
                # -1
                out_view.set_uint32(position, 0)
            else:
                out_view.set_uint32(position, loop.count, True)
            position += 4
    return position


def extract_wav_from_sound(tbl, sound, sampling_rate):
    """Return a .wav file (bytearray) of an ISound (ALSound or ALSoundSimple)."""
    wave = sound.wave
    tbl_view = DataView(tbl, wave.wave_base)

    if wave.type == ALWaveType.AL_RAW16_WAVE:
        data_chunk_size = wave.wave_len - 2
        wav_file_size = (RIFF_CHUNK_HEADER_SIZE + 4  # "WAVE"
                         + WAV_FMT_CHUNK_SIZE + WAV_DATA_CHUNK_HEADER_SIZE
                         + data_chunk_size + WAV_SMPL_CHUNK_SIZE)
        out_buffer = bytearray(wav_file_size)
        out_view = DataView(out_buffer)
        _write_header(out_view, sampling_rate, data_chunk_size, 0x10)

        # Grab the wave data from the tbl.
        # Skip first and last byte for some reason?
        if data_chunk_size + 1 > tbl_view.byte_length:
            raise IndexError("Offset is outside the bounds of the DataView")
        start = tbl_view.byte_offset + 1
        out_buffer[0x2C:0x2C + data_chunk_size] = tbl_view.buffer[start:start + data_chunk_size]
        position = 0x2C + data_chunk_size

        _write_smpl(out_view, position, sound, wave.raw_wave.loop)
        return out_buffer

    elif wave.type == ALWaveType.AL_ADPCM_WAVE:
        adpcm_wave = wave.adpcm_wave
        if not adpcm_wave or not adpcm_wave.book:
            raise ValueError("Cannot decode AL_ADPCM_WAVE without book")

        samples = decode_vadpcm_samples(tbl_view, wave.wave_len, adpcm_wave.book,
                                        (wave.flags & 0x30) == 0x30)
        num_samples = len(samples)

        # 0x2C + (numSamples * 2) + 0x44;
        wav_file_size = (RIFF_CHUNK_HEADER_SIZE + 4  # "WAVE"
                         + WAV_FMT_CHUNK_SIZE + WAV_DATA_CHUNK_HEADER_SIZE
                         + num_samples * 2 + WAV_SMPL_CHUNK_SIZE)

        out_buffer = bytearray(wav_file_size)
        out_view = DataView(out_buffer)
        _write_header(out_view, sampling_rate, num_samples * 2, WAV_FMT_CHUNK_SIZE - 8)

        # Copy the samples to the data section.
        struct.pack_into("<%dh" % num_samples, out_buffer, 0x2C, *samples)
        position = 0x2C + num_samples * 2

        _write_smpl(out_view, position, sound, adpcm_wave.loop)
        return out_buffer

    else:
        raise ValueError("Unsupported wave type %s" % wave.type)


def read_wav_samples(wav):
    """Return (sample_rate, samples) of a mono 16-bit PCM .wav made by extract_wav_from_sound.

    Stands in for the browser's decodeAudioData on these files.
    """
    view = DataView(bytes(wav))
    sample_rate = view.get_uint32(0x18, True)
    size = view.get_uint32(0x28, True)
    count = size // 2
    samples = struct.unpack_from("<%dh" % count, wav, 0x2C) if count else ()
    return sample_rate, samples
