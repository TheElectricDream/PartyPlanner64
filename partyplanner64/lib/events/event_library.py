"""The global event library (EventLibrary.ts)."""


class IEventLibrary:
    """Interface of an event library implementation."""

    def add_event_to_library(self, event):
        raise NotImplementedError()

    def remove_event_from_library(self, event_id):
        raise NotImplementedError()

    def get_event_from_library(self, id):
        raise NotImplementedError()

    def get_events_in_library(self):
        raise NotImplementedError()


class BasicEventLibrary(IEventLibrary):
    """A library kept in a dict, id -> event (in insertion order)."""

    def __init__(self):
        self._events = {}

    def add_event_to_library(self, event):
        self._events[event.id] = event

    def remove_event_from_library(self, event_id):
        if not self._events.get(event_id):
            raise ValueError(
                f"Cannot remove event {event_id}, as it isn't in the event library")

        if not self._events[event_id].custom:
            raise ValueError(
                f"Cannot remove event {event_id}, as it is a built-in event")

        # Note: like the TypeScript, the basic library does not actually delete
        # the event; library implementations that persist events (the editor's)
        # override this.

    def get_event_from_library(self, id):
        return self._events.get(id)

    def get_events_in_library(self):
        return self._events


_event_library = BasicEventLibrary()


def set_event_library_implementation(event_library):
    """Swap in another library implementation, carrying over existing events."""
    global _event_library
    # In the web app, we may have added events to the BasicEventLibrary
    # before this call, and need to transfer them over.
    existing_events = _event_library.get_events_in_library()
    for event_id in list(existing_events):
        event_library.add_event_to_library(existing_events[event_id])

    _event_library = event_library


def get_event_library_implementation():
    """The current library implementation (not in the TypeScript)."""
    return _event_library


def add_event_to_library(event):
    """Adds an event to the global event library."""
    _event_library.add_event_to_library(event)


def remove_event_from_library(event_id):
    _event_library.remove_event_from_library(event_id)


def get_event_from_library(id):
    return _event_library.get_event_from_library(id)


def get_events_in_library():
    return _event_library.get_events_in_library()
