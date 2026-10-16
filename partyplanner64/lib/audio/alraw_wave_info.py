"""ALRAWWaveInfo (port of audio/ALRAWWaveInfo.ts)."""

from .al_raw_loop import ALRawLoop


class ALRAWWaveInfo:
    def __init__(self, b1view, offset):
        self.loop = None
        self._extract(b1view, offset)

    def _extract(self, b1view, offset):
        loop_offset = b1view.get_uint32(offset)
        if loop_offset != 0:
            self.loop = ALRawLoop(b1view, offset + loop_offset)
