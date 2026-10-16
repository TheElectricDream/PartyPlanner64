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
    return f"""
      addiu SP, SP, -0x18
      sw    RA, 0x10(SP)

      ; TODO: Face player towards Boo
      ;jal   GetCurrentSpaceIndex
      ;NOP
      ;sll   V0, V0, 0x10
      ;sra   V1, V0, 0x10
      ;addiu    V0, R0, 10 ; bottom left boo invisible space index
      ;beq   V1, V0, boo_space_event_passing_bottom_boo
      ;addiu    V0, R0, 129 ; upper middle boo invisible space index
      ;bne   V1, V0, boo_space_event_goto_boo_scene
      ;addiu    A0, R0, 101 ; Boo overlay index
      ;addiu    A0, R0, -1
      ;addiu    A1, R0, 8
      ;j     L800F97E0
      ;addiu    A2, R0, 111 ; upper middle boo standing space index
    ;boo_space_event_passing_bottom_boo:
      ;addiu    A0, R0, -1
      ;addiu    A1, R0, 8
      ;addiu    A2, R0, 98 ; bottom left boo standing space index
    ;L800F97E0:
      ;jal   0x8004D2A4
      ;NOP

      addiu A0, R0, 101 ; Boo overlay index
    boo_space_event_goto_boo_scene:
      addu  A1, R0, R0
      jal   0x800587EC  ; 0x800587BC wrapper, A3 = 0 default
      addiu A2, R0, 1
      lw    RA, 0x10(SP)
      jr    RA
      addiu SP, SP, 0x18
    """


BooEvent1 = Event(parse=_parse, write=_write)
