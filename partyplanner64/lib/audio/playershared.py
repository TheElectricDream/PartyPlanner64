"""Shared pieces of the audio players (stands in for audio/playershared.ts).

The browser played audio through WebAudio (an AudioContext, buffer source
nodes and gain nodes). The Python port renders to a WAV file instead, which
the page plays; this module holds the sample maths the renderers share.

Mixing without numpy: a voice's samples are packed into one Python integer,
64 bits per sample (biased to be non-negative, so the fields don't borrow),
and voices are summed into per-block integers with big-integer shifts,
multiplications and additions, which run at C speed over whole blocks.
"""

import struct
import sys
from array import array
from itertools import repeat
from operator import add

_FIELD_BITS = 64
_FIELD_BYTES = 8
_SAMPLE_BIAS = 1 << 15  # Makes an int16 sample non-negative.
_SUM_BIAS = 1 << 62  # Makes a summed field non-negative when decoding.
_GAIN_BITS = 16  # Gains are fixed point with this many fraction bits.
BLOCK_SAMPLES = 1 << 15

_LITTLE = sys.byteorder == "little"


def pcm16_wav(pcm, sample_rate, channels=1):
    """Return a 16-bit PCM .wav file of samples (an array('h') or a sequence of ints)."""
    if not isinstance(pcm, array) or pcm.typecode != "h":
        pcm = array("h", pcm)
    if not _LITTLE:
        pcm = array("h", pcm)
        pcm.byteswap()
    data = pcm.tobytes()
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(data), b"WAVE",
        b"fmt ", 16, 1, channels, sample_rate, sample_rate * channels * 2, channels * 2, 16,
        b"data", len(data))
    return header + data


def resample_linear(src, step, count):
    """Return count samples of src read every `step` source samples, with linear interpolation.

    This is what a WebAudio buffer source does when its playbackRate (or
    detune) makes it read the buffer faster or slower than real time.

    Args:
        src: The source samples (a sequence of numbers).
        step: Source samples advanced per output sample.
        count: How many output samples to make (reads past the end repeat the last sample).

    Returns:
        A list of floats.
    """
    if count <= 0 or not len(src):
        return []
    s = list(src)
    last = len(s) - 1
    if step == 1.0:
        out = s[:count]
        out.extend(repeat(s[-1], count - len(out)))
        return out
    s.append(s[-1])
    out = []
    append = out.append
    limit = min(count, int(last / step) + 1)
    for k in range(limit):
        p = k * step
        i = int(p)
        a = s[i]
        append(a + (s[i + 1] - a) * (p - i))
    out.extend(repeat(s[-1], count - limit))
    return out


def resampled_length(src_len, step):
    """How many output samples a source of src_len samples lasts when read every `step` samples."""
    if src_len <= 0 or step <= 0:
        return 0
    return int((src_len - 1) / step) + 1


def _pack(values):
    """Pack non-negative ints < 2**64 into an integer, 64 bits each, first value lowest."""
    arr = array("Q", values)
    if not _LITTLE:
        arr.byteswap()
    return int.from_bytes(arr.tobytes(), "little")


class PackedVoice:
    """A voice's samples (int16 units) packed for Mixer."""

    __slots__ = ("length", "_packed", "_bias")

    def __init__(self, samples):
        """samples: floats or ints in int16 units."""
        ints = list(map(int, samples))
        self.length = len(ints)
        self._packed = _pack(map(add, ints, repeat(_SAMPLE_BIAS)))
        self._bias = int.from_bytes(_SAMPLE_BIAS.to_bytes(_FIELD_BYTES, "little") * self.length,
                                    "little")

    def piece(self, start, count):
        """Return samples [start, start + count) as a signed packed integer."""
        mask = (1 << (_FIELD_BITS * count)) - 1
        return ((self._packed >> (_FIELD_BITS * start)) & mask) - (self._bias & mask)


class Mixer:
    """Sums voices into a mono track of 16-bit samples."""

    def __init__(self):
        self._blocks = {}
        self.length = 0

    def add(self, start, voice, gain, length=None):
        """Add voice (a PackedVoice) times gain, starting at sample `start`, for `length` samples."""
        if length is None or length > voice.length:
            length = voice.length
        g = int(round(gain * (1 << _GAIN_BITS)))
        if length <= 0 or g == 0 or start < 0:
            return
        self.length = max(self.length, start + length)
        pos = 0
        while pos < length:
            at = start + pos
            block, local = divmod(at, BLOCK_SAMPLES)
            count = min(length - pos, BLOCK_SAMPLES - local)
            value = (voice.piece(pos, count) * g) << (_FIELD_BITS * local)
            self._blocks[block] = self._blocks.get(block, 0) + value
            pos += count

    def render(self):
        """Return the mix as an array('h'), clamped to 16 bits."""
        out = bytearray()
        if self.length <= 0:
            return array("h")
        n = BLOCK_SAMPLES
        # Each field becomes 2**62 + 2**31 + v: while v (the sum, with _GAIN_BITS fraction
        # bits) is in [-2**31, 2**31), its bytes 2-3 are (v >> 16) + 0x8000 and bytes 4-7
        # are 00 00 00 40; other fields clip.
        bias_field = (_SUM_BIAS + (1 << 31)).to_bytes(_FIELD_BYTES, "little")
        bias = int.from_bytes(bias_field * n, "little")
        in_range = (bytes(n), bytes(n), bytes(n), b"\x40" * n)
        block_count = (self.length + n - 1) // n
        for block in range(block_count):
            raw = (self._blocks.get(block, 0) + bias).to_bytes(_FIELD_BYTES * n, "little")
            pcm = bytearray(2 * n)
            pcm[0::2] = raw[2::8]
            pcm[1::2] = raw[3::8].translate(_FLIP_SIGN)
            if (raw[4::8], raw[5::8], raw[6::8], raw[7::8]) != in_range:
                for i in range(n):
                    field = raw[8 * i:8 * i + 8]
                    if field[4:] != b"\x00\x00\x00\x40":
                        v = int.from_bytes(field, "little") - _SUM_BIAS - (1 << 31)
                        pcm[2 * i:2 * i + 2] = (32767 if v > 0 else -32768).to_bytes(2, "little", signed=True)
            out += pcm
        result = array("h")
        result.frombytes(bytes(out[:2 * self.length]))
        if not _LITTLE:
            result.byteswap()
        return result


_FLIP_SIGN = bytes((b ^ 0x80) for b in range(256))
