"""ALKeyMap (port of audio/ALKeyMap.ts)."""


class ALKeyMap:
    def __init__(self, b1view, keymap_offset):
        self.velocity_min = 0
        self.velocity_max = 0
        self.key_min = 0
        self.key_max = 0
        self.key_base = 0
        self.detune = 0
        self._extract(b1view, keymap_offset)

    def _extract(self, b1view, keymap_offset):
        self.velocity_min = b1view.get_uint8(keymap_offset)
        self.velocity_max = b1view.get_uint8(keymap_offset + 1)
        self.key_min = b1view.get_uint8(keymap_offset + 2)
        self.key_max = b1view.get_uint8(keymap_offset + 3)
        self.key_base = b1view.get_uint8(keymap_offset + 4)
        self.detune = b1view.get_int8(keymap_offset + 5)
