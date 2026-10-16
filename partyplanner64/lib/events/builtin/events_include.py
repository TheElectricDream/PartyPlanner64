"""Import this module to register the built-in events (events.include.ts).

The events register in the order the TypeScript app registered them (where
the adapters' imports came first), whatever imported them before this module.
"""

from ..event_library import get_event_library_implementation

# The adapters (imported before events.include in the TypeScript bundle) bring these in first.
from .mp1.u import chain_split1  # noqa: F401
from .mp2.u import chain_split2  # noqa: F401
from .mp1.u import chance_time_event1  # noqa: F401
from .mp1.u import star_chance_event1  # noqa: F401
from .mp3.u import chain_split3  # noqa: F401
from .mp3.u import chain_merge_event3  # noqa: F401

from . import events_common  # noqa: F401
from .mp1 import events_mp1  # noqa: F401
from .mp2 import events_mp2  # noqa: F401
from .mp3 import events_mp3  # noqa: F401

BUILTIN_EVENT_ORDER = [
    "CHAINSPLIT1", "CHAINSPLIT2", "CHANCETIME", "STARCHANCE", "CHAINSPLIT3", "CHAINMERGE3",
    "CHAINMERGE", "BOO", "STAR", "BANK", "ITEMSHOP", "GATE", "GATECLOSE", "BOULDERCHASE",
    "BOWSER", "PASSSTART", "THWOMPCHAINSPLIT", "GATECHAINSPLIT", "REVERSECHAINSPLIT",
]


def _put_builtins_in_order():
    events = getattr(get_event_library_implementation(), "_events", None)
    if not isinstance(events, dict):
        return
    ordered = {k: events[k] for k in BUILTIN_EVENT_ORDER if k in events}
    for k, v in events.items():
        if k not in ordered:
            ordered[k] = v
    events.clear()
    events.update(ordered)


_put_builtins_in_order()
