"""Buy star, MP2 (StarEvent2.ts)."""

from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        "WESTERN": "D52AD53C2FED642C3001C3579B4299C3",  # 0x29E0DC - 0x29E91C ROM
    }

    if hash_equal([data_view.buffer, info["offset"], 0x840], hashes["WESTERN"]):
        return True

    return False


def _write(data_view, event, info, temp):
    # Most of the code lives in the overlay.
    return f"""
      J __PP64_INTERNAL_STAR_SPACE_EVENT ; star_space_event
      NOP
    """


StarEvent2 = Event(parse=_parse, write=_write)
