"""The library's events, as the React hooks gave them (port of events/EventHooks.ts)."""

from ..store import store


def use_library_events():
    """The event library (id -> event)."""
    return store.event_library


def use_custom_events():
    """Copies of the custom events in the library."""
    events = []
    library = use_library_events()
    for id in list(library):
        event = library[id]
        if event.custom:
            events.append(event.copy() if hasattr(event, "copy") else event)
    return events
