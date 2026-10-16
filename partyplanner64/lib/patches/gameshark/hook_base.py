"""The code that runs the cheat routine (port of patches/gameshark/HookBase.ts)."""

from ...mips import parse
from ...utils.mips import get_reg_set_upper_and_lower


class HookBase:
    # Subclasses set these.
    HOOK_RAM_START_OFFSET = None
    HOOK_ROM_START_OFFSET = None
    HOOK_CACHE_DEFAULT_VALUE = None
    MAINFS_CHEAT_FILE = None
    HOOK_JUMP_ROM_OFFSET = None

    def apply(self, rom_buffer):
        raise NotImplementedError("apply not implemented, is that OK?")

    def write_hook_code(self, rom_view):
        from ...adapter.adapters import get_rom_adapter

        adapter = get_rom_adapter({})
        MAINFS_READ_ADDR = adapter and adapter.MAINFS_READ_ADDR
        if not MAINFS_READ_ADDR:
            raise RuntimeError("Cheats were being applied, but the ROM adapter had no MAINFS_READ_ADDR")

        # The first 4 bytes will be reserved to store the pointer to the cheat routine,
        # so we can remember where it is for subsequent frames.
        # The hook will immediately follow.
        offset = self.HOOK_ROM_START_OFFSET + 4

        # T9 = saved off V0 value
        # S7 = saved off RA value
        # A1 = address of cheat routine (either due to reading from cached location, or from the heap call)
        # A2 = "ver!" constant that is initially in RAM

        # Read the cached cheat routine address
        cached_read_locs = get_reg_set_upper_and_lower(self.HOOK_RAM_START_OFFSET)
        insts = [
            "LUI A1 %d" % (0x8000 | cached_read_locs[0]),  # A1 = 0x800C
            "ADDIU A1 A1 %d" % cached_read_locs[1],  # A1 = 0x800CA900
            "LW A1 0(A1)",

            # Check if the cached cheat routine address is legit. If not, this is the first
            # execution and we need to get it
            "LUI A2 %d" % ((self.HOOK_CACHE_DEFAULT_VALUE & 0xFFFFFFFF) >> 16),  # A2 = 0x76650000 "ve"
            "ADDIU A2 A2 %d" % (self.HOOK_CACHE_DEFAULT_VALUE & 0xFFFF),  # A2 = 0x76657221 "ver!"
            "BNE A1 A2 11",  # Jump to the JR A1

            # Prep to call mainfs read
            # Should save off V0 and RA, because they are needed to leave the controller routine properly.
            "ADDU T9 V0 R0",  # T9 <= V0
            "ADDU S7 RA R0",  # S7 <= RA

            # Read from MainFS if we don't have cheat buffer (only happens once)
            "LUI A0 %d" % self.MAINFS_CHEAT_FILE[0],  # A0 <= [The dir index]xxxx
            "JAL %d" % MAINFS_READ_ADDR,
            "ADDIU A0 A0 %d" % self.MAINFS_CHEAT_FILE[1],  # A0 = [dir index][file index]

            # Cache off the cheat location
            "LUI A1 %d" % (0x8000 | cached_read_locs[0]),  # A1 = 0x800C
            "ADDIU A1 A1 %d" % cached_read_locs[1],  # A1 = 0x800CA900
            "SW V0 0(A1)",
            "ADDU A1 V0 R0",  # A1 <= V0

            # Post-JAL cleanup, restore cached regs
            "ADDU V0 T9 R0",  # V0 <= T9
            "ADDU RA S7 R0",  # RA <= S7

            # A1 has the location of the cheat routine... jump to it!
            "JR A1",
        ]
        for inst in insts:
            rom_view.set_uint32(offset, parse(inst))
            offset += 4
        rom_view.set_uint32(offset, 0)  # NOP
