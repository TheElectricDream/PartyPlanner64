"""Visit Bank, MP2 (BankEvent2.ts)."""

from ....events import Event


def _parse(data_view, info):
    found = False

    # Western Land 0x8010964C - 0x80109A70, spaces 0x5E,0x8A with banks 0x9B,0x99
    if info["board_index"] == 0:
        if info["offset"] != 0x0029E91C:
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
    # Code still lives in the overlay itself.
    return f"""
      J __PP64_INTERNAL_BANK_SPACE_EVENT
      NOP
    """


BankEvent2 = Event(parse=_parse, write=_write)
