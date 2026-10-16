"""The game's compression formats (port of utils/compression.ts).

decompress(type, src, size) and compress(type, src) handle every
compression type found in the Mario Party games:

- 0: uncompressed.
- 1: LZSS with a 1 KB circular window (all three games).
- 2, 3, 4: a yaz0-like LZ (Mario Party 2 and 3).
- 5: run-length encoding.

The hot loops are written with bytearray slicing rather than per-byte
DataView calls: the circular window of type 1 and the out-of-bounds
lookback of type 2 are both modelled as a run of zero bytes in front of
the output, which gives the same bytes as the original algorithms.

Sources may be a DataView, bytes, bytearray or memoryview. A DataView
starts at its byte offset (and may run to the end of its buffer, as the
TypeScript's `new DataView(buffer, offset)` did).
"""

from .dataview import DataView
from .debug import log

WINDOW_START = 0x3BE
WINDOW_SIZE = 1024

MIN_MATCH_LEN = 3
# MAX_MATCH_LEN = 0x42


class DecompressedBuffer(bytearray):
    """A bytearray holding decompressed data.

    The TypeScript attached the compressed size as a property of the
    returned ArrayBuffer (`buffer.compressedSize`); here it is the
    `compressed_size` attribute (None when the type is not implemented).
    """

    compressed_size = None


def _source(src):
    """Return (buffer, start, end) for a compression source."""
    if isinstance(src, DataView):
        return src.buffer, src.byte_offset, src.byte_offset + src.byte_length
    if isinstance(src, memoryview):
        src = src.cast("B") if src.format != "B" else src
        return src, 0, len(src)
    return src, 0, len(src)


def _check_src(pos, end):
    if pos > end:
        raise IndexError("Offset is outside the bounds of the DataView")


def _decompress01(buf, start, end, decompressed_size):
    """Mario Party N64 compression type 01

    This type of compression was used in all three titles, though was the
    exclusive type available in the original title. It is similar to LZSS, and
    uses a 1KB circular buffer when referencing offsets. Like yaz0 compression,
    there are code bytes for every 8 "chunks," though they are read from right
    to left (0x01 to 0x80).

    When a '0' code bit is encountered, the next two bytes in the input are
    read as offset and length pairs into the sliding window.

          Byte 1    Byte 2
        [oooooooo][oollllll]

    The two offset bits within Byte 2 are masked and shifted such that they
    become the most significant bits. The length is found by adding the value
    of MIN_MATCH_LEN, in this case, 3.

    Notably, the circular buffer begins filling not at zero, but at a position
    roughly 90% of the way through, WINDOW_START.

    Returns (output bytearray, compressed size).
    """
    # The sliding window always holds the last 1024 output bytes, and starts
    # out zeroed. Prefixing the output with 1024 zeros models it exactly: the
    # window slot for output position p is (WINDOW_START + p) % WINDOW_SIZE.
    out = bytearray(WINDOW_SIZE)
    target = WINDOW_SIZE + decompressed_size
    src_place = start
    window_base = WINDOW_SIZE - WINDOW_START  # out index i <-> window slot (i - base) % 1024
    while len(out) < target:
        code = buf[src_place]
        src_place += 1
        if code == 0xFF:
            # Eight straight copies.
            take = target - len(out)
            if take > 8:
                take = 8
            _check_src(src_place + take, end)
            out += buf[src_place:src_place + take]
            src_place += take
            continue
        for _ in range(8):
            if len(out) >= target:
                break
            if code & 1:
                # Copy the next byte from the source to the destination.
                out.append(buf[src_place])
                src_place += 1
            else:
                # Interpret the next two bytes as an offset into the sliding
                # window and a length to read.
                byte1 = buf[src_place]
                byte2 = buf[src_place + 1]
                src_place += 2
                offset = ((byte2 & 0xC0) << 2) | byte1
                count = (byte2 & 0x3F) + MIN_MATCH_LEN
                cur = len(out)
                win_place = (cur - window_base) % WINDOW_SIZE
                back = (win_place - offset) % WINDOW_SIZE or WINDOW_SIZE
                pos = cur - back
                if back >= count:
                    out += out[pos:pos + count]
                else:
                    pattern = out[pos:cur]
                    out += (pattern * (count // back + 1))[:count]
            # Consider the code bit consumed.
            code >>= 1
    _check_src(src_place, end)
    return out, src_place - start


def _compress01(buf, start, end):
    """This is a hack for MP3 Strings3 at the moment. Just "wraps" with dummy
    code words, so file size will just grow."""
    data = bytes(buf[start:end])
    return bytearray(b"".join(b"\xff" + data[i:i + 8] for i in range(0, len(data), 8)))


def _decompress02(buf, start, end, decompressed_size):
    """Mario Party N64 compression type 02

    This compression algorithm was introduced in Mario Party 2, and is very
    similar to yaz0. It uses word sized groups of code bits rather than a
    single byte, and reads them in the same left to right order as yaz0. The
    interpretation of the bytes when a code bit is 0 is also the same as yaz0.

          Byte 1    Byte 2     [Byte 3 when l = 0]
        [lllldddd][dddddddd]   [llllllll]

    The values of length and lookback distance are simply split apart and used.
    The special case when length == 0 in yaz0 also applies, where a third byte
    is read as the value of length and 0x12 is added. When the lookback
    distance is farther than the start (out of bounds), 0s are inserted.

    This is also the implementation used for decompression types 03 and 04.
    03 and 04 are considered the same by the game engine.
    02 differs from 03/04 in that it is the only implementation that checks
    whether lookback goes out of bounds, and handles it. As far as I know,
    it is OK to use that handling for 03/04 as well, since the behavior would
    otherwise be undefined.

    Returns (output bytearray, compressed size).
    """
    # Lookback before the start reads zeros: model it with 4096 zeros in front
    # (the farthest lookback is 0x1000).
    PREFIX = 0x1000
    out = bytearray(PREFIX)
    target = PREFIX + decompressed_size
    src_place = start
    while len(out) < target:
        # Read a new code word.
        code = int.from_bytes(buf[src_place:src_place + 4], "big")
        _check_src(src_place + 4, end)
        src_place += 4
        if code == 0xFFFFFFFF:
            take = target - len(out)
            if take > 32:
                take = 32
            _check_src(src_place + take, end)
            out += buf[src_place:src_place + take]
            src_place += take
            continue
        bit = 0x80000000
        while bit:
            if len(out) >= target:
                break
            if code & bit:
                # Copy the next byte from the source to the destination.
                out.append(buf[src_place])
                src_place += 1
            else:
                # Interpret the next two bytes as a distance to travel
                # backwards and a length to read.
                byte1 = buf[src_place]
                byte2 = buf[src_place + 1]
                src_place += 2
                back = (((byte1 & 0x0F) << 8) | byte2) + 1
                count = ((byte1 & 0xF0) >> 4) + 2
                if count == 2:
                    # Special case where 0xF0 masked byte 1 is zero.
                    count = buf[src_place] + 0x12
                    src_place += 1
                # Step back and copy count bytes into the dst.
                cur = len(out)
                remaining = target - cur
                if count > remaining:
                    count = remaining
                pos = cur - back
                if back >= count:
                    out += out[pos:pos + count]
                else:
                    pattern = out[pos:cur]
                    out += (pattern * (count // back + 1))[:count]
            # Consider the code bit consumed.
            bit >>= 1
    _check_src(src_place, end)
    return out, src_place - start


def _compress02(buf, start, end):
    """This is a hack for MP2 HVQ at the moment. Just "wraps" with dummy code
    words, so file size just grows."""
    length = end - start
    if length % 32:
        # The TypeScript reads and writes past the end of its buffers here
        # (a RangeError).
        raise IndexError("Offset is outside the bounds of the DataView")
    data = bytes(buf[start:end])
    return bytearray(b"".join(b"\xff\xff\xff\xff" + data[i:i + 32] for i in range(0, length, 32)))


def _decompress05(buf, start, end, decompressed_size):
    """Mario Party N64 compression type 05

    This is mostly a run-length encoding. The algorithm can be pretty simply
    described:
    1. Read a byte
    2. If the byte has the sign bit (byte & 0x80), then get rid of the sign
       bit and use that to count and copy in that many bytes.
    3. If there is no sign bit, use the byte to count and repeat the next byte
       for that many times.
    4. Repeat until decompressed size reached.

    Typically this is used when there are a lot of zeroes or repeated single
    values, like in some images.

    Returns (output bytearray, compressed size).
    """
    out = bytearray()
    src_place = start
    while len(out) < decompressed_size:
        code = buf[src_place]
        src_place += 1
        count = code & 0x7F
        if code & 0x80:
            # Having the sign bit means we read the next n bytes from the input.
            _check_src(src_place + count, end)
            out += buf[src_place:src_place + count]
            src_place += count
        else:
            # No sign bit means we repeat the next byte n times.
            repeated = buf[src_place]
            src_place += 1
            out += bytes((repeated,)) * count
    _check_src(src_place, end)
    return out[:decompressed_size], src_place - start


def _compress05(buf, start, end):
    """Run length encoding compression.
    Implementation provided by @gamemasterplc

    The TypeScript read one byte past the end of the input through a
    DataView, which throws; this port reads such bytes as "no byte" (as a
    Uint8Array index would), which is what the algorithm intends.
    """
    data = bytes(buf[start:end])
    n = len(data)

    def at(i):
        return data[i] if i < n else None

    output = bytearray()
    input_pos = 0
    while input_pos < n:
        curr_byte = at(input_pos)
        next_byte = at(input_pos + 1)
        if curr_byte == next_byte:
            copy_len = 0
            for i in range(127):
                curr_byte = at(input_pos + i)
                next_byte = at(input_pos + i + 1)
                if curr_byte != next_byte or input_pos + i >= n:
                    copy_len += 1
                    break
                copy_len += 1
            output.append(copy_len)
            output.append(data[input_pos])
            input_pos += copy_len
        else:
            copy_len = 0
            for i in range(127):
                curr_byte = at(input_pos + i)
                next_byte = at(input_pos + i + 1)
                if curr_byte == next_byte or input_pos + i >= n:
                    break
                copy_len += 1
            output.append(0x80 | copy_len)
            output += data[input_pos:input_pos + copy_len]
            input_pos += copy_len
    return output


def decompress(type, src_data_view, decompressed_size):
    """Return a new DecompressedBuffer with the decompressed data.

    The compressed size is attached as `compressed_size`.
    """
    buf, start, end = _source(src_data_view)
    compressed_size = None
    if type == 1:
        out, compressed_size = _decompress01(buf, start, end, decompressed_size)
        data = memoryview(out)[WINDOW_SIZE:WINDOW_SIZE + decompressed_size]
    elif type in (2, 3, 4):
        out, compressed_size = _decompress02(buf, start, end, decompressed_size)
        data = memoryview(out)[0x1000:]
    elif type == 5:
        data, compressed_size = _decompress05(buf, start, end, decompressed_size)
    elif type == 0:
        # Just directly copy uncompressed data.
        compressed_size = decompressed_size
        _check_src(start + decompressed_size, end)
        data = buf[start:start + decompressed_size]
    else:
        log("decompression %s not implemented." % type)
        data = bytes(decompressed_size)

    result = DecompressedBuffer(data)
    result.compressed_size = compressed_size
    return result


def compress(type, src_data_view):
    """Return a new bytearray with the data compressed with a type."""
    buf, start, end = _source(src_data_view)
    if type == 1:
        return _compress01(buf, start, end)
    # TODO: Are all these really the same, particularly 4?
    if type in (2, 3, 4):
        return _compress02(buf, start, end)
    if type == 5:
        return _compress05(buf, start, end)
    # Just directly copy uncompressed data.
    if isinstance(src_data_view, DataView):
        # srcDataView.buffer.slice(0): the whole underlying buffer.
        return bytearray(src_data_view.buffer)
    return bytearray(buf[start:end])


def get_compressed_size(type, src_data_view, decompressed_size):
    """Return how many source bytes decompressing would consume."""
    buf, start, end = _source(src_data_view)
    if type == 1:
        return _decompress01(buf, start, end, decompressed_size)[1]
    if type in (2, 3, 4):
        return _decompress02(buf, start, end, decompressed_size)[1]
    if type == 5:
        return _decompress05(buf, start, end, decompressed_size)[1]
    if type == 0:
        return decompressed_size
    log("getCompressedSize %s not implemented." % type)
    return None
