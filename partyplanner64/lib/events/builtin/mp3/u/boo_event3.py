"""Visit Boo, MP3 (BooEvent3.ts)."""

from ....events import Event


def _parse(data_view, info):
    from .....utils.mips import get_function_length

    found = False

    # Chilly Waters 0x8010DE7C - 0x10F050, space 0x92 with 0x6A boo
    if info["board_index"] == 0:
        if info["offset"] != 0x003239EC:
            return False
        if data_view.get_uint32(info["offset"] + 0x4C) != 0x0C03AF32:
            # JAL 0x800EBCC8
            return False
        fn_len = get_function_length(data_view, info["offset"])
        found = fn_len == 0x11D4

    # Deep bloober 0x8010D9E4, space 0x79 with 0x66 boo

    if not found:
        return False

    return True


def _write(data_view, event, info, temp):
    # Code still lives in the board overlay.
    return f"""
      J __PP64_INTERNAL_BOO_SPACE_EVENT
      NOP
    """


BooEvent3 = Event(parse=_parse, write=_write)
