"""FXD0 (port of audio/FXD0.ts). No idea what this is."""


class FXD0:
    def __init__(self, data_view):
        self.hunks = []
        if data_view.get_uint32(0) != 0x46584430:  # "FXD0"
            raise ValueError("FXD0 constructor encountered non-FXD0 structure")
        self._extract(data_view)

    def _extract(self, view):
        self.hunks = []
        hunk_count = view.get_uint32(4)

        # Seems to be composed of hunks of a fixed size.
        current_offset = 0x10
        for _ in range(hunk_count):
            hunk_offset_end = current_offset + 0x208
            self.hunks.append(bytearray(
                view.buffer[view.byte_offset + current_offset:view.byte_offset + hunk_offset_end]))
            current_offset += 0x208
