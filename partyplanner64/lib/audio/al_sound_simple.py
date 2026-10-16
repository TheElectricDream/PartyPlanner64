"""ALSoundSimple: a sound effect's sound (port of audio/ALSoundSimple.ts)."""

from .al_envelope import ALEnvelope
from .al_wave_table import ALWaveTable


class ALSoundSimple:
    def __init__(self, view, offset):
        self.env = None
        self.keymap = None
        self.wave = None
        self.sample_pan = 0
        self.sample_volume = 0
        self.flags = 0
        self.sample_rate = 0
        self._extract(view, offset)

    def _extract(self, view, offset):
        env_offset = view.get_uint32(offset)
        self.env = ALEnvelope(view, env_offset)

        self.sample_rate = view.get_uint32(offset + 4)

        wave_offset = view.get_uint32(offset + 8)
        self.wave = ALWaveTable(view, wave_offset)

        self.sample_pan = view.get_uint8(offset + 12)
        self.sample_volume = view.get_uint8(offset + 13)
        self.flags = view.get_uint8(offset + 14)
