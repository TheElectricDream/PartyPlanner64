"""ALInst (port of audio/ALInst.ts)."""

from .al_sound import ALSound


class ALInst:
    def __init__(self, b1view, inst_offset):
        self.volume = 0
        self.pan = 0
        self.priority = 0
        self.flags = 0
        self.trem_type = 0
        self.trem_rate = 0
        self.trem_depth = 0
        self.trem_delay = 0
        self.vib_type = 0
        self.vib_rate = 0
        self.vib_depth = 0
        self.vib_delay = 0
        self.bend_range = 0
        self.sounds = []
        self._extract(b1view, inst_offset)

    def _extract(self, b1view, inst_offset):
        self.volume = b1view.get_uint8(inst_offset)
        self.pan = b1view.get_uint8(inst_offset + 1)
        self.priority = b1view.get_uint8(inst_offset + 2)
        self.flags = b1view.get_uint8(inst_offset + 3)
        self.trem_type = b1view.get_uint8(inst_offset + 4)
        self.trem_rate = b1view.get_uint8(inst_offset + 5)
        self.trem_depth = b1view.get_uint8(inst_offset + 6)
        self.trem_delay = b1view.get_uint8(inst_offset + 7)
        self.vib_type = b1view.get_uint8(inst_offset + 8)
        self.vib_rate = b1view.get_uint8(inst_offset + 9)
        self.vib_depth = b1view.get_uint8(inst_offset + 10)
        self.vib_delay = b1view.get_uint8(inst_offset + 11)
        self.bend_range = b1view.get_int16(inst_offset + 12)

        sound_count = b1view.get_int16(inst_offset + 14)
        for i in range(sound_count):
            sound_offset = b1view.get_uint32(inst_offset + 16 + i * 4)
            self.sounds.append(ALSound(b1view, sound_offset))
