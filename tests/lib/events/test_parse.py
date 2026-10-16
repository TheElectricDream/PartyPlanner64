"""Built-in events' parse() on synthetic ROM data.

There is no ROM here, so code recognized by MD5 hashes of the original game
code is simulated by patching the events' hash_equal; the logic after the
match (reading chain indices, adding links) is what's tested. Events
recognized by offsets and instruction words are tested directly.
"""

import pytest

from partyplanner64.lib.events import events as events_module
from partyplanner64.lib.events.builtin import events_include  # noqa: F401
from partyplanner64.lib.events.builtin import chain_merge_event
from partyplanner64.lib.events.builtin.events_common import (
    BankEvent, BooEvent, Gate, GateClose, ItemShopEvent, StarEvent)
from partyplanner64.lib.events.builtin.hash_util import hash, hash_equal
from partyplanner64.lib.events.builtin.mp2.u import chain_split2
from partyplanner64.lib.events.builtin.mp3.u import chain_merge_event3, chain_split3
from partyplanner64.lib.events.event_library import add_event_to_library, get_events_in_library
from partyplanner64.lib.events.events import Event
from partyplanner64.lib.types import Game
from partyplanner64.lib.utils.dataview import DataView

from . import romstub


def _board(n=12, links=None):
    return {"game": 3, "spaces": [{"x": 0, "y": 0, "z": 0, "type": 1} for _ in range(n)],
            "links": links if links is not None else {}, "events": {}}


def _info(view, offset, board, game_version, **kw):
    info = {"addr": 0x80100000, "offset": offset, "board": board, "board_index": 0,
            "cur_space": 1, "cur_space_index": 1, "chains": [[0, 1, 2], [3, 4, 5], [6, 7]],
            "game": {1: Game.MP1_USA, 2: Game.MP2_USA, 3: Game.MP3_USA}[game_version],
            "game_version": game_version}
    info.update(kw)
    return info


def test_hash_equal():
    data = bytearray(range(64))
    import hashlib
    assert hash(data, 4, 8) == hashlib.md5(bytes(data[4:12])).hexdigest()
    assert hash_equal([data, 4, 8], hashlib.md5(bytes(data[4:12])).hexdigest().upper())
    assert hash(data, 60, 8) == ""  # Out of bounds.


def test_nothing_matches_random_code(monkeypatch):
    romstub.install(monkeypatch, Game.MP1_USA)
    buf = bytearray(0x4000)  # (GateClose3 scans up to 0x2000 bytes for the function's end.)
    view = DataView(buf)
    for v in (1, 2, 3):
        romstub.install(monkeypatch, {1: Game.MP1_USA, 2: Game.MP2_USA, 3: Game.MP3_USA}[v])
        info = _info(view, 0x100, _board(), v, board_index=5)
        assert events_module.parse(view, info) is False


def test_parse_dispatch(monkeypatch):
    romstub.install(monkeypatch, Game.MP2_USA)
    calls = []

    def parse_args(view, info):
        calls.append(info["offset"])
        return {"x": 1} if info["offset"] == 0x10 else False

    evs = get_events_in_library()
    add_event_to_library(Event(id="ZZTEST", name="t", supported_games=[Game.MP2_USA],
                               parse=parse_args))
    add_event_to_library(Event(id="ZZFAKE", name="f", fake_event=True,
                               supported_games=[Game.MP2_USA],
                               parse=lambda v, i: i["offset"] == 0x20))
    add_event_to_library(Event(id="ZZOTHER", name="o", supported_games=[Game.MP3_USA],
                               parse=lambda v, i: True))
    try:
        view = DataView(bytearray(0x100))
        assert events_module.parse(view, _info(view, 0x10, _board(), 2, board_index=9)) == \
            {"id": "ZZTEST", "args": {"x": 1}}
        assert events_module.parse(view, _info(view, 0x20, _board(), 2, board_index=9)) is True
        assert events_module.parse(view, _info(view, 0x30, _board(), 2, board_index=9)) is False
    finally:
        for id in ("ZZTEST", "ZZFAKE", "ZZOTHER"):
            evs.pop(id, None)


def test_offset_recognized_events():
    big = bytearray(0x330000)
    view = DataView(big)
    # MP2 Western Land: Bank, Boo and Item Shop by offset alone.
    assert BankEvent.parse(view, _info(view, 0x0029E91C, _board(), 2))
    assert not BankEvent.parse(view, _info(view, 0x0029E920, _board(), 2))
    assert not BankEvent.parse(view, _info(view, 0x0029E91C, _board(), 2, board_index=1))
    assert not BankEvent.parse(view, _info(view, 0x0029E91C, _board(), 1))
    assert BooEvent.parse(view, _info(view, 0x002A0D18, _board(), 2))
    assert ItemShopEvent.parse(view, _info(view, 0x0029EE00, _board(), 2))

    # MP3 Chilly Waters item shop: offset + a JAL.
    assert not ItemShopEvent.parse(view, _info(view, 0x003211CC, _board(), 3))
    view.set_uint32(0x003211CC + 0x44, 0x0C03C84F)
    assert ItemShopEvent.parse(view, _info(view, 0x003211CC, _board(), 3))

    # MP3 Chilly Waters boo: offset + JAL + function length 0x11D4.
    off = 0x003239EC
    view.set_uint32(off + 0x4C, 0x0C03AF32)
    assert not BooEvent.parse(view, _info(view, off, _board(), 3))
    view.set_uint32(off + 0x11D4 - 8, 0x03E00008)  # JR RA
    assert BooEvent.parse(view, _info(view, off, _board(), 3))

    # The star events don't parse in MP3.
    assert StarEvent.parse(view, _info(view, off, _board(), 3)) is False


def test_gate_events():
    big = bytearray(0x330000)
    view = DataView(big)
    off = 0x0031F648
    view.set_uint16(off + 0x62, 4)
    view.set_uint16(off + 0x106, 9)
    view.set_uint16(off + 0x6A, 5)
    view.set_uint16(off + 0x10E, 10)
    board = _board()
    assert Gate.parse(view, _info(view, off, board, 3, cur_space_index=4))
    assert board["spaces"][9]["subtype"] == 8
    assert Gate.parse(view, _info(view, off, board, 3, cur_space_index=5))
    assert board["spaces"][10]["subtype"] == 8
    assert not Gate.parse(view, _info(view, off, board, 3, cur_space_index=6))
    assert not Gate.parse(view, _info(view, off, board, 2, cur_space_index=4))

    # GateClose3: a 0x1C function with JAL 0x80108AE8 at +8.
    pytest.importorskip("partyplanner64.lib.utils.mips")
    goff = 0x1000
    view.set_uint32(goff + 0x14, 0x03E00008)
    assert not GateClose.parse(view, _info(view, goff, board, 3))
    view.set_uint32(goff + 8, 0x0C0422BA)
    assert GateClose.parse(view, _info(view, goff, board, 3))
    assert not GateClose.parse(view, _info(view, goff, board, 3, board_index=1))


def _match_all(monkeypatch, module):
    monkeypatch.setattr(module, "hash_equal", lambda args, expected: True)


def test_chain_merge(monkeypatch):
    _match_all(monkeypatch, chain_merge_event)
    view = DataView(bytearray(0x100))
    board = _board()
    view.set_uint16(0x10 + 0x0E, 1)  # chain 1
    view.set_uint16(0x10 + 0x14, 0x2400)
    view.set_uint16(0x10 + 0x16, 2)  # space 2 of chain 1
    assert chain_merge_event.ChainMerge.parse(view, _info(view, 0x10, board, 1, cur_space=7))
    assert board["links"] == {7: 5}
    # R0 for the chain ("way too big") means chain 0; add with R0 means its first space.
    view.set_uint16(0x40 + 0x0E, 0x2821)
    assert chain_merge_event.ChainMerge.parse(view, _info(view, 0x40, board, 1, cur_space=7))
    assert board["links"] == {7: [5, 0]}
    # Out of range space index: no link.
    view.set_uint16(0x60 + 0x0E, 2)
    view.set_uint16(0x60 + 0x14, 1)
    view.set_uint16(0x60 + 0x16, 9)
    assert chain_merge_event.ChainMerge.parse(view, _info(view, 0x60, board, 1, cur_space=8))
    assert 8 not in board["links"]


def test_chain_merge3(monkeypatch):
    _match_all(monkeypatch, chain_merge_event3)
    view = DataView(bytearray(0x100))
    view.set_uint16(0x10 + 0x0E, 2)
    view.set_uint16(0x10 + 0x14, 1)
    view.set_uint16(0x10 + 0x16, 1)
    board = _board()
    # Needs one of the merge helper JALs.
    assert not chain_merge_event3.ChainMerge3.parse(view, _info(view, 0x10, board, 3, cur_space=3))
    view.set_uint32(0x10 + 0x10, 0x0C042307)
    assert chain_merge_event3.ChainMerge3.parse(view, _info(view, 0x10, board, 3, cur_space=3))
    assert board["links"] == {3: 7}
    # A space with links already (going in reverse) isn't a merge.
    assert chain_merge_event3.ChainMerge3.parse(view, _info(view, 0x10, board, 3, cur_space=3)) is False
    board = _board(links={"3": 1})
    assert chain_merge_event3.ChainMerge3.parse(view, _info(view, 0x10, board, 3, cur_space=3)) is False


def test_chain_split3(monkeypatch):
    _match_all(monkeypatch, chain_split3)
    view = DataView(bytearray(0x9000))
    offset = 0x100
    addr = 0x00200100  # (The adapters pass addresses without the 0x80000000 prefix.)
    # LUI/ADDIU pair pointing at 0x80200300 (offset 0x300); lower half has its sign bit set
    # in another case below.
    view.set_uint16(offset + 0x0A, 0x8020)
    view.set_uint16(offset + 0x0E, 0x0300)
    for i, s in enumerate([4, 9, 0xFFFF]):
        view.set_uint16(0x300 + 2 * i, s)
    board = _board()
    assert chain_split3.ChainSplit3.parse(view, _info(view, offset, board, 3, addr=addr, cur_space=2))
    assert board["links"] == {2: [4, 9]}

    view.set_uint16(offset + 0x0A, 0x8021)
    view.set_uint16(offset + 0x0E, 0x8380)  # 0x00218380 - 0x10000 (sign of the ADDIU) = 0x00208380
    for i, s in enumerate([6, 0xFFFF]):
        view.set_uint16(0x8380 + 2 * i, s)
    board = _board()
    assert chain_split3.ChainSplit3.parse(view, _info(view, offset, board, 3, addr=addr, cur_space=1))
    assert board["links"] == {1: 6}


def test_chain_split2(monkeypatch):
    _match_all(monkeypatch, chain_split2)
    view = DataView(bytearray(0x200))
    view.set_uint16(0x10 + 0xEA, 1)
    view.set_uint16(0x10 + 0xEE, 2)
    board = _board()
    assert chain_split2.ChainSplit2.parse(view, _info(view, 0x10, board, 2, cur_space=11))
    assert board["links"] == {11: [3, 6]}


def test_chain_split1(monkeypatch):
    pytest.importorskip("partyplanner64.lib.utils.mips")
    pytest.importorskip("partyplanner64.lib.symbols.symbols")
    from partyplanner64.lib.events.builtin.mp1.u import chain_split1
    from partyplanner64.lib.mips import parse as parse_inst
    from partyplanner64.lib.symbols.symbols import get_symbol

    _match_all(monkeypatch, chain_split1)
    view = DataView(bytearray(0x400))
    offset = 0x40
    addr = 0x800F0040
    view.set_uint16(offset + 0xDA, 0)
    view.set_uint16(offset + 0xDE, 1)
    # LUI A0, 0x800F / ADDIU A0, A0, 0x0200 then JAL RunDecisionTree (tree at offset 0x200).
    view.set_uint16(offset + 0x60 - 6, 0x800F)
    view.set_uint16(offset + 0x60 - 2, 0x0200)
    view.set_uint32(offset + 0x60, parse_inst("JAL %d" % get_symbol(Game.MP1_USA, "RunDecisionTree")))
    view.set_uint32(offset + 0x80, 0x03E00008)
    view.set_uint32(0x200 + 8, 0x00000102)  # One leaf node.
    board = _board()
    assert chain_split1.ChainSplit1.parse(view, _info(view, offset, board, 1, addr=addr, cur_space=2))
    assert board["links"] == {2: [0, 3]}
