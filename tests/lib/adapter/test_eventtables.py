"""SpaceEventTable / SpaceEventList against the TypeScript (fixture eventtables.json)."""

import pytest

from partyplanner64.lib.adapter.eventlist import SpaceEventList, create_space_event_list_label
from partyplanner64.lib.adapter.eventtable import SpaceEventTable
from partyplanner64.lib.utils.dataview import DataView

from .conftest import load_fixture

REF = load_fixture("eventtables.json")


def test_event_table_write_parse_assembly():
    ref = REF["table"]
    table = SpaceEventTable()
    for index, address in ref["entries"]:
        table.add(index, address)
    table.add(0, 0x80110018)  # Replacing keeps the position.

    buffer = bytearray(table.byte_length() + 16)
    assert table.write(buffer, 8) == ref["written"]
    assert table.byte_length() == ref["byteLength"]
    assert buffer.hex() == ref["buffer"]
    assert table.get_assembly() == ref["assembly"]

    parsed = SpaceEventTable()
    parsed.parse(buffer, 8)
    entries = []
    parsed.for_each(entries.append)
    assert [[e["space_index"], e["address"]] for e in entries] == \
        [[e["spaceIndex"], e["address"]] for e in ref["parsed"]]

    # A DataView works too.
    parsed2 = SpaceEventTable()
    parsed2.parse(DataView(buffer, 8))
    assert parsed2.entries() == entries


def test_event_table_null_address():
    table = SpaceEventTable()
    table.add(3)
    with pytest.raises(ValueError):
        table.write(bytearray(16), 0)


def test_event_list_write_parse_assembly():
    ref = REF["list"]
    lst = SpaceEventList(7)
    lst.add(1, 2, 0x807B0100)
    lst.add(3, 1, 0x807B0200)
    lst.add(8, 2, 0x80110300)
    lst.set_address(1, -0x7F84FE00)
    buffer = bytearray(lst.byte_length() + 4)
    assert lst.write(buffer, 4) == ref["written"]
    assert lst.byte_length() == ref["byteLength"]
    assert buffer.hex() == ref["buffer"]
    assert lst.get_assembly() == ref["assembly"]
    assert SpaceEventList.byte_length_for(5) == ref["staticByteLength"]

    parsed = SpaceEventList()
    parsed.parse(buffer, 4)
    assert [[e.activation_type, e.execution_type, e.address] for e in parsed.entries()] == ref["parsed"]


def test_event_list_symbolic():
    ref = REF["symList"]
    lst = SpaceEventList(-5)
    lst.add(7, 1, 0)
    lst.add(7, 1, "__PP64_INTERNAL_CURSE_POISON_DICEROLL_EVENT")
    assert lst.get_assembly() == ref["assembly"]
    assert lst.count() == ref["count"]
    with pytest.raises(ValueError) as e:
        lst.write(bytearray(64), 0)
    assert str(e.value) == ref["writeError"]


def test_labels():
    assert [create_space_event_list_label(i) for i in (0, -3, 42)] == REF["labels"]
