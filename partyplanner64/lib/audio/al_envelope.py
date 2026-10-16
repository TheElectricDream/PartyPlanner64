"""ALEnvelope (port of audio/ALEnvelope.ts)."""


class ALEnvelope:
    def __init__(self, b1view, env_offset, small_volumes=None):
        self.__small_volumes = small_volumes
        self.attack_time = 0
        self.decay_time = 0
        self.release_time = 0
        self.attack_volume = 0
        self.decay_volume = 0
        self.zero_pad = 0
        self._extract(b1view, env_offset)

    def _extract(self, b1view, env_offset):
        self.attack_time = b1view.get_int32(env_offset)
        self.decay_time = b1view.get_int32(env_offset + 4)
        self.release_time = b1view.get_int32(env_offset + 8)
        if self.__small_volumes:
            # MP2/3
            self.attack_volume = b1view.get_uint8(env_offset + 12)
            self.decay_volume = b1view.get_uint8(env_offset + 13)
        else:
            self.attack_volume = b1view.get_int16(env_offset + 12)
            self.decay_volume = b1view.get_int16(env_offset + 14)
