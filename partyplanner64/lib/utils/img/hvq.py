"""HVQ background tiles (port of utils/img/HVQ.ts, plus real HVQ decoding).

The games store their board backgrounds in Hudson's HVQ format, which the
TypeScript PartyPlanner64 never decoded (its tiles read as black). The
decoders here were worked out from the games' own decoders:

- Mario Party 1: "HVQ 2.0" tiles (the decoder at RAM 0x8007c000-0x8007fb60
  of Mario Party (U)). See HVQ2Decoder.
- Mario Party 2 and 3: an "HVQ-MPS 1.1" file per background, shared by its
  "HVQS" tiles (the decoder at RAM 0x800665e0-0x8006a440 of Mario Party 3
  (U); Mario Party 2's is the same code). See HVQMPS and HVQSDecoder.

Hudson's HVQ patent (US 6,714,687) describes the ideas: an image in YCbCr,
in 4x4 blocks, each with its mean (the DC) and either predicted from the
neighbouring DCs ("flat"), or the DC plus a few scaled basis vectors
sampled from a "nest" (a window of the DC image), or stored raw.

Tiles the editor writes itself use the run-length/LZ "type 3" encoding
(Mario Party 2 and 3) or raw RGBA5551 (Mario Party 1); those decode as
before.
"""

import logging
import struct

from ..arrays import _region, copy_range
from ..compression import compress, decompress
from ..dataview import DataView

logger = logging.getLogger("partyplanner64")

_black_rgb16 = None


def decode(hvq_view, mps=None):
    """Return the RGBA5551 bytes of a background tile.

    `mps` is the background's HVQMPS (or its file), needed for HVQS tiles.
    """
    if not isinstance(hvq_view, DataView):
        hvq_view = DataView(hvq_view if not isinstance(hvq_view, memoryview) else bytearray(hvq_view))
    first_word = hvq_view.get_uint32(0)
    if first_word == 0x00000003:
        # MP2+ can have run-length instead
        # (As in the TypeScript, the data is read from offset 8 of the
        # underlying buffer, not of the view.)
        file_start_view = DataView(hvq_view.buffer, 8)
        decompressed_size = hvq_view.get_uint32(4)
        return decompress(3, file_start_view, decompressed_size)
    if (first_word & 0xFFFFFF00) != 0x48565100:  # "HVQ"
        return hvq_view.bytes()

    data = bytes(hvq_view.bytes())
    try:
        if data[:7] == b"HVQ 2.0":
            return bytearray(HVQ2Decoder(data).decode())
        if data[:4] == b"HVQS":
            if mps is None:
                raise ValueError("an HVQS tile needs its background's HVQ-MPS file")
            if not isinstance(mps, HVQMPS):
                mps = HVQMPS(mps)
            return bytearray(HVQSDecoder(data, mps).decode())
        raise ValueError("unknown HVQ variant %r" % data[:8])
    except Exception as exc:  # noqa: BLE001 - a bad tile must not take the board down
        logger.warning("HVQ tile could not be decoded (%s); it will be black", exc)

    global _black_rgb16
    if _black_rgb16 is None:
        _black_rgb16 = bytes(b"\x00\x01" * (0x1800 // 2))
    return bytearray(_black_rgb16)


def encode(buffer, width, height):
    """Return the tile bytes to store for RGBA5551 pixels."""
    from ...romhandler import romhandler
    game_version = romhandler.get_game_version()
    if game_version is None:
        raise RuntimeError("HVQ encode not implemented")

    if game_version > 1:
        # Hack for MP2
        compressed = compress(3, buffer)
        result = bytearray(len(compressed) + 8)
        result_view = DataView(result)
        result_view.set_uint32(0, 3)
        result_view.set_uint32(4, _region(buffer)[2])
        copy_range(result_view, compressed, 8, 0, len(compressed))
        return result
    return buffer

    # throw "HVQ encode not implemented";


# -- shared pieces -----------------------------------------------------------

def _sext8(v):
    v &= 0xFF
    return v - 0x100 if v & 0x80 else v


def _sext16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _sext10(v):
    v &= 0x3FF
    return v - 0x400 if v & 0x200 else v


class BitReader:
    """The games' bit reader: 32-bit big-endian words, most significant bit
    first. A word is fetched when the previous one is used up, so a stream
    may be read a little past its end (the games do too)."""

    def __init__(self, data, pos):
        self.data = data
        self.pos = pos
        self.mask = 0
        self.word = 0

    def bit(self):
        if self.mask == 0:
            chunk = self.data[self.pos:self.pos + 4]
            self.word = int.from_bytes(bytes(chunk).ljust(4, b"\0"), "big")
            self.pos += 4
            self.mask = 0x80000000
        bit = 1 if self.word & self.mask else 0
        self.mask >>= 1
        return bit

    def byte(self):
        v = 0
        for _ in range(8):
            v = (v << 1) | self.bit()
        return v


class HuffmanTree:
    """A Huffman tree as the games store it: a 1 bit is a branch (its 0 child,
    then its 1 child, follow), a 0 bit a leaf followed by its 8-bit symbol."""

    def __init__(self, bits):
        self.left = {}
        self.right = {}
        self.next = 0x100
        self.root = self._read(bits)

    def _read(self, bits):
        if bits.bit():
            idx = self.next
            self.next += 1
            self.left[idx] = self._read(bits)
            self.right[idx] = self._read(bits)
            return idx
        return bits.byte()

    def decode(self, bits):
        node = self.root
        while node >= 0x100:
            node = self.right[node] if bits.bit() else self.left[node]
        return node


class _ByteReader:
    def __init__(self, data, pos):
        self.data = data
        self.pos = pos

    def u16(self):
        v = struct.unpack_from(">H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def u8(self):
        v = self.data[self.pos]
        self.pos += 1
        return v


class _Plane:
    """A plane's 4x4 blocks: each has a DC (0..255) and a mode (0: flat,
    1..7: that many basis vectors, 8: raw pixels)."""

    def __init__(self, bw, bh):
        self.bw = bw
        self.bh = bh
        self.dc = [0] * (bw * bh)
        self.mode = [0] * (bw * bh)


# 4096 / n: scales a basis vector by the inverse of its largest sample.
_RECIP = [0] + [0x1000 // i for i in range(1, 0x200)]


def _decode_dc_plane(plane, delta):
    """Fill a plane's DCs from `delta()` calls: the first row predicts each
    DC from the one on its left, later rows from the average of the DC above
    and the one on the left (the first of a row from the one above)."""
    bw, bh = plane.bw, plane.bh
    dc = plane.dc
    pred = 0
    for x in range(bw):
        pred = (pred + delta()) & 0xFF
        dc[x] = pred
    for y in range(1, bh):
        row = y * bw
        above = row - bw
        pred = dc[above]
        for x in range(bw):
            v = (pred + delta()) & 0xFF
            dc[row + x] = v
            if x + 1 < bw:
                pred = (dc[above + x + 1] + v) >> 1


def _dc_delta_with_escape(table, tree, bits, lo, hi):
    """A DC delta: a symbol's table value, where the two extreme values mean
    "keep adding" until a value that is not extreme."""
    v = table[tree.decode(bits)]
    if v == lo or v == hi:
        total = v
        while True:
            v = table[tree.decode(bits)]
            total += v
            if lo < v < hi:
                break
        return _sext16(total)
    return v


def predict_flat_block(plane, bx, by):
    """The 16 pixels of a flat block, from its DC (S) and the DCs above (U),
    below (B), left (L) and right (R); a neighbour that is not flat, or is
    off the plane, counts as S."""
    bw, bh = plane.bw, plane.bh
    dc, mode = plane.dc, plane.mode
    i = by * bw + bx
    s = dc[i]

    def nb(x, y):
        if x < 0 or y < 0 or x >= bw or y >= bh:
            return s
        j = y * bw + x
        return dc[j] if mode[j] == 0 else s

    u = nb(bx, by - 1)
    b = nb(bx, by + 1)
    l = nb(bx - 1, by)
    r = nb(bx + 1, by)
    return [
        (6 * s + 2 * u + 2 * l - b - r + 4) >> 3,
        (8 * s + 2 * u - b - r + 4) >> 3,
        (8 * s + 2 * u - b - l + 4) >> 3,
        (6 * s + 2 * u + 2 * r - b - l + 4) >> 3,
        (8 * s + 2 * l - b - r + 4) >> 3,
        (10 * s - b - r + 4) >> 3,
        (10 * s - b - l + 4) >> 3,
        (8 * s + 2 * r - b - l + 4) >> 3,
        (8 * s + 2 * l - u - r + 4) >> 3,
        (10 * s - u - r + 4) >> 3,
        (10 * s - u - l + 4) >> 3,
        (8 * s + 2 * r - u - l + 4) >> 3,
        (6 * s + 2 * b + 2 * l - u - r + 4) >> 3,
        (8 * s + 2 * b - u - r + 4) >> 3,
        (8 * s + 2 * b - u - l + 4) >> 3,
        (6 * s + 2 * b + 2 * r - u - l + 4) >> 3,
    ]


# -- colour --------------------------------------------------------------------
#
# The games convert YCbCr to RGBA5551 in fixed point: each colour is
# Y * 64 + (a chroma term + 0x4020), shifted right 6, clamped through a
# 0x300-entry table indexed by value + 256. The tables here are padded (an
# extra _PAD either side), holding the pixel bits of each colour already in
# place, so a row converts with three lookups per pixel.

_PAD = 512

# Y: the games take the low 10 bits of each sample, signed (times 64, but as
# that is a multiple of 64 the shift right by 6 can be done on the chroma
# terms alone).
_Y10 = [((v - 0x400) if v & 0x200 else v) for v in range(0x400)]


def _padded(table, shift_left, shift_right=0):
    out = []
    for i in range(0x300 + 2 * _PAD):
        v = i - _PAD
        v = 0 if v < 0 else 0x2FF if v >= 0x300 else v
        out.append((table[v] << shift_left) >> shift_right)
    return out


def _blocks_to_rgba5551(y_blocks, cb_blocks, cr_blocks, w, h, bw, cbw, hsub, vsub,
                        r_table, g_table, b_table, alpha):
    """Return RGBA5551 bytes of the planes' 4x4 blocks (chroma subsampled
    hsub x vsub); the tables are _padded ones with the bits in place."""
    rows = []
    for py in range(h):
        if py % vsub == 0:
            # The chroma terms of this chroma row, one per pixel. The games
            # take each chroma sample less 128 as a signed 16-bit value.
            cy = py // vsub
            cj = (cy & 3) * 4
            cb_row = []
            cr_row = []
            for blk in range((cy >> 2) * cbw, (cy >> 2) * cbw + cbw):
                cb_row += cb_blocks[blk][cj:cj + 4]
                cr_row += cr_blocks[blk][cj:cj + 4]
            cb_row = [((v - 128 + 0x8000) & 0xFFFF) - 0x8000 for v in cb_row]
            cr_row = [((v - 128 + 0x8000) & 0xFFFF) - 0x8000 for v in cr_row]
            rt = [t for c in cr_row for t in (((90 * c + 0x4020) >> 6) + _PAD,) * hsub]
            gt = [t for c, b in zip(cr_row, cb_row)
                  for t in (((-46 * c - 22 * b + 0x4020) >> 6) + _PAD,) * hsub]
            bt = [t for b in cb_row for t in (((113 * b + 0x4020) >> 6) + _PAD,) * hsub]
        yr = (py & 3) * 4
        y_row = []
        for blk in range((py >> 2) * bw, (py >> 2) * bw + bw):
            y_row += y_blocks[blk][yr:yr + 4]
        rows.append([
            r_table[y + r] | g_table[y + g] | b_table[y + b] | alpha
            for y, r, g, b in zip([_Y10[v & 0x3FF] for v in y_row], rt, gt, bt)])
    out = bytearray(w * h * 2)
    o = 0
    for row in rows:
        out[o:o + w * 2] = b"".join(v.to_bytes(2, "big") for v in row)
        o += w * 2
    return bytes(out)


# -- Mario Party 1: HVQ 2.0 ------------------------------------------------------

# Mario Party 1 clamps to 8 bits with the low 3 bits cleared.
_CLAMP8 = bytes(0 if v < 256 else (v - 256) & 0xF8 if v < 512 else 0xF8 for v in range(0x300))
_R8 = _padded(_CLAMP8, 8)
_G8 = _padded(_CLAMP8, 3)
_B8 = _padded(_CLAMP8, 0, 2)


class HVQ2Decoder:
    """Mario Party 1's tiles.

    File layout (big-endian):
      0x00  "HVQ 2.0" (16 bytes, zero padded)
      0x10  u16 width, u16 height (pixels)
      0x14  u16 nest x, u16 nest y (in 4x4 blocks of the Y DC image)
      0x18  u32 (unused by the decoder)
      0x1c  u8 orientation (8: 70x38 nest, else 38x70), u8 DC shift, u8, u8
      0x20  u32 x16 chunk offsets; each chunk is a u32 byte length + data

    Chunks: 0 block modes for Y (Huffman tree, then data), 1 block modes
    for the two chroma planes (nibble packed, same tree), 2 the run-length
    tree and Y runs, 3 chroma runs; 4 DC deltas for Y (tree + data), 5 / 6
    for the chroma planes, 7 / 8 / 9 DC zero runs; 10 AC coefficients for Y
    (tree + data), 11 / 12 chroma; 13 / 14 / 15 raw bytes per plane: basis
    index words (u16) and the pixels of raw (mode 8) blocks.

    The image is YCrCb 4:2:0 in 4x4 blocks. The nest is a 70x38 window of
    the Y DC image (mirrored and zero padded past the plane's edge).
    """

    def __init__(self, data):
        self.data = data = bytes(data)
        if data[:7] != b"HVQ 2.0":
            raise ValueError("not an HVQ 2.0 file")
        self.width, self.height = struct.unpack_from(">HH", data, 0x10)
        self.nest_x, self.nest_y = struct.unpack_from(">HH", data, 0x14)
        self.orient = data[0x1C]
        self.dc_shift = data[0x1D]
        offsets = struct.unpack_from(">16I", data, 0x20)
        self.chunks = []
        for off in offsets:
            length = struct.unpack_from(">I", data, off)[0]
            self.chunks.append((off + 4, length))
        if self.orient == 8:
            self.nest_w, self.nest_h = 70, 38
        else:
            self.nest_w, self.nest_h = 38, 70

    def _bits(self, chunk):
        off, length = self.chunks[chunk]
        return BitReader(self.data, off) if length else None

    def _raw(self, chunk):
        return _ByteReader(self.data, self.chunks[chunk][0])

    def decode(self):
        """Return the tile as big-endian RGBA5551 bytes (alpha set)."""
        w, h = self.width, self.height
        bw, bh = w >> 2, h >> 2
        y_plane = _Plane(bw, bh)
        c_planes = [_Plane(bw >> 1, bh >> 1), _Plane(bw >> 1, bh >> 1)]

        # Block modes.
        r0 = self._bits(0)
        mode_tree = HuffmanTree(r0)
        r2 = self._bits(2)
        run_tree = HuffmanTree(r2)
        self._decode_modes([y_plane], r0, mode_tree, r2, run_tree)
        self._decode_modes(c_planes, self._bits(1), mode_tree, self._bits(3), run_tree)

        # DC values.
        r4 = self._bits(4)
        dc_tree = HuffmanTree(r4)
        dc_table = [_sext8(i) << self.dc_shift for i in range(256)]
        self._decode_dc(y_plane, r4, self._bits(7), dc_tree, run_tree, dc_table)
        self._decode_dc(c_planes[0], self._bits(5), self._bits(8), dc_tree, run_tree, dc_table)
        self._decode_dc(c_planes[1], self._bits(6), self._bits(9), dc_tree, run_tree, dc_table)

        self.nest = self._build_nest(y_plane)

        # AC: the coefficient streams and the raw streams per plane.
        r10 = self._bits(10)
        ac_tree = HuffmanTree(r10)
        ac_table = [_sext8(i) * 8 for i in range(256)]
        planes = [y_plane] + c_planes
        ac_bits = [r10, self._bits(11), self._bits(12)]
        raws = [self._raw(13), self._raw(14), self._raw(15)]

        pixels = []
        for p, plane in enumerate(planes):
            blocks = []
            for by in range(plane.bh):
                for bx in range(plane.bw):
                    i = by * plane.bw + bx
                    mode = plane.mode[i]
                    if mode == 0:
                        blocks.append(predict_flat_block(plane, bx, by))
                    elif mode == 8:
                        blocks.append([raws[p].u8() for _ in range(16)])
                    else:
                        blocks.append(self._basis_block(plane.dc[i], mode, ac_bits[p], ac_tree,
                                                        ac_table, raws[p]))
            pixels.append(blocks)

        return self._to_rgba5551(pixels, y_plane, c_planes[0])

    def _decode_modes(self, planes, bits, tree, run_bits, run_tree):
        """Y modes are a symbol each; the chroma planes' are packed in one
        symbol (low nibble: first plane). A 0 symbol is a run of flat
        blocks, its length (less one) from the run stream."""
        n = len(planes[0].mode)
        i = 0
        while i < n:
            sym = tree.decode(bits)
            if sym:
                if len(planes) == 1:
                    planes[0].mode[i] = sym
                else:
                    planes[0].mode[i] = sym & 0xF
                    planes[1].mode[i] = sym >> 4
                i += 1
            else:
                i += run_tree.decode(run_bits) + 1

    def _decode_dc(self, plane, bits, run_bits, tree, run_tree, table):
        lo = (-0x80) << self.dc_shift
        hi = 0x7F << self.dc_shift
        state = [0]  # pending zero run

        def delta():
            if state[0]:
                state[0] -= 1
                return 0
            v = table[tree.decode(bits)]
            if v == 0:
                state[0] = run_tree.decode(run_bits)
                return 0
            if v == lo or v == hi:
                total = v
                while True:
                    v = table[tree.decode(bits)]
                    total += v
                    if lo < v < hi:
                        break
                return _sext16(total)
            return v

        _decode_dc_plane(plane, delta)

    def _build_nest(self, plane):
        nw, nh = self.nest_w, self.nest_h
        bw, bh = plane.bw, plane.bh
        src = self.nest_x + self.nest_y * bw
        if bw < nw:
            copy_w = bw
            mirror_w = min(bw, nw - bw)
        else:
            copy_w, mirror_w = nw, 0
        if bh < nh:
            copy_h = bh
            mirror_h = min(bh, nh - bh)
        else:
            copy_h, mirror_h = nh, 0

        dc = plane.dc
        rows = []
        for y in range(copy_h):
            base = src + y * bw
            row = [dc[base + x] if base + x < len(dc) else 0 for x in range(copy_w)]
            row += row[::-1][:mirror_w]
            row += [0] * (nw - len(row))
            rows.append(row)
        for y in range(mirror_h):
            rows.append(list(rows[copy_h - 1 - y]))
        while len(rows) < nh:
            rows.append([0] * nw)
        nest = []
        for row in rows:
            nest.extend(row)
        return nest

    def _basis_block(self, dc, count, bits, tree, table, raw):
        """DC plus `count` basis vectors. Each is a 4x4 sample of the nest
        (the index word gives its position and strides, 1 or 2) less its
        mean, scaled so its largest sample is 1, times the coefficient."""
        nw = self.nest_w
        nest = self.nest
        out = [dc] * 16
        for _ in range(count):
            coef = table[tree.decode(bits)]
            idx = raw.u16()
            sx = (idx & 1) + 1
            sy = ((idx >> 1) & 1) + 1
            if self.orient == 8:
                y = (idx >> 8) & 0x1F
                x = (idx >> 2) & 0x3F
            else:
                y = (idx >> 7) & 0x3F
                x = (idx >> 2) & 0x1F
            samples = []
            for r in range(4):
                base = (y + r * sy) * nw + x
                for c in range(4):
                    samples.append(nest[base + c * sx])
            mean = (sum(samples) + 8) >> 4
            basis = [s - mean for s in samples]
            scale = _RECIP[max(map(abs, basis))] * (coef + (idx >> 13))
            out = [o + ((scale * b + 0x200) >> 10) for o, b in zip(out, basis)]
        return out

    def _to_rgba5551(self, pixels, y_plane, c_plane):
        # The first chroma plane is Cr. The game leaves the alpha bit clear;
        # the editor wants it set.
        y_blocks, cr_blocks, cb_blocks = pixels
        return _blocks_to_rgba5551(y_blocks, cb_blocks, cr_blocks, self.width, self.height,
                                   y_plane.bw, c_plane.bw, 2, 2, _R8, _G8, _B8, 1)


# -- Mario Party 2 and 3: HVQ-MPS 1.1 and HVQS --------------------------------------

def _clamp_tables(alpha=1):
    """The games' two clamp tables: 5-bit colour (shifted left once) for red
    and green, and the same with the alpha bit for blue."""
    a = bytearray(0x300)
    b = bytearray(0x300)
    for i in range(0x300):
        v = i - 256
        if v < 0:
            a[i], b[i] = 0, alpha
        elif v >= 256:
            a[i], b[i] = 0x3E, 0x3E | alpha
        else:
            a[i] = (v >> 2) & 0x3E
            b[i] = a[i] | alpha
    return bytes(a), bytes(b)


_CLAMP_A, _CLAMP_B = _clamp_tables()
_R5 = _padded(_CLAMP_A, 10)
_G5 = _padded(_CLAMP_A, 5)
_B5 = _padded(_CLAMP_B, 0)


class HVQMPS:
    """A background's "HVQ-MPS 1.1" file: what its HVQS tiles share.

    Layout (big-endian):
      0x00  "HVQ-MPS 1.1" (16 bytes, zero padded)
      0x10  u32 file size
      0x14  u16 tile width, u16 tile height
      0x18  u8 chroma horizontal subsampling, u8 vertical subsampling
      0x1a  u8: high nibble DC shift, low nibble AC precision (the AC shift
            is 12 less it)
      0x1b  u8 nest orientation (0: 70x38, else 38x70)
      0x1c  u32 x4 chunk offsets (u32 length + data): the Huffman trees for
            block modes, DC deltas, AC coefficients, and the nest; the last
            tree's bits continue with the nest's samples (DPCM, steps of 16)
    """

    def __init__(self, data):
        data = bytes(data)
        if data[:7] != b"HVQ-MPS":
            raise ValueError("not an HVQ-MPS file")
        self.width, self.height = struct.unpack_from(">HH", data, 0x14)
        self.hsub = data[0x18] or 1
        self.vsub = data[0x19] or 1
        self.dc_shift = data[0x1A] >> 4
        self.ac_shift = 12 - (data[0x1A] & 0xF)
        self.ac_round = 1 << (self.ac_shift - 1)
        self.orient = data[0x1B]
        if self.orient == 0:
            self.nest_w, self.nest_h = 70, 38
        else:
            self.nest_w, self.nest_h = 38, 70
        offsets = struct.unpack_from(">4I", data, 0x1C)
        trees = []
        bits = None
        for off in offsets:
            bits = BitReader(data, off + 4)
            trees.append(HuffmanTree(bits))
        self.mode_tree, self.dc_tree, self.ac_tree, nest_tree = trees
        acc = 0
        nest = []
        for _ in range(self.nest_w * self.nest_h):
            acc += _sext8(nest_tree.decode(bits)) << 4
            nest.append(acc & 0xFF)
        self.nest = nest
        self.dc_table = [_sext8(i) << self.dc_shift for i in range(256)]
        self.ac_table = [_sext8(i) * 4 for i in range(256)]
        self.dc_lo = (-0x80) << self.dc_shift
        self.dc_hi = 0x7F << self.dc_shift


class HVQSDecoder:
    """Mario Party 2 and 3's tiles.

    Layout (big-endian):
      0x00  "HVQS", u32 size
      0x08  u32 x11 chunk offsets, relative to 0x04 (u32 length + data):
            Y block modes; chroma block modes (two nibbles, low: Cb); DC
            deltas for Y, Cb, Cr; AC coefficients for Y, Cb, Cr; raw bytes
            for Y, Cb, Cr (basis index words and the pixels of raw blocks)

    The image is YCbCr in 4x4 blocks, the chroma subsampled as the HVQ-MPS
    says (4:2:2 in the games' backgrounds).
    """

    def __init__(self, data, mps):
        self.data = data = bytes(data)
        if data[:4] != b"HVQS":
            raise ValueError("not an HVQS file")
        self.mps = mps
        offsets = struct.unpack_from(">11I", data, 8)
        self.chunks = []
        for off in offsets:
            start = 4 + off
            length = struct.unpack_from(">I", data, start)[0]
            self.chunks.append((start + 4, length))

    def _bits(self, chunk):
        off, length = self.chunks[chunk]
        return BitReader(self.data, off) if length else None

    def _raw(self, chunk):
        return _ByteReader(self.data, self.chunks[chunk][0])

    def decode(self):
        """Return the tile as big-endian RGBA5551 bytes."""
        mps = self.mps
        w, h = mps.width, mps.height
        bw, bh = w >> 2, h >> 2
        cbw, cbh = bw // mps.hsub, bh // mps.vsub
        y_plane = _Plane(bw, bh)
        c_planes = [_Plane(cbw, cbh), _Plane(cbw, cbh)]

        # Block modes.
        bits = self._bits(0)
        for i in range(bw * bh):
            y_plane.mode[i] = mps.mode_tree.decode(bits)
        bits = self._bits(1)
        for i in range(cbw * cbh):
            sym = mps.mode_tree.decode(bits)
            c_planes[0].mode[i] = sym & 0xF
            c_planes[1].mode[i] = sym >> 4

        # DC values.
        planes = [y_plane] + c_planes
        for p, plane in enumerate(planes):
            bits = self._bits(2 + p)
            _decode_dc_plane(plane, lambda: _dc_delta_with_escape(
                mps.dc_table, mps.dc_tree, bits, mps.dc_lo, mps.dc_hi))

        # Pixels.
        pixels = []
        for p, plane in enumerate(planes):
            ac_bits = self._bits(5 + p)
            raw = self._raw(8 + p)
            blocks = []
            for by in range(plane.bh):
                for bx in range(plane.bw):
                    i = by * plane.bw + bx
                    mode = plane.mode[i]
                    if mode == 0:
                        blocks.append(predict_flat_block(plane, bx, by))
                    elif mode == 8:
                        blocks.append([raw.u8() for _ in range(16)])
                    else:
                        blocks.append(self._basis_block(plane.dc[i], mode, ac_bits, raw))
            pixels.append(blocks)

        return self._to_rgba5551(pixels, y_plane, c_planes[0])

    def _basis_block(self, dc, count, bits, raw):
        """DC plus `count` basis vectors, summed in fixed point. The
        coefficients are differences within the block, each with two more
        bits and the sign in the index word."""
        mps = self.mps
        nest, nw = mps.nest, mps.nest_w
        acc = [(dc << mps.ac_shift) + mps.ac_round] * 16
        running = 0
        for _ in range(count):
            idx = raw.u16()
            if mps.orient == 0:
                pos = ((idx >> 6) & 0x1F) * nw + (idx & 0x3F)
                sx = ((idx >> 11) & 1) + 1
                row = nw * 2 if (idx >> 12) & 1 else nw
            else:
                pos = (idx & 0x3F) * nw + ((idx >> 6) & 0x1F)
                sx = ((idx >> 12) & 1) + 1
                row = nw * 2 if (idx >> 11) & 1 else nw
            samples = []
            for r in range(4):
                base = pos + r * row
                for c in range(4):
                    samples.append(nest[base + c * sx])
            mean = sum(samples) >> 4
            basis = [s - mean for s in samples]
            running += mps.ac_table[mps.ac_tree.decode(bits)]
            coef = running + ((idx >> 13) & 3)
            recip = _RECIP[max(map(abs, basis))]
            if idx & 0x8000:
                recip = -recip
            scale = recip * coef
            acc = [a + scale * b for a, b in zip(acc, basis)]
        shift = mps.ac_shift
        return [a >> shift for a in acc]

    def _to_rgba5551(self, pixels, y_plane, c_plane):
        mps = self.mps
        y_blocks, cb_blocks, cr_blocks = pixels
        return _blocks_to_rgba5551(y_blocks, cb_blocks, cr_blocks, mps.width, mps.height,
                                   y_plane.bw, c_plane.bw, mps.hsub, mps.vsub, _R5, _G5, _B5, 0)
