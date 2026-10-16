"""The event library the editor uses (port of events/ReduxEventLibrary.ts).

The TypeScript kept the library in the Redux store; here it is kept by the
editor store (store.event_library), changed through its library actions.
`set_event_library_implementation(ReduxEventLibrary())` makes it the global
library of partyplanner64.lib.events.event_library.
"""

from ..store import store as _default_store


class ReduxEventLibrary:
    """An IEventLibrary backed by the editor store."""

    def __init__(self, store=None):
        self._store = store or _default_store

    def add_event_to_library(self, event):
        """Adds an event to the global event library."""
        self._store.dispatch("addEventToLibraryAction", {"event": event})

    def remove_event_from_library(self, event_id):
        self._store.dispatch("removeEventFromLibraryAction", {"eventId": event_id})

    def get_event_from_library(self, id):
        return self._store.event_library.get(id)

    def get_events_in_library(self):
        return self._store.event_library
