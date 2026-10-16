"""The ultra64.h header made available to C events (ultra64h.ts).

The header text lives in ultra64.h next to this module (it was a large string
in the TypeScript); `ultra64h` holds its contents.
"""

import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ultra64.h")

with open(_PATH, "r", encoding="utf-8", newline="") as _f:
    ultra64h = _f.read()
