"""Visit Item Shop, MP3 (ItemShopEvent3.ts)."""

from ....events import Event


def _parse(data_view, info):
    found = False

    # Chilly Waters 0x8010B65C - , spaces 0x7C,0x77 with 0x6E,0x73
    if info["board_index"] == 0:
        if info["offset"] != 0x003211CC:
            return False
        if data_view.get_uint32(info["offset"] + 0x44) != 0x0C03C84F:
            # JAL 0x800F213C
            return False
        # fnLen = getFunctionLength(dataView, info.offset);
        # found = fnLen === ;
        found = True

    if not found:
        return False

    return True


def _write(data_view, event, info, temp):
    # Most of the event remains in the overlay.
    return f"""
      J __PP64_INTERNAL_ITEM_SHOP_EVENT
      NOP
    """


ItemShopEvent3 = Event(parse=_parse, write=_write)
