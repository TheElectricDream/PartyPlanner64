"""ALADPCMLoop (port of audio/ALADPCMLoop.ts)."""

# https://github.com/derselbst/N64SoundTools/blob/master/N64SoundListTool/N64SoundLibrary/N64AIFCAudio.cpp#L20065


class ALADPCMLoop:
    def __init__(self, view, loop_offset):
        self.start = 0
        self.end = 0
        self.count = 0
        self.state = []  # u16[16]
        self._extract(view, loop_offset)

    def _extract(self, view, loop_offset):
        self.start = view.get_uint32(loop_offset)
        self.end = view.get_uint32(loop_offset + 4)
        self.count = view.get_uint32(loop_offset + 8)
        self.state = [view.get_uint16(loop_offset + 12 + i * 2) for i in range(0x10)]
