// Reference tables for tests/lib/adapter/test_soundeffects.py.
import { getSoundEffectMapMP1 } from "../packages/lib/adapter/MP1.U.soundeffects";
import { getSoundEffectMapMP3 } from "../packages/lib/adapter/MP3.U.soundeffects";
import { getAudioMapMP1 } from "../packages/lib/adapter/MP1.U.audio";
console.log(JSON.stringify({
  soundEffectsMP1: [getSoundEffectMapMP1(0), getSoundEffectMapMP1(1)],
  soundEffectsMP3: [getSoundEffectMapMP3(0), getSoundEffectMapMP3(1)],
  audioMP1: [getAudioMapMP1(0), getAudioMapMP1(1), getAudioMapMP1(2)],
}));
