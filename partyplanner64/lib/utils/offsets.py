"""ROM <-> RAM offsets (port of utils/offsets.ts)."""


def rom_to_ram(rom_offset):
    """Convert a ROM offset to a RAM offset.

    Does not handle overlay offsets, only simple ones.
    """
    return ((rom_offset - 0xC00) | 0x80000000) & 0xFFFFFFFF


def ram_to_rom(ram_offset):
    """Convert a RAM offset to a ROM offset.

    Does not handle overlay offsets, only simple ones.
    """
    return ((ram_offset + 0xC00) & 0x7FFFFFFF) & 0xFFFFFFFF
