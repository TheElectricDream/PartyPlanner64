"""Installs a Gameshark hook for MP3 (U) (port of patches/gameshark/hook.MP3.U.ts)."""

from ...mips import parse
from ...utils.dataview import DataView
from .cheats import get_cheat_routine_buffer
from .hook_base import HookBase

class MP3UHook(HookBase):
    # File to store the cheat routine.
    MAINFS_CHEAT_FILE = [0, 149]

    # Location safe to write a small set of hooking code
    HOOK_ROM_START_OFFSET = 0xA7830
    HOOK_RAM_START_OFFSET = 0xA6C30

    # Use controller routine 0x80078E98 (ROM 0x79A98) to reach the hook
    HOOK_JUMP_ROM_OFFSET = 0x79A98

    # Value initially in the spot we cache the hook routine.
    HOOK_CACHE_DEFAULT_VALUE = 0x76657221

    def apply(self, rom_buffer):
        rom_view = rom_buffer if isinstance(rom_buffer, DataView) else DataView(rom_buffer)
        self.apply_hook(rom_view)
        self.write_hook_code(rom_view)

    def apply_hook(self, rom_view):
        # Jump out from the controller routine to a small fixed position hook.
        # This hook will read the cheat buffer (if not already read) and jump to it.
        from ...romhandler import romhandler

        hook_j = parse("J %d" % (self.HOOK_RAM_START_OFFSET + 4))

        # Remember the stack adjustment, and NOP it out here.
        end_insts = [
            rom_view.get_uint32(self.HOOK_JUMP_ROM_OFFSET),
            rom_view.get_uint32(self.HOOK_JUMP_ROM_OFFSET + 4),
            rom_view.get_uint32(self.HOOK_JUMP_ROM_OFFSET + 8),
        ]
        rom_view.set_uint32(self.HOOK_JUMP_ROM_OFFSET, hook_j)
        rom_view.set_uint32(self.HOOK_JUMP_ROM_OFFSET + 4, 0)
        rom_view.set_uint32(self.HOOK_JUMP_ROM_OFFSET + 8, 0)

        cheat_routine = get_cheat_routine_buffer(end_insts=end_insts)
        mainfs = romhandler.get_rom().get_main_fs()
        mainfs.write(self.MAINFS_CHEAT_FILE[0], self.MAINFS_CHEAT_FILE[1], cheat_routine)


# The singleton the original exports.
MP3UHook = MP3UHook()
