"""ALADPCMBook: the VADPCM predictor codebook (port of audio/ALADPCMBook.ts)."""


class ALADPCMBook:
    def __init__(self, view, offset):
        self.order = 0
        self.npredictors = 0
        self.predictors = []
        self._extract(view, offset)

    def _extract(self, view, offset):
        self.order = view.get_int32(offset)
        self.npredictors = view.get_int32(offset + 4)

        predictor_count = self.order * self.npredictors * 8
        self.predictors = [view.get_int16(offset + 8 + i * 2) for i in range(predictor_count)]
