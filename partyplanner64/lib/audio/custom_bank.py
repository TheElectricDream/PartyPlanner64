"""Custom soundbanks: instruments of your own for a board's custom songs.

A board keeps its custom soundbanks in board["soundbanks"]; a custom song plays one
of them when its audio entry has "customSoundbank" (an index into that list). When
the board is written, each soundbank it uses is appended to the ROM's bank file (B1)
after the game's own banks, and its samples to the sound data (TBL) after the game's.

A soundbank (JSON, as boards store it):

    {"name": "Game Boy", "instruments": [instrument, ...]}

An instrument (its program number in the MIDI is its position in the list):

    {"name": "Pulse 25%", "volume": 0-127, "pan": 0-127 (64 is the middle),
     "attack": ms, "decay": ms, "sustain": 0-127, "release": ms,
     "source": one of
        {"type": "pulse", "duty": 0.125 | 0.25 | 0.5 | 0.75}     Game Boy pulse channels
        {"type": "wave", "pattern": "0123...EF" (32 hex digits)}  Game Boy wave channel RAM
        {"type": "noise", "short": false}                         Game Boy noise (short: 7-bit)
        {"type": "sample", "data": "data:audio/wav;base64,...",   a recording (16-bit mono
         "key": 60, "detune": 0, "loopStart": n, "loopEnd": n}     32 kHz wav, as import_wav makes)
    }

A "sample" plays at its own pitch on "key" (MIDI note; "detune" in cents); loopStart and
loopEnd (in samples) make it sustain, without them it plays once. Synthesized sources play
in tune on every key.

How the game reads a bank file (Mario Party 3 USA, its bank loader at 0x80074870 and the
functions it calls): the file starts with "B1" (0x4231), a bank count (s16) and the banks'
offsets (u32 each, from the file's start). Each structure is fixed up once, guarded by a
flag byte; every offset is turned into an address by adding the file's address, and a wave's
base by adding the sound data's address:

    ALBank   +0 s16 instrument count, +2 u8 flag, +3 pad, +4 s32 sample rate,
             +8 percussion (an ALInst offset or 0), +12 instrument offsets
    ALInst   +0 volume, +1 pan, +2 priority, +3 flag, +4..+11 tremolo/vibrato,
             +12 s16 bend range (cents), +14 s16 sound count, +16 sound offsets
    ALSound  +0 envelope, +4 key map, +8 wave table offsets, +12 pan, +13 volume, +14 flag
    ALWaveTable  +0 base (in the sound data), +4 length (bytes), +8 type (0 ADPCM,
             1 RAW16), +9 flag, +12 loop offset (or 0), +16 ADPCM book offset
    ALEnvelope   +0 attack, +4 decay, +8 release (s32 microseconds), +12 attack volume,
             +13 decay volume (u8)
    ALKeyMap +0 velocity min, +1 max, +2 key min, +3 key max, +4 key base, +5 s8 detune
    ALADPCMLoop  +0 start, +4 end (samples), +8 count (0xFFFFFFFF: forever),
             +12 state (16 s16: the decoded samples of the frame holding the loop start)
    ALADPCMBook  +0 s32 order (2), +4 s32 predictor count, +8 s16 [count][order][8]

Custom samples are ADPCM, like every sample of the games' own banks (see encode_adpcm).
The games' RAW16 path exists (Mario Party 3 USA reads RAW16 at 0x80074054) but the
emulators' high-level audio plays it wrongly, so it isn't used. A sample is played at most
an octave above its base key (the resampler's limit), so each source is split into bands of
keys, each with its own copy of the sound, pitched for its band.
"""

import base64
import cmath
import hashlib
import json
import math
import struct

SAMPLE_RATE = 32000

# Bytes of the games' audio heaps that custom soundbanks may use. The whole bank file is
# loaded into the heap at boot (the samples stay in the ROM); a bank file that doesn't fit
# hangs the game there. Mario Party 3 USA: the heap is 0x80000 bytes at 0x802E0000 (its
# audio config, set at 0x8000e6b4) and 11200 of them are free after boot with the game's
# own banks (measured in an emulator); about 1 KB is kept spare.
BANK_BUDGET = {"MP3_USA": 10000}
_B1_MAGIC = 0x4231
_LOOP_FOREVER = 0xFFFFFFFF

# Bands of MIDI keys: (first key, last key, key the band's sound is made for).
# The sound is pitched down for the rest of the band (never up past its key).
_BANDS = [(0, 35, 35), (36, 47, 47), (48, 59, 59), (60, 71, 71), (72, 83, 83),
          (84, 95, 95), (96, 107, 107), (108, 127, 119)]

_MIN_CYCLES = 7             # a synthesized loop holds at least this many periods (so the
                            # detune that tunes it stays within its +-127 cents)
_TOP_HARMONIC_HZ = 15000    # band-limit synthesized sounds below this
# Sample units per unit of a Game Boy wave (steps of -1..1): every source swings the same,
# as the Game Boy's channels do, and a 12.5% pulse (off-centre once its DC is gone) fits.
_LEVEL = 14000
_SAMPLE_TYPES = ("pulse", "wave", "noise", "sample")


class SoundbankError(ValueError):
    pass


# --- Defaults and checking --------------------------------------------------------

def default_instrument(name, source, **kw):
    inst = {"name": name, "volume": 110, "pan": 64, "attack": 0, "decay": 1, "sustain": 127,
            "release": 20, "source": source}
    inst.update(kw)
    return inst


def game_boy_bank(name="Game Boy"):
    """The Game Boy's sound chip as a soundbank: programs 0-2 pulse (12.5, 25, 50% duty;
    75% sounds the same as 25%), 3-5 wave channel (triangle, sawtooth, square), 6-7 noise
    (long, short)."""
    return {"name": name, "instruments": [
        default_instrument("Pulse 12.5%", {"type": "pulse", "duty": 0.125}),
        default_instrument("Pulse 25%", {"type": "pulse", "duty": 0.25}),
        default_instrument("Pulse 50%", {"type": "pulse", "duty": 0.5}),
        default_instrument("Wave Triangle", {"type": "wave", "pattern": "0123456789ABCDEFFEDCBA9876543210"}),
        default_instrument("Wave Sawtooth", {"type": "wave", "pattern": "00112233445566778899AABBCCDDEEFF"}),
        default_instrument("Wave Square", {"type": "wave", "pattern": "FFFFFFFFFFFFFFFF0000000000000000"}),
        default_instrument("Noise", {"type": "noise", "short": False}, release=10),
        default_instrument("Noise (Short)", {"type": "noise", "short": True}, release=10),
    ]}


def check_soundbank(bank):
    """What is wrong with a soundbank, or None. (Boards are checked before writing.)"""
    if not isinstance(bank, dict):
        return "A soundbank must be an object."
    insts = bank.get("instruments")
    if not isinstance(insts, list) or not insts:
        return "Soundbank \"%s\" has no instruments." % bank.get("name", "")
    if len(insts) > 128:
        return "Soundbank \"%s\" has more than 128 instruments." % bank.get("name", "")
    for i, inst in enumerate(insts):
        problem = _check_instrument(inst)
        if problem:
            return "Soundbank \"%s\", instrument %d: %s" % (bank.get("name", ""), i, problem)
    return None


def _check_instrument(inst):
    if not isinstance(inst, dict):
        return "not an object."
    for key, lo, hi in (("volume", 0, 127), ("pan", 0, 127), ("sustain", 0, 127),
                        ("attack", 0, 60000), ("decay", 0, 60000), ("release", 0, 60000)):
        v = inst.get(key)
        if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi):
            return "%s must be a number from %d to %d." % (key, lo, hi)
    src = inst.get("source")
    if not isinstance(src, dict) or src.get("type") not in _SAMPLE_TYPES:
        return "source type must be one of %s." % ", ".join(_SAMPLE_TYPES)
    t = src["type"]
    if t == "pulse" and src.get("duty") not in (0.125, 0.25, 0.5, 0.75):
        return "pulse duty must be 0.125, 0.25, 0.5 or 0.75."
    if t == "wave":
        p = src.get("pattern")
        if not isinstance(p, str) or len(p) != 32 or any(c not in "0123456789abcdefABCDEF" for c in p):
            return "wave pattern must be 32 hex digits."
    if t == "sample":
        try:
            pcm = sample_pcm(src)
        except Exception as e:  # noqa: BLE001 - any decoding problem is the user's file
            return "sample data could not be read (%s)." % e
        if not pcm:
            return "the sample is empty."
        key = src.get("key", 60)
        if not isinstance(key, int) or not 0 <= key <= 127:
            return "key must be 0-127."
        ls, le = src.get("loopStart"), src.get("loopEnd")
        if ls is not None or le is not None:
            if not isinstance(ls, int) or not isinstance(le, int) or not 0 <= ls < le <= len(pcm):
                return "loopStart and loopEnd must be sample positions with start < end <= length."
    return None


# --- Sound synthesis -------------------------------------------------------------

def _midi_hz(key):
    return 440.0 * 2.0 ** ((key - 69) / 12.0)


def _ifft_real(spectrum):
    """Real signal from a half spectrum (bins 0..n/2) of a power-of-two length n = 2*(len-1)."""
    n = 2 * (len(spectrum) - 1)
    full = list(spectrum) + [c.conjugate() for c in reversed(spectrum[1:-1])]
    # Iterative radix-2 FFT with conjugate trick: ifft(x) = conj(fft(conj(x))) / n
    a = [c.conjugate() for c in full]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        w_step = cmath.exp(-2j * math.pi / size)
        half = size // 2
        for start in range(0, n, size):
            w = 1.0
            for k in range(half):
                u = a[start + k]
                v = a[start + k + half] * w
                a[start + k] = u + v
                a[start + k + half] = u - v
                w *= w_step
        size *= 2
    return [c.conjugate().real / n for c in a]


def _loop_length(hz):
    """The power-of-two loop length (at least 512) that holds _MIN_CYCLES periods of hz."""
    n = 512
    while n * hz / SAMPLE_RATE < _MIN_CYCLES:
        n *= 2
    return n


def _periodic_loop(harmonics, cycles, n):
    """A loop of n (a power of two) samples holding `cycles` periods of the wave
    sum over h of Re(a_h e^{i2πht}) (harmonics a_1, a_2, ...), at _LEVEL per unit."""
    spec = [0j] * (n // 2 + 1)
    for h, amp in enumerate(harmonics, start=1):
        b = h * cycles
        if b >= n // 2:
            break
        spec[b] = amp * n / 2
    sig = _ifft_real(spec)
    return [max(-32768, min(32767, int(round(v * _LEVEL)))) for v in sig]


def _wave_harmonics(steps, f0):
    """Complex harmonic amplitudes (2 c_h, h = 1, 2, ... below _TOP_HARMONIC_HZ) of one
    period made of equal steps (values -1..1), c_h being its Fourier coefficients."""
    m = len(steps)
    out = []
    h = 1
    while h * f0 < _TOP_HARMONIC_HZ:
        # Fourier coefficient of a stepped wave: sum over steps of value * (integral of e^-i2πht).
        c = 0j
        for s, v in enumerate(steps):
            t0, t1 = s / m, (s + 1) / m
            c += v * (cmath.exp(-2j * math.pi * h * t1) - cmath.exp(-2j * math.pi * h * t0)) / (-2j * math.pi * h)
        # x(t) = sum over h of 2 Re(c_h e^{i2πht}), so harmonic h's amplitude is 2 c_h.
        out.append(2 * c)
        h += 1
    return out


def _synth_band(src, band_key):
    """(pcm, key, detune) for one band of a synthesized source: a loop tuned to band_key."""
    t = src["type"]
    target = _midi_hz(band_key)
    if t == "noise":
        return _noise_band(src, band_key)
    n = _loop_length(target)
    cycles = max(1, int(round(n * target / SAMPLE_RATE)))
    exact = cycles * SAMPLE_RATE / n
    if t == "pulse":
        duty = src["duty"]
        steps = [1.0 if s < duty * 8 else -1.0 for s in range(8)]
    else:  # wave: 4-bit levels, centered
        steps = [(int(c, 16) - 7.5) / 7.5 for c in src["pattern"]]
    harmonics = _wave_harmonics(steps, exact)
    if not harmonics or all(abs(c) < 1e-9 for c in harmonics):
        pcm = [0] * n
    else:
        pcm = _periodic_loop(harmonics, cycles, n)
    detune = int(round(1200 * math.log2(target / exact)))
    return pcm, band_key, detune


def _noise_band(src, band_key):
    """Game Boy noise: an LFSR clocked at a rate that rises with the key (key 60 ~ 4 kHz)."""
    clock = 4096.0 * 2.0 ** ((band_key - 60) / 12.0)
    short = bool(src.get("short"))
    lfsr = 0x7FFF
    n = 4096
    out = []
    hold = SAMPLE_RATE / clock
    acc = 0.0
    level = _LEVEL
    for _ in range(n):
        acc += 1.0
        while acc >= hold:
            acc -= hold
            # The Game Boy's LFSR: bit 0 XOR bit 1 shifts in at bit 14 (and bit 6 when short);
            # the output is bit 0, inverted.
            bit = (lfsr ^ (lfsr >> 1)) & 1
            lfsr = (lfsr >> 1) | (bit << 14)
            if short:
                lfsr = (lfsr & ~(1 << 6)) | (bit << 6)
            level = -_LEVEL if lfsr & 1 else _LEVEL
        out.append(level)
    return out, band_key, 0


# --- Recordings ------------------------------------------------------------------

def _data_url_bytes(url):
    if not isinstance(url, str) or "," not in url:
        raise SoundbankError("not a data URL")
    return base64.b64decode(url.split(",", 1)[1])


def read_wav(data):
    """(rate, channels as lists of floats -1..1, loop or None) of a .wav file's bytes.
    Handles 8/16/24/32-bit PCM and 32-bit float; loop from a "smpl" chunk."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise SoundbankError("not a WAV file")
    pos = 12
    fmt = None
    frames = None
    loop = None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag, chans, rate = struct.unpack_from("<HHI", body, 0)
            bits = struct.unpack_from("<H", body, 14)[0]
            if tag == 0xFFFE and len(body) >= 26:
                tag = struct.unpack_from("<H", body, 24)[0]
            fmt = (tag, chans, rate, bits)
        elif cid == b"data":
            frames = body
        elif cid == b"smpl" and len(body) >= 36 + 24:
            count = struct.unpack_from("<I", body, 28)[0]
            if count:
                start, end = struct.unpack_from("<II", body, 36 + 8)
                loop = (start, end + 1)
        pos += 8 + size + (size & 1)
    if fmt is None or frames is None:
        raise SoundbankError("WAV file without fmt or data")
    tag, chans, rate, bits = fmt
    if chans < 1:
        raise SoundbankError("WAV file without channels")
    width = bits // 8
    count = len(frames) // (width * chans)
    if tag == 3 and bits == 32:
        vals = struct.unpack_from("<%df" % (count * chans), frames)
    elif tag == 1 and bits == 16:
        vals = [v / 32768.0 for v in struct.unpack_from("<%dh" % (count * chans), frames)]
    elif tag == 1 and bits == 8:
        vals = [(b - 128) / 128.0 for b in frames[:count * chans]]
    elif tag == 1 and bits == 24:
        vals = []
        for i in range(count * chans):
            b = frames[i * 3:i * 3 + 3]
            v = b[0] | (b[1] << 8) | (b[2] << 16)
            vals.append((v - (1 << 24) if v & 0x800000 else v) / 8388608.0)
    elif tag == 1 and bits == 32:
        vals = [v / 2147483648.0 for v in struct.unpack_from("<%di" % (count * chans), frames)]
    else:
        raise SoundbankError("unsupported WAV format (%d-bit, format %d)" % (bits, tag))
    channels = [list(vals[c::chans]) for c in range(chans)]
    return rate, channels, loop


def _resample(x, ratio):
    """Linear resampling by ratio (output rate / input rate)."""
    if ratio == 1.0:
        return list(x)
    n = max(1, int(len(x) * ratio))
    out = []
    last = len(x) - 1
    for i in range(n):
        p = i / ratio
        j = int(p)
        f = p - j
        a = x[min(j, last)]
        b = x[min(j + 1, last)]
        out.append(a + (b - a) * f)
    return out


def import_wav(data, name="Sample", key=60):
    """An instrument made from a .wav file's bytes: mono, 32 kHz, 16-bit, loop points kept."""
    rate, channels, loop = read_wav(data)
    mono = [sum(v) / len(channels) for v in zip(*channels)]
    ratio = SAMPLE_RATE / rate
    pcm = _resample(mono, ratio)
    peak = max(1e-9, max(abs(v) for v in pcm)) if pcm else 1
    scale = 32000 / peak if peak > 1.0 else 32767
    ints = [max(-32768, min(32767, int(round(v * scale)))) for v in pcm]
    src = {"type": "sample", "data": "data:audio/wav;base64," + base64.b64encode(pcm16_wav(ints)).decode(),
           "key": key, "detune": 0}
    if loop:
        s, e = int(loop[0] * ratio), min(len(ints), int(loop[1] * ratio))
        if 0 <= s < e:
            src["loopStart"], src["loopEnd"] = s, e
    return default_instrument(name, src, release=100)


def pcm16_wav(samples, rate=SAMPLE_RATE):
    data = struct.pack("<%dh" % len(samples), *samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


def sample_pcm(src):
    """The 16-bit samples of a "sample" source (32 kHz)."""
    rate, channels, _ = read_wav(_data_url_bytes(src.get("data")))
    mono = [sum(v) / len(channels) for v in zip(*channels)]
    if rate != SAMPLE_RATE:
        mono = _resample(mono, SAMPLE_RATE / rate)
    return [max(-32768, min(32767, int(round(v * 32767)))) for v in mono]


def _sample_bands(src):
    """[(key min, key max, pcm, base key, detune, loop)] for a recording: its own pitch for
    the keys up to an octave above it, then copies an octave higher each (half as long)."""
    pcm = sample_pcm(src)
    key = int(src.get("key", 60))
    detune = int(src.get("detune", 0))
    loop = (src["loopStart"], src["loopEnd"]) if src.get("loopEnd") else None
    out = []
    lo, base = 0, key
    while True:
        hi = 127 if base + 11 >= 127 else base + 11
        out.append((lo, hi, pcm, base, detune, loop))
        if hi >= 127 or len(pcm) < 64:
            if hi < 127:
                out[-1] = (lo, 127, pcm, base, detune, loop)
            break
        # An octave up: average pairs (a gentle low-pass) and keep every other sample.
        pcm = [(pcm[i] + pcm[i + 1]) // 2 for i in range(0, len(pcm) - 1, 2)]
        if loop:
            loop = (loop[0] // 2, max(loop[0] // 2 + 1, loop[1] // 2))
        lo, base = hi + 1, base + 12
    return out


def instrument_sounds(inst):
    """[(key min, key max, pcm, base key, detune, loop or None)] for an instrument."""
    src = inst["source"]
    if src["type"] == "sample":
        return _sample_bands(src)
    out = []
    for lo, hi, key in _BANDS:
        pcm, base, detune = _synth_band(src, key)
        out.append((lo, hi, pcm, base, detune, (0, len(pcm))))
    return out


# --- ADPCM ----------------------------------------------------------------------

_ITABLE = (0, 1, 2, 3, 4, 5, 6, 7, -8, -7, -6, -5, -4, -3, -2, -1)


def _expand_predictor(a1, a2):
    """A book entry (16 s16) for s[n] = a1 s[n-1] + a2 s[n-2]: the first 8 values weigh
    s[-2] and the second 8 weigh s[-1] (and the corrections) for the frame's samples,
    in 1/2048ths, as the decoder (vadpcm.py) uses them."""
    def response(y2, y1):
        out = []
        for _ in range(8):
            y = a1 * y1 + a2 * y2
            out.append(y)
            y2, y1 = y1, y
        return out
    clamp = lambda v: max(-32768, min(32767, int(round(v * 2048))))
    return [clamp(v) for v in response(1.0, 0.0)] + [clamp(v) for v in response(0.0, 1.0)]


def _lpc2(x):
    """Second-order linear prediction coefficients (a1, a2) of a signal."""
    n = len(x)
    r0 = sum(v * v for v in x) or 1.0
    r1 = sum(x[i] * x[i - 1] for i in range(1, n))
    r2 = sum(x[i] * x[i - 2] for i in range(2, n))
    det = r0 * r0 - r1 * r1
    if abs(det) < 1e-9:
        return 1.0, 0.0
    a1 = (r1 * r0 - r1 * r2) / det
    a2 = (r2 * r0 - r1 * r1) / det
    # Keep it stable (both poles inside the unit circle).
    a2 = max(-0.98, min(0.98, a2))
    a1 = max(-(1 - a2) * 0.999 + 1e-9, min((1 - a2) * 0.999, a1)) if a2 < 1 else a1
    return a1, a2


def _decode_half(nibbles, scale, p1, p2, h2, h1):
    """The decoder's 8 samples (vadpcm._decode_block) for 4-bit corrections at a scale."""
    tmp = [((_ITABLE[n & 15] << scale) + 0x8000 & 0xFFFF) - 0x8000 for n in nibbles]
    out = []
    for i in range(8):
        total = p1[i] * h2 + p2[i] * h1
        for x in range(i):
            total += tmp[i - 1 - x] * p2[x]
        r = ((tmp[i] << 11) + total + 0x80000000 & 0xFFFFFFFF) - 0x80000000
        r >>= 11
        out.append(32767 if r > 32767 else -32768 if r < -32768 else r)
    return out


def _encode_half(target, scale, p1, p2, h2, h1):
    """(nibbles, decoded, squared error) choosing each correction to land nearest the target."""
    tmp = []
    nibbles = []
    out = []
    err = 0
    step = 1 << scale
    for i in range(8):
        total = p1[i] * h2 + p2[i] * h1
        for x in range(i):
            total += tmp[i - 1 - x] * p2[x]
        base = total >> 11 if total >= 0 else -((-total + 2047) >> 11)  # floor(total / 2048)
        want = target[i] - base
        n = int(round(want / step))
        n = 7 if n > 7 else -8 if n < -8 else n
        t = n << scale
        r = ((t << 11) + total + 0x80000000 & 0xFFFFFFFF) - 0x80000000
        r >>= 11
        r = 32767 if r > 32767 else -32768 if r < -32768 else r
        tmp.append(t)
        nibbles.append(n & 15)
        out.append(r)
        d = r - target[i]
        err += d * d
    return nibbles, out, err


def make_book(signals=()):
    """A codebook (order 2, 4 predictors, 64 s16) for a bank: the linear prediction of its
    recordings (or a gentle default), holding, straight lines and nothing. One book serves
    every sound in a bank: the game keeps the whole bank file in a small audio heap."""
    x = [v for sig in signals for v in sig]
    first = _lpc2(x) if len(x) > 64 else (1.2, -0.4)
    book = []
    for c in (first, (1.0, 0.0), (2.0, -1.0), (0.0, 0.0)):
        book.extend(_expand_predictor(*c))
    return book


def encode_adpcm(pcm, loop=None, book=None):
    """(data, loop state) of 16-bit samples as VADPCM with a book (make_book's; by default
    one made for these samples).

    Each 16-sample frame is a header byte (scale << 4 | predictor) and 8 bytes of 4-bit
    corrections. For each frame every predictor is tried at the scales around the one its
    largest correction needs, and the choice the decoder reproduces best is kept.

    loop (start, end): at the loop end the game resumes the data at the frame after the
    one holding the loop start, taking that frame's 16 decoded samples from the loop's state
    (Mario Party 3 USA 0x80073d48). The state is what the decoder makes of that frame on the
    way through, so every pass through the loop decodes exactly like the first.
    """
    n = (len(pcm) + 15) // 16 * 16
    x = list(pcm) + [0] * (n - len(pcm))
    if book is None:
        book = make_book([x])
    preds = [(book[k * 16:k * 16 + 8], book[k * 16 + 8:k * 16 + 16]) for k in range(len(book) // 16)]
    anchor = loop[0] // 16 if loop else -1
    data = bytearray()
    h2 = h1 = 0
    state = None
    for f in range(n // 16):
        target = x[f * 16:f * 16 + 16]
        best = None
        for k, (p1, p2) in enumerate(preds):
            # The scale the plain prediction's error needs, and its neighbours.
            guess = [target[i] - ((p1[i] * h2 + p2[i] * h1) >> 11) for i in range(8)]
            peak = max(abs(v) for v in guess + [target[i] - target[i - 1] for i in range(9, 16)])
            s0 = 0
            while s0 < 12 and (7 << s0) < peak:
                s0 += 1
            for scale in range(max(0, s0 - 2), min(12, s0 + 1) + 1):
                n1, o1, e1 = _encode_half(target[:8], scale, p1, p2, h2, h1)
                n2, o2, e2 = _encode_half(target[8:], scale, p1, p2, o1[6], o1[7])
                e = e1 + e2
                if best is None or e < best[0]:
                    best = (e, k, scale, n1 + n2, o1 + o2)
        _, k, scale, nibbles, out = best
        data.append(scale << 4 | k)
        for i in range(0, 16, 2):
            data.append(nibbles[i] << 4 | nibbles[i + 1])
        if f == anchor:
            state = list(out)
        h2, h1 = out[14], out[15]
    return bytes(data), state


_encode_cache = {}


def _encode_cached(pcm, loop, book):
    key = hashlib.sha1(struct.pack(">%dh" % len(pcm), *pcm) + repr((loop, book)).encode()).hexdigest()
    hit = _encode_cache.get(key)
    if hit is None:
        if len(_encode_cache) > 512:
            _encode_cache.clear()
        hit = _encode_cache[key] = encode_adpcm(pcm, loop, book)
    return hit


# --- Building a bank -------------------------------------------------------------

def _ms_to_us(v, default):
    return int(round((v if v is not None else default) * 1000))


def _align(n, a):
    return (n + a - 1) // a * a


def build_bank(bank, file_offset, tbl_offset):
    """(bank bytes, sound data bytes) for a soundbank placed at file_offset in the bank file,
    its samples at tbl_offset in the sound data. Offsets in the bank are from the file's
    start; wave bases are from the sound data's start (as the game's loader expects).

    The bank's structures are kept small, since the game holds the whole bank file in its
    audio heap (see BANK_BUDGET): one codebook for the bank, one envelope per instrument,
    and key maps shared between sounds that cover the same keys the same way."""
    insts = bank["instruments"]
    built = [instrument_sounds(inst) for inst in insts]
    recordings = [pcm for inst, sounds in zip(insts, built) if inst["source"]["type"] == "sample"
                  for _, _, pcm, _, _, _ in sounds[:1]]
    book = make_book(recordings)

    out = bytearray()
    tbl = bytearray()

    def here():
        return file_offset + len(out)

    def pad(a):
        out.extend(b"\0" * (_align(len(out), a) - len(out)))

    # ALBank, then the shared codebook.
    out.extend(struct.pack(">hBBiI", len(insts), 0, 0, SAMPLE_RATE, 0))
    inst_ptr_pos = len(out)
    out.extend(b"\0" * (4 * len(insts)))
    pad(8)
    book_off = here()
    out.extend(struct.pack(">ii%dh" % len(book), 2, len(book) // 16, *book))

    keymaps = {}
    for i, (inst, sounds) in enumerate(zip(insts, built)):
        pad(8)
        env_off = here()
        out.extend(struct.pack(">iiiBBH",
                               _ms_to_us(inst.get("attack"), 0), max(1, _ms_to_us(inst.get("decay"), 1)),
                               _ms_to_us(inst.get("release"), 20), 127, int(inst.get("sustain", 127)), 0))
        sound_offs = []
        for lo, hi, pcm, base, detune, loop in sounds:
            data, state = _encode_cached(pcm, loop, tuple(book))
            tbl.extend(b"\0" * (_align(len(tbl), 16) - len(tbl)))
            wave_base = tbl_offset + len(tbl)
            tbl.extend(data)
            km = (lo, hi, base, max(-128, min(127, detune)))
            if km not in keymaps:
                pad(8)
                keymaps[km] = here()
                out.extend(struct.pack(">BBBBBbH", 0, 127, lo, hi, base, km[3], 0))
            loop_off = 0
            if loop:
                pad(8)
                loop_off = here()
                out.extend(struct.pack(">III16h", loop[0], loop[1], _LOOP_FOREVER, *state))
            pad(8)
            wave_off = here()
            out.extend(struct.pack(">IIBBHII", wave_base, len(data), 0, 0, 0, loop_off, book_off))
            pad(8)
            sound_offs.append(here())
            out.extend(struct.pack(">IIIBBBB", env_off, keymaps[km], wave_off, 64, 127, 0, 0))
        pad(8)
        struct.pack_into(">I", out, inst_ptr_pos + 4 * i, here())
        out.extend(struct.pack(">BBBBBBBBBBBBhh", int(inst.get("volume", 110)), int(inst.get("pan", 64)),
                               5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 200, len(sound_offs)))
        for so in sound_offs:
            out.extend(struct.pack(">I", so))
    pad(16)
    tbl.extend(b"\0" * (_align(len(tbl), 16) - len(tbl)))
    return bytes(out), bytes(tbl)


def preview_bank(bank):
    """(ALBank, sound data) of a soundbank on its own, for previews."""
    from ..utils.dataview import DataView
    from .b1 import B1
    data, tbl = build_bank(bank, 16, 0)
    b1 = B1(DataView(bytearray(struct.pack(">hhI8x", _B1_MAGIC, 1, 16) + data)))
    return b1.banks[0], tbl


# --- Adding banks to a bank file --------------------------------------------------

def _u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def _s16(b, o):
    return struct.unpack_from(">h", b, o)[0]


def pointer_fields(b1):
    """The positions of every offset in a bank file, found as the game's loader finds them."""
    if _s16(b1, 0) != _B1_MAGIC:
        raise SoundbankError("not a B1 bank file")
    fields = set()
    seen = set()

    def inst(o):
        if ("i", o) in seen:
            return
        seen.add(("i", o))
        for k in range(_s16(b1, o + 14)):
            fields.add(o + 16 + 4 * k)
            sound(_u32(b1, o + 16 + 4 * k))

    def sound(o):
        if ("s", o) in seen:
            return
        seen.add(("s", o))
        fields.update((o, o + 4, o + 8))
        wave(_u32(b1, o + 8))

    def wave(o):
        if ("w", o) in seen:
            return
        seen.add(("w", o))
        typ = b1[o + 8]
        if typ == 0:
            if _u32(b1, o + 12):
                fields.add(o + 12)
            if _u32(b1, o + 16):
                fields.add(o + 16)
        elif typ == 1 and _u32(b1, o + 12):
            fields.add(o + 12)

    for i in range(_s16(b1, 2)):
        fields.add(4 + 4 * i)
        bank = _u32(b1, 4 + 4 * i)
        if ("b", bank) in seen:
            continue
        seen.add(("b", bank))
        if _u32(b1, bank + 8):
            fields.add(bank + 8)
            inst(_u32(b1, bank + 8))
        for k in range(_s16(b1, bank)):
            fields.add(bank + 12 + 4 * k)
            inst(_u32(b1, bank + 12 + 4 * k))
    return sorted(fields)


def append_banks(b1, tbl, banks):
    """(new bank file, new sound data, index of the first new bank): `banks` (soundbank
    dicts) added after the bank file's own. The file's structures move down to make room
    for the new offsets, and every offset in it is moved with them."""
    b1 = bytes(b1)
    if not banks:
        return b1, bytes(tbl), _s16(b1, 2)
    count = _s16(b1, 2)
    fields = pointer_fields(b1)
    header_end = 4 + 4 * count
    targets = [_u32(b1, f) for f in fields]
    first = min([t for t in targets if t >= header_end] + [len(b1)])
    need = 4 + 4 * (count + len(banks))
    delta = _align(need - first, 16) if need > first else 0

    out = bytearray(b1[:first]) + bytearray(delta) + bytearray(b1[first:])
    for f in fields:
        nf = f if f < first else f + delta
        struct.pack_into(">I", out, nf, _u32(b1, f) + delta)
    struct.pack_into(">h", out, 2, count + len(banks))

    new_tbl = bytearray(tbl)
    for j, bank in enumerate(banks):
        out.extend(b"\0" * (_align(len(out), 16) - len(out)))
        new_tbl.extend(b"\0" * (_align(len(new_tbl), 16) - len(new_tbl)))
        bank_bytes, bank_tbl = build_bank(bank, len(out), len(new_tbl))
        struct.pack_into(">I", out, 4 + 4 * (count + j), len(out))
        out.extend(bank_bytes)
        new_tbl.extend(bank_tbl)
    out.extend(b"\0" * (_align(len(out), 16) - len(out)))
    new_tbl.extend(b"\0" * (_align(len(new_tbl), 16) - len(new_tbl)))
    return bytes(out), bytes(new_tbl), count


def bank_key(bank):
    """A key that is the same for soundbanks that sound the same (names aside)."""
    clean = {"instruments": [{k: v for k, v in inst.items() if k != "name"} for inst in bank["instruments"]]}
    return hashlib.sha1(json.dumps(clean, sort_keys=True).encode()).hexdigest()


def _game_name(game):
    """"MP3_USA" for a Game, its ID ("NMVE") or its name."""
    from ..types import Game
    try:
        return Game(game).name
    except ValueError:
        return game


def bank_bytes(bank):
    """How many bytes of the game's audio heap a soundbank takes."""
    return len(build_bank(bank, 0, 0)[0]) + 4


def budget_problem(game, banks):
    """Why these soundbanks can't be added to a game's ROM together, or None."""
    budget = BANK_BUDGET.get(_game_name(game))
    if budget is None:
        return "Custom soundbanks work with Mario Party 3 (USA) so far."
    need = sum(bank_bytes(b) for b in banks)
    if need > budget:
        return ("The soundbanks need %d bytes of the game's audio memory, but only about %d are "
                "free. Use fewer instruments, or recordings with fewer key ranges." % (need, budget))
    return None


def add_soundbank(seq_table, bank, game="MP3_USA"):
    """Add a soundbank to a sequence table (MBF0 or S2) and return its index. A soundbank
    already added (the same instruments) is not added again. Raises SoundbankError when the
    game's audio heap can't hold it (with the banks added before it)."""
    from ..utils.dataview import DataView
    from .b1 import B1

    added = seq_table.__dict__.setdefault("_custom_banks", {})
    key = bank_key(bank)
    if key in added:
        return added[key]
    raw_attr = "_soundback_buffer" if hasattr(seq_table, "_soundback_buffer") else "_raw_b1"
    original = seq_table.__dict__.setdefault("_original_b1_length", len(getattr(seq_table, raw_attr)))
    b1, tbl, first = append_banks(getattr(seq_table, raw_attr), seq_table.tbl, [bank])
    if first > 255:
        raise SoundbankError("Too many soundbanks (the game counts them in a byte).")
    budget = BANK_BUDGET.get(_game_name(game))
    if budget is None:
        raise SoundbankError("Custom soundbanks work with Mario Party 3 (USA) so far.")
    if len(b1) - original > budget:
        raise SoundbankError(
            "The soundbanks need %d bytes of the game's audio memory, but only about %d are free. "
            "Use fewer instruments." % (len(b1) - original, budget))
    setattr(seq_table, raw_attr, bytearray(b1))
    seq_table.tbl = bytearray(tbl)
    seq_table.soundbanks = B1(DataView(bytearray(b1)))
    added[key] = first
    return first

