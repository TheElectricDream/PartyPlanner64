"""Visit Boo, MP2 (BooEvent2.ts)."""

from ....events import Event


def _parse(data_view, info):
    found = False

    # Western Land 0x10BA48 - 0x8010C44C, spaces 0xAF,0xB4 with boos 0x9D,0x9F
    if info["board_index"] == 0:
        if info["offset"] != 0x002A0D18:
            return False
        # if (dataView.getUint32(info.offset + 0x4C) !== 0x0C03AF32) // JAL 0x800EBCC8
        #   return false;
        # fnLen = getFunctionLength(dataView, info.offset);
        # found = fnLen === 0x11D4;
        found = True

    if not found:
        return False

    return True


def _write(data_view, event, info, temp):
    # Code still lives in the board overlay.
    return f"""@@TPL@@"""


BooEvent2 = Event(parse=_parse, write=_write)
