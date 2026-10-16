"""ALRawLoop (port of audio/ALRawLoop.ts)."""


class ALRawLoop:
    def __init__(self, b1view, offset):
        self.start = 0
        self.end = 0
        self.count = 0
        self._extract(b1view, offset)

    def _extract(self, b1view, offset):
        self.start = b1view.get_uint32(offset)
        self.end = b1view.get_uint32(offset + 4)
        self.count = b1view.get_uint32(offset + 8)
