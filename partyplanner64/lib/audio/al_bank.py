"""ALBank (port of audio/ALBank.ts)."""

from .al_inst import ALInst


class ALBank:
    def __init__(self, b1view, bank_offset):
        self.flags = 0
        self.pad = 0
        self.sample_rate = 0
        self.instruments = []
        self._extract(b1view, bank_offset)

    def _extract(self, b1view, bank_offset):
        self.flags = b1view.get_uint8(bank_offset + 2)
        self.pad = b1view.get_uint8(bank_offset + 3)
        self.sample_rate = b1view.get_int32(bank_offset + 4)

        percussion_offset = b1view.get_uint32(bank_offset + 8)
        if percussion_offset:
            raise ValueError("Need to parse percussion at bank offset 0x%x"
                             % (b1view.byte_offset + bank_offset))

        instrument_count = b1view.get_uint16(bank_offset)
        for i in range(instrument_count):
            instrument_offset = b1view.get_uint32(bank_offset + 12 + i * 4)
            self.instruments.append(ALInst(b1view, instrument_offset))
