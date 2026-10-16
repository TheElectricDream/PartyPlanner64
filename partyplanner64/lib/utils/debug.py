"""Debug output helpers ($$log, $$hex and assert in the TypeScript)."""

import logging

from ..debug import is_debug

logger = logging.getLogger("partyplanner64")


def log(*args):
    """Log the arguments when debug features are on ($$log)."""
    if is_debug():
        logger.debug(" ".join(str(a) for a in args))


def hexstr(num, prefix="0x"):
    """Format a number as upper-case hex, at least two digits ($$hex).

    hexstr(10) == "0x0A", hexstr(-255) == "-0xFF".
    """
    val = "%X" % abs(int(num))
    if len(val) == 1:
        val = "0" + val
    return ("-" if num < 0 else "") + prefix + val


def assert_(condition, message="Assertion failed"):
    """Raise AssertionError if the condition fails, when debug is on (assert)."""
    if is_debug() and not condition:
        raise AssertionError(message)
