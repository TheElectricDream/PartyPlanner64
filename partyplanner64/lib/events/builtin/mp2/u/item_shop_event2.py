"""Visit Item Shop, MP2 (ItemShopEvent2.ts)."""

from ....events import Event


def _parse(data_view, info):
    found = False

    # Western Land 0x80109B30 - 0x8010A13C, space 0xA7 with shop at 0x9A
    if info["board_index"] == 0:
        if info["offset"] != 0x0029EE00:
            return False
        # if (dataView.getUint32(info.offset + 0x44) !== 0x0C03C84F)
        #   return false;
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


ItemShopEvent2 = Event(parse=_parse, write=_write)
