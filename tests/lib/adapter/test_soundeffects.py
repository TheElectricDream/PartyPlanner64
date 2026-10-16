"""The sound effect and song name tables match the TypeScript's (gen_soundeffects.ts)."""

import json
import os

from partyplanner64.lib.adapter.mp1_u_audio import get_audio_map_mp1
from partyplanner64.lib.adapter.mp1_u_soundeffects import get_sound_effect_map_mp1
from partyplanner64.lib.adapter.mp3_u_soundeffects import get_sound_effect_map_mp3

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "overlays",
                       "soundeffects.json")

with open(FIXTURE, encoding="utf-8") as _f:
    REF = json.load(_f)


def test_sound_effects_mp1():
    assert [get_sound_effect_map_mp1(0), get_sound_effect_map_mp1(1)] == REF["soundEffectsMP1"]


def test_sound_effects_mp3():
    assert [get_sound_effect_map_mp3(0), get_sound_effect_map_mp3(1)] == REF["soundEffectsMP3"]
    assert get_sound_effect_map_mp3(0)[10] == "Mushroom Growth (Toadstool Titan)"


def test_audio_mp1():
    assert [get_audio_map_mp1(0), get_audio_map_mp1(1), get_audio_map_mp1(2)] == REF["audioMP1"]


def test_playsound_notes_are_packaged():
    from importlib import resources
    for name in ("mp1_u_playsound_map.txt", "mp3_u_playsound_map.txt"):
        text = resources.files("partyplanner64.lib.adapter").joinpath("data", name).read_text()
        assert text.startswith("To actually use the raw sounds")
