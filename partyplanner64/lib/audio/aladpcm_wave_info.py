"""ALADPCMWaveInfo (port of audio/ALADPCMWaveInfo.ts)."""

from .aladpcm_book import ALADPCMBook
from .aladpcm_loop import ALADPCMLoop


class ALADPCMWaveInfo:
    def __init__(self, view, offset):
        self.loop = None
        self.book = None
        self._extract(view, offset)

    def _extract(self, view, offset):
        loop_offset = view.get_uint32(offset)
        if loop_offset != 0:
            self.loop = ALADPCMLoop(view, loop_offset)

        book_offset = view.get_uint32(offset + 4)
        if book_offset != 0:
            self.book = ALADPCMBook(view, book_offset)
