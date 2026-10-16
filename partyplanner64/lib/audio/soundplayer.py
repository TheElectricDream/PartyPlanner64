"""Sound effect playback (stands in for audio/soundplayer.ts).

The browser decoded the sound's .wav (extractWavFromSound) with WebAudio
and played it as is; the page now plays the .wav returned here.
"""

from .wav import extract_wav_from_sound


def sound_wav(table, index):
    """Return the .wav file (bytes) of sound effect `index` of sound table `table` of the open ROM."""
    from ..romhandler import romhandler

    audio = romhandler.get_rom().get_audio()
    sound_table = audio.get_sound_table(table)
    if sound_table is None:
        raise ValueError("There is no sound table %s" % table)
    if index < 0 or index >= len(sound_table.sounds):
        raise ValueError("There is no sound %s in sound table %s" % (index, table))

    sound = sound_table.sounds[index]
    return bytes(extract_wav_from_sound(sound_table.tbl, sound, sound.sample_rate))
