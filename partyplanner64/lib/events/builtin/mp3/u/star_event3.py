"""Buy star, MP3 (StarEvent3.ts)."""

from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        "CHILLY": "E9B6C28983AAE724AC187EA8E0CBC79D",  # 0x8010A4B4 - 0x8010A860 (0x00320024 - 0x003203d0)
    }

    if hash_equal([data_view.buffer, info["offset"], 0x3BC], hashes["CHILLY"]):
        return True

    return False


def _write(data_view, event, info, temp):
    # Most of the code lives in the overlay.
    return f"""
      J __PP64_INTERNAL_STAR_SPACE_EVENT ; star_space_event
      NOP
    """


StarEvent3 = Event(parse=_parse, write=_write)
