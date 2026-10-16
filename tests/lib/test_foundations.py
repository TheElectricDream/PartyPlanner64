"""Tests of the hand-written foundations every port builds on."""

import pytest

from partyplanner64.lib.utils.dataview import DataView
from partyplanner64.lib.utils.number import get_raw_float32_format, make_divisible_by
from partyplanner64.lib.utils.offsets import ram_to_rom, rom_to_ram
from partyplanner64.lib.types import EditorEventActivationType, EventActivationType, \
    get_event_activation_type_from_editor_type, get_game_name


def test_dataview_endianness_and_sharing():
    buf = bytearray(8)
    view = DataView(buf)
    view.set_uint32(0, 0x80371240)
    assert buf[:4] == b"\x80\x37\x12\x40"
    view.set_uint16(4, 0x1234, True)
    assert buf[4:6] == b"\x34\x12"
    sub = DataView(buf, 4, 4)
    assert sub.get_uint16(0, True) == 0x1234
    sub.set_uint8(3, 0xFF)
    assert view.get_uint8(7) == 0xFF


def test_dataview_wraps_like_javascript():
    view = DataView(bytearray(4))
    view.set_uint32(0, -1)
    assert view.get_uint32(0) == 0xFFFFFFFF
    assert view.get_int32(0) == -1
    view.set_int16(0, 0xFFFF)
    assert view.get_int16(0) == -1


def test_dataview_bounds():
    view = DataView(bytearray(4))
    with pytest.raises(IndexError):
        view.get_uint32(1)


def test_numbers():
    assert get_raw_float32_format(1.0) == 0x3F800000
    assert make_divisible_by(17, 16) == 32
    assert rom_to_ram(0x1000) == 0x80000400
    assert ram_to_rom(0x80000400) == 0x1000


def test_types():
    assert get_game_name("NMVE") == "MP3_USA"
    assert get_event_activation_type_from_editor_type(
        EditorEventActivationType.AFTER_TURN) == EventActivationType.SPECIAL
