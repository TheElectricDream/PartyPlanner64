"""ALSound (port of audio/ALSound.ts).

ISound (the TypeScript interface) is anything with env, keymap (optional),
wave, sample_pan, sample_volume and flags: ALSound or ALSoundSimple.
"""

from .al_envelope import ALEnvelope
from .al_key_map import ALKeyMap
from .al_wave_table import ALWaveTable


class ALSound:
    def __init__(self, b1view, sound_offset):
        self.env = None
        self.keymap = None
        self.wave = None
        self.sample_pan = 0
        self.sample_volume = 0
        self.flags = 0
        self._extract(b1view, sound_offset)

    def _extract(self, b1view, sound_offset):
        env_offset = b1view.get_uint32(sound_offset)
        self.env = ALEnvelope(b1view, env_offset)

        keymap_offset = b1view.get_uint32(sound_offset + 4)
        self.keymap = ALKeyMap(b1view, keymap_offset)

        wave_offset = b1view.get_uint32(sound_offset + 8)
        self.wave = ALWaveTable(b1view, wave_offset)

        self.sample_pan = b1view.get_uint8(sound_offset + 12)
        self.sample_volume = b1view.get_uint8(sound_offset + 13)
        self.flags = b1view.get_uint8(sound_offset + 14)
