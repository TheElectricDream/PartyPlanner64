"""ALWaveTable (port of audio/ALWaveTable.ts)."""

from enum import IntEnum

from .aladpcm_wave_info import ALADPCMWaveInfo
from .alraw_wave_info import ALRAWWaveInfo


class ALWaveType(IntEnum):
    AL_ADPCM_WAVE = 0
    AL_RAW16_WAVE = 1
    AL_VOX_WAVE = 2
    AL_MUSYX_WAVE = 3
    # AL_SIGNED_RAW8,
    # AL_SIGNED_RAW16


class ALWaveTable:
    def __init__(self, view, wave_offset):
        self.wave_base = 0
        self.wave_len = 0
        self.type = 0
        self.flags = 0
        self.zeroes = 0
        self.loop_offset = 0
        self.predictor_offset = 0
        # Union
        self.adpcm_wave = None
        self.raw_wave = None
        self._extract(view, wave_offset)

    def _extract(self, view, wave_offset):
        self.wave_base = view.get_uint32(wave_offset)  # Offset into TBL
        self.wave_len = view.get_uint32(wave_offset + 4)
        self.type = view.get_uint8(wave_offset + 8)  # ALWaveType
        self.flags = view.get_uint8(wave_offset + 9)

        if self.type == ALWaveType.AL_ADPCM_WAVE:
            self.adpcm_wave = ALADPCMWaveInfo(view, wave_offset + 12)  # not 10?
        elif self.type == ALWaveType.AL_RAW16_WAVE:
            self.raw_wave = ALRAWWaveInfo(view, wave_offset + 12)
        else:
            raise ValueError("Unrecognized ALWaveTable type %s" % self.type)
