"""Boo space event parsing/writing for MP1 (BooEvent1.ts)."""

from ....events import Event
from ...hash_util import hash_equal


def _parse(data_view, info):
    hashes = {
        # Single Boo hashes
        "PLAYER_DIRECTION_CHANGE": "DAD5E635FE90ED982D02B3F1D5C0CE21",  # +0x14
        "METHOD_END": "FF104A680C0ECE615B5A24AD95A908CC",  # [0x1C/0x54]+0x18

        # DK specific method
        "DK_TWOBOO_METHOD_START": "94A87B51D2478E81AAC34F7D3C5C37F2",  # +0x28
    }

    offset = info["offset"]
    if hash_equal([data_view.buffer, offset + 0x1C, 0x18], hashes["METHOD_END"]) and \
            hash_equal([data_view.buffer, offset, 0x14], hashes["PLAYER_DIRECTION_CHANGE"]):
        # Check whether this points to the Boo scene.
        scene_num = data_view.get_uint16(offset + 0x1A)
        return scene_num == 0x65
    elif hash_equal([data_view.buffer, offset + 0x54, 0x18], hashes["METHOD_END"]) and \
            hash_equal([data_view.buffer, offset, 0x28], hashes["DK_TWOBOO_METHOD_START"]):
        return True  # We know this is stock DK board.

    return False


def _write(data_view, event, info, temp):
    return f"""@@TPL@@"""


BooEvent1 = Event(parse=_parse, write=_write)
