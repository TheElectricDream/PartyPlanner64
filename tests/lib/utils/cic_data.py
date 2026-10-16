"""Synthetic ROM-sized buffers for the CIC checksum tests.

The bootcode region (0x40-0x1000) is random, with its last four bytes
forged so that its CRC32 selects each CIC variant.
"""

import random
import zlib

CIC_CRCS = {6101: 0x6170A4A1, 6102: 0x90BB6CB5, 6103: 0x0B050EE0, 6105: 0x98BC2C86, 6106: 0xACC8580A}
SIZE = 0x101000 + 0x40


def _forge_last4(region, target):
    """Set the last 4 bytes of region so that crc32(region) == target (GF(2) solve)."""
    def crc_with(x):
        region[-4:] = x.to_bytes(4, "little")
        return zlib.crc32(region)
    base = crc_with(0)
    cols = [crc_with(1 << i) ^ base for i in range(32)]
    # Solve sum(x_i * cols[i]) == target ^ base by Gaussian elimination.
    basis = {}
    for i, col in enumerate(cols):
        comb = 1 << i
        v = col
        while v:
            top = v.bit_length() - 1
            if top in basis:
                bv, bc = basis[top]
                v ^= bv
                comb ^= bc
            else:
                basis[top] = (v, comb)
                break
    want = target ^ base
    x = 0
    v = want
    while v:
        top = v.bit_length() - 1
        bv, bc = basis[top]
        v ^= bv
        x ^= bc
    region[-4:] = x.to_bytes(4, "little")
    assert zlib.crc32(region) == target


def make_rom(seed, bootcode):
    rng = random.Random(seed)
    buf = bytearray(rng.getrandbits(8) for _ in range(0x1000))
    buf += rng.randbytes(SIZE - 0x1000)
    if bootcode in CIC_CRCS:
        region = buf[0x40:0x1000]
        _forge_last4(region, CIC_CRCS[bootcode])
        buf[0x40:0x1000] = region
    return buf
