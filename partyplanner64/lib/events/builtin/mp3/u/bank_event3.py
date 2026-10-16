"""Visit Bank, MP3 (BankEvent3.ts)."""

from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        # A good chunk...
        "CHILLY": "FCA0025616E8B2BE4CD60F47EE60DC30",  # 0x8010A860 - 0x8010B394 (0x3203D0 ...)
    }

    if hash_equal([data_view.buffer, info["offset"], 0xB4], hashes["CHILLY"]):
        return True

    return False


def _write(data_view, event, info, temp):
    # Code still lives in the overlay itself.
    return f"""
      J __PP64_INTERNAL_BANK_SPACE_EVENT
      NOP
    """


BankEvent3 = Event(parse=_parse, write=_write)
