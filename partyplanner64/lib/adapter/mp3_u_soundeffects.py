"""Names of MP3's raw sound effects (port of adapter/MP3.U.soundeffects.ts).

The names are in data/mp3_u_soundeffects.json (index = raw sound index; "" where
unknown). data/mp3_u_playsound_map.txt keeps the original notes on which raw sound
each PlaySound argument plays.
"""

import json
from importlib import resources

_sound_effect_map = None


def _load():
    global _sound_effect_map
    if _sound_effect_map is None:
        path = resources.files(__package__).joinpath("data", "mp3_u_soundeffects.json")
        with path.open("r", encoding="utf-8") as f:
            _sound_effect_map = json.load(f)
    return _sound_effect_map


def get_sound_effect_map_mp3(table):
    """Names of the raw sound effects in the game (the same list for every table)."""
    return _load()
