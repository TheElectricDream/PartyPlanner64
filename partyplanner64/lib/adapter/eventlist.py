"""Space event lists (port of adapter/eventlist.ts).

An event list holds the events of one space: 8-byte entries (uint16
activation type, uint16 execution type, uint32 address of the event code),
ended by a null entry.
"""

from ..utils.dataview import DataView


class SpaceEventList:
    """Listing of events for a space."""

    def __init__(self, space_index=None):
        self._space_index = space_index
        self._entries = []

    def parse(self, arr, offset=None):
        """Populates this SpaceEventList from an event list existing in the buffer.

        Args:
            arr: A DataView, or a buffer (with offset).
            offset: Where the list starts in the buffer.
        """
        if isinstance(arr, DataView):
            data_view = arr
        else:
            data_view = DataView(arr, offset or 0)
        current_offset = 0
        while True:
            activation_type = data_view.get_uint16(current_offset)
            if activation_type == 0:
                break
            execution_type = data_view.get_uint16(current_offset + 2)
            address = data_view.get_uint32(current_offset + 4)
            self.add(activation_type, execution_type, address)
            current_offset += 8

    def write(self, buffer, offset):
        """Writes the current entries back to the buffer at an offset.

        Returns:
            Length of bytes written (equal to calling byte_length()).
        """
        data_view = DataView(buffer, offset)
        current_offset = 0
        for entry in self._entries:
            if isinstance(entry.address, str):
                raise ValueError("Cannot write event list with symbolic address")
            self._write_entry(data_view, current_offset, entry.activation_type,
                              entry.execution_type, entry.address)
            current_offset += 8
        self._write_entry(data_view, current_offset, 0, 0)
        current_offset += 8

        return current_offset

    def get_assembly(self):
        """Creates the assembly representation of the event list."""
        from ..events.prep_asm import create_event_instance_label

        asm = "%s:\n" % create_space_event_list_label(self._space_index)
        for index, entry in enumerate(self._entries):
            asm += ".halfword %d, %d\n" % (entry.activation_type, entry.execution_type)
            if isinstance(entry.address, str):
                asm += ".word %s\n" % entry.address  # A symbol, write verbatim.
            else:
                asm += ".word %s\n" % create_event_instance_label(self._space_index, index)
        asm += ".word 0, 0\n"
        return asm

    def _write_entry(self, data_view, current_offset, activation_type, execution_type, address=0):
        data_view.set_uint16(current_offset, activation_type)
        data_view.set_uint16(current_offset + 2, execution_type)
        if not address and (activation_type or execution_type):
            raise ValueError("Tried to write null address from SpaceEventList.")
        data_view.set_uint32(current_offset + 4, address)

    def add(self, activation_type, execution_type, address=0):
        self._entries.append(SpaceEventListEntry(activation_type, execution_type, address))

    def set_address(self, entry_index, address=0):
        self._entries[entry_index].address = int(address) & 0xFFFFFFFF

    def for_each(self, fn):
        """Calls fn(entry, index) for each entry."""
        for index, entry in enumerate(self._entries):
            fn(entry, index)

    def entries(self):
        return list(self._entries)

    def count(self):
        return len(self._entries)

    def byte_length(self):
        # Each entry is 8 bytes, plus the last null entry.
        return len(self._entries) * 8 + 8

    @staticmethod
    def byte_length_for(entry_count):
        """SpaceEventList.byteLength(entryCount), the static form."""
        return entry_count * 8 + 8


class SpaceEventListEntry:
    __slots__ = ("activation_type", "execution_type", "address")

    def __init__(self, activation_type, execution_type, address):
        self.activation_type = activation_type
        self.execution_type = execution_type
        self.address = address

    def __repr__(self):
        return "SpaceEventListEntry(%r, %r, %r)" % (
            self.activation_type, self.execution_type, self.address)


def create_space_event_list_label(space_index):
    str_index = ("minus%d" % abs(space_index)) if space_index < 0 else str(space_index)
    return "__PP64_INTERNAL_SPACE_LIST_%s" % str_index
