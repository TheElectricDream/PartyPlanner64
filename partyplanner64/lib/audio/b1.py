"""B1: an ALBankFile (port of audio/B1.ts)."""

from .al_bank import ALBank


class B1:
    def __init__(self, data_view):
        self.banks = []
        if data_view.get_uint16(0) != 0x4231:  # "B1"
            raise ValueError("B1 constructor encountered non-B1 structure")
        self._extract(data_view)

    def _extract(self, view):
        bank_count = view.get_uint16(2)
        for i in range(bank_count):
            bank_offset = view.get_uint32(4 + i * 4)
            self.banks.append(ALBank(view, bank_offset))
