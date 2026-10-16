"""VADPCM decoding (port of audio/vadpcm.ts).

Ported from work by Ice Mario and Subdrag
https://github.com/derselbst/N64SoundTools/blob/master/N64SoundListTool/N64SoundLibrary/N64AIFCAudio.cpp#L20619

The arithmetic reproduces the TypeScript exactly, including its typed-array
truncations (the temporary samples live in an Int16Array) and the 32-bit
wrap of the ">> 0xb".
"""

import struct

itable = (0, 1, 2, 3, 4, 5, 6, 7, -8, -7, -6, -5, -4, -3, -2, -1)

# itable_half = (0, 1, -2, -1)

_PACK8 = struct.Struct("<8h")


def _i16(x):
    return ((x + 0x8000) & 0xFFFF) - 0x8000


def _sign_extend(b, x):
    """Sign extends a number.

    Args:
        b: number of bits representing the number in x
        x: sign extend this b-bit number to r
    """
    m = 1 << (b - 1)  # mask can be pre-computed if b is fixed
    x = x & ((1 << b) - 1)  # (Skip this if bits in x above position b are already zero.)
    return (x ^ m) - m


def _make_preds(book):
    # flip the predictors (TODO: What does flip mean?)
    count = 16 * book.npredictors
    preds = [0] * count
    for p in range(min(8 * book.order * book.npredictors, count)):
        preds[p] = book.predictors[p]
    return preds


def _decode_block(tmp, p1, p2, last6, last7):
    """Return the 8 output samples of one block (decode8's maths)."""
    out = [0] * 8
    for i in range(8):
        total = p1[i] * last6 + p2[i] * last7
        for x in range(i):
            total += tmp[i - 1 - x] * p2[x]
        result = (tmp[i] << 0xB) + total
        # JS ">>" converts to a 32-bit integer first.
        result = ((result + 0x80000000) & 0xFFFFFFFF) - 0x80000000
        result >>= 0xB
        if result > 32767:
            result = 32767
        elif result < -32768:
            result = -32768
        out[i] = result
    return out


def decode_vadpcm_samples(tbl_view, length, book, decode8_only):
    """Decode VADPCM data into a list of signed 16-bit samples."""
    preds = _make_preds(book)
    npredictors = book.npredictors
    data = tbl_view.buffer
    base = tbl_view.byte_offset
    frame_size = 5 if decode8_only else 9
    frames = length // frame_size
    if frames * frame_size > tbl_view.byte_length:
        raise IndexError("Offset is outside the bounds of the DataView")

    samples = []
    extend = samples.extend
    last6 = last7 = 0
    pred_cache = {}
    in_index = base
    for _ in range(frames):
        header = data[in_index]
        index = (header >> 4) & 0xF
        pred = header & 0xF

        # to not make zelda crash but doesn't fix it
        pred = pred % npredictors

        coefs = pred_cache.get(pred)
        if coefs is None:
            pred1_index = pred * 16
            coefs = pred_cache[pred] = (preds[pred1_index:pred1_index + 8],
                                        preds[pred1_index + 8:pred1_index + 16])
        p1, p2 = coefs
        in_index += 1

        for _half in range(2):
            if not decode8_only:
                tmp = []
                for k in range(4):
                    byte = data[in_index + k]
                    tmp.append(_i16(itable[(byte >> 4) & 0xF] << index))
                    tmp.append(_i16(itable[byte & 0xF] << index))
                in_index += 4
            else:
                tmp = []
                for k in range(2):
                    byte = data[in_index + k]
                    for shift in (6, 4, 2, 0):
                        val = _i16(((byte >> shift) & 0x3) << index)
                        tmp.append(_i16(_sign_extend(index + 2, val)))
                in_index += 2
            out = _decode_block(tmp, p1, p2, last6, last7)
            # update the last sample set for subsequent iterations
            last6 = out[6]
            last7 = out[7]
            extend(out)
    return samples


def decode_vadpcm(tbl_view, out_raw_data, length, book, decode8_only):
    """Decode VADPCM into out_raw_data (a bytearray) as little-endian 16-bit samples.

    Returns:
        The number of samples decoded.
    """
    samples = decode_vadpcm_samples(tbl_view, length, book, decode8_only)
    count = len(samples)
    if count * 2 > len(out_raw_data):
        raise IndexError("Offset is outside the bounds of the DataView")
    struct.pack_into("<%dh" % count, out_raw_data, 0, *samples)
    return count
