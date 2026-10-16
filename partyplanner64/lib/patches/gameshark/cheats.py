"""The cheats to write into the ROM (port of patches/gameshark/cheats.ts)."""

from ...utils.dataview import DataView

# Compiled cheat buffers (bytearrays). reset_cheats() empties this list in
# place, so modules that imported it keep seeing the current cheats.
current_cheats = []


def reset_cheats():
    del current_cheats[:]


def get_cheat_buffer():
    """All the cheat buffers joined into one."""
    if not current_cheats:
        raise TypeError("Reduce of empty array with no initial value")
    if len(current_cheats) == 1:
        return current_cheats[0]
    return bytearray(b"".join(bytes(c) for c in current_cheats))


def get_cheat_routine_buffer(end_insts=None):
    """Joins all the cheat buffers into one.

    end_insts: if given, a list of instructions to append.
    """
    all_cheats_buffer = get_cheat_buffer()

    buffer_len = len(all_cheats_buffer) + (len(end_insts) * 4 if end_insts else 0)
    full_buffer = bytearray(buffer_len)
    data_view = DataView(full_buffer)

    offset = 0

    # Write cheats
    full_buffer[0:len(all_cheats_buffer)] = all_cheats_buffer
    offset += len(all_cheats_buffer)

    if end_insts:
        for inst in end_insts:
            data_view.set_uint32(offset, inst)
            offset += 4

    return full_buffer
