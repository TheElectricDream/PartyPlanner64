"""Space event tables (port of adapter/eventtable.ts).

A space event table lists, for each space with events, the address of the
space's event list: 8-byte entries (int16 space index, 2 bytes padding,
uint32 address), ended by a 0xFFFF space index.
"""

from ..utils.dataview import DataView
from ._js import js_keys
from .eventlist import create_space_event_list_label


class SpaceEventTable:
    def __init__(self):
        # Keyed by space index. Iterated in JavaScript object key order
        # (non-negative indices ascending, then negative ones as added),
        # like the original's plain object.
        self._entries = {}

    def parse(self, arr, offset=None):
        """Populates this SpaceEventTable from an event table existing in the buffer.

        Args:
            arr: A DataView, or a buffer (with offset).
            offset: Where the table starts in the buffer.
        """
        if isinstance(arr, DataView):
            data_view = arr
        else:
            data_view = DataView(arr, offset or 0)
        current_offset = 0
        while True:
            space_index = data_view.get_int16(current_offset)
            if space_index == -1:
                break
            address = data_view.get_uint32(current_offset + 4)
            self.add(space_index, address)
            current_offset += 8

    def write(self, buffer, offset):
        """Writes the current entries back to the buffer at an offset.

        Returns:
            Length of bytes written (equal to calling byte_length()).
        """
        data_view = DataView(buffer, offset)
        current_offset = 0
        for space_index in self._ordered_keys():
            self._write_entry(data_view, current_offset, space_index, self._entries[space_index])
            current_offset += 8
        self._write_entry(data_view, current_offset, 0xFFFF, 0)
        current_offset += 8

        return current_offset

    def get_assembly(self):
        """Creates the assembly representation of the event table."""
        asm = "__PP64_INTERNAL_SPACE_TABLE:\n"
        for space_index in self._ordered_keys():
            asm += (".halfword %d, 0\n       .word %s\n"
                    % (space_index, create_space_event_list_label(space_index)))
        asm += ".halfword 0xFFFF, 0, 0, 0\n"
        return asm

    def _write_entry(self, data_view, current_offset, space_index, address):
        data_view.set_uint16(current_offset, space_index)
        data_view.set_uint16(current_offset + 2, 0)  # Just to be sure
        if not address and space_index != 0xFFFF:
            raise ValueError(
                "Tried to write null address from SpaceEventTable at space index %d." % space_index)
        data_view.set_uint32(current_offset + 4, address)

    def add(self, space_index, address=0):
        self._entries[int(space_index)] = address

    def for_each(self, fn):
        """Calls fn({"space_index", "address"}) for each entry."""
        for space_index in self._ordered_keys():
            fn({"space_index": space_index, "address": self._entries[space_index]})

    def entries(self):
        """Return the entries as a list of {"space_index", "address"} dicts."""
        return [{"space_index": i, "address": self._entries[i]} for i in self._ordered_keys()]

    def byte_length(self):
        # Each entry is 8 bytes, plus the last 0xFFFF entry.
        return len(self._entries) * 8 + 8

    def _ordered_keys(self):
        return js_keys(self._entries)
