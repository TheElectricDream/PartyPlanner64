"""ALRAWWaveInfo (port of audio/ALRAWWaveInfo.ts).

Note: the games' bank loader (Mario Party 3 USA 0x80074a9c) treats the loop's offset as
from the bank file's start, like every other offset in the file, while this (as the
original) adds it to the wave info's position. No game bank has RAW16 waves and custom
soundbanks are ADPCM, so the original's reading is kept (the differential tests pin it).
"""

from .al_raw_loop import ALRawLoop


class ALRAWWaveInfo:
    def __init__(self, b1view, offset):
        self.loop = None
        self._extract(b1view, offset)

    def _extract(self, b1view, offset):
        loop_offset = b1view.get_uint32(offset)
        if loop_offset != 0:
            self.loop = ALRawLoop(b1view, offset + loop_offset)
