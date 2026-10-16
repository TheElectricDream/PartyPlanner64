"""N64 ROM checksums (port of utils/CIC.ts).

N64 ROMs have checksums that need to be correct to run on real hardware.
The following logic is responsible for recalculating those checksums.

I have no idea who originally did the work to figure all this out. I mostly
ported the source code from spinout182's n64crc.c code.
"""

import struct
import zlib

from .debug import hexstr, log

# Different possible CIC variations.
# MP uses 6102 but we might as well write this in a generic way.
Type = {
    "6101": 6101,
    "6102": 6102,
    "6103": 6103,
    "6105": 6105,
    "6106": 6106,
}

N64_HEADER_SIZE = 0x40
CHECKSUM_START = 0x00001000
CHECKSUM_LENGTH = 0x00100000

_M = 0xFFFFFFFF


def fix_checksum(buffer):
    """Fixes the checksum of a ROM buffer (a bytearray), in place."""
    bootcode = _get_game_cic(buffer)
    seed = _get_checksum_seed(bootcode)
    t1 = t2 = t3 = t4 = t5 = t6 = seed

    log("CIC.fixChecksum -> Bootcode: %s, seed: %s" % (bootcode, hexstr(seed)))

    if len(buffer) < CHECKSUM_START + CHECKSUM_LENGTH:
        raise IndexError("Offset is outside the bounds of the DataView")
    words = struct.unpack_from(">%dI" % (CHECKSUM_LENGTH // 4), buffer, CHECKSUM_START)
    is6105 = bootcode == 6105
    if is6105:
        extra = struct.unpack_from(">64I", buffer, N64_HEADER_SIZE + 0x0710)

    i = CHECKSUM_START
    for d in words:
        if ((t6 + d) & _M) < t6:
            t4 = (t4 + 1) & _M
        t6 = (t6 + d) & _M
        t3 ^= d
        b = d & 0x1F
        r = ((d << b) | (d >> (32 - b))) & _M if b else d
        t5 = (t5 + r) & _M
        if t2 > d:
            t2 ^= r
        else:
            t2 ^= t6 ^ d

        if is6105:
            t1 = (t1 + (extra[(i & 0xFF) >> 2] ^ d)) & _M
        else:
            t1 = (t1 + (t5 ^ d)) & _M
        i += 4

    if bootcode == 6103:
        crc1 = ((t6 ^ t4) + t3) & _M
        crc2 = ((t5 ^ t2) + t1) & _M
    elif bootcode == 6106:
        # JavaScript multiplied these as doubles.
        crc1 = ((int(float(t6) * float(t4)) & _M) + t3) & _M
        crc2 = ((int(float(t5) * float(t2)) & _M) + t1) & _M
    else:
        crc1 = t6 ^ t4 ^ t3
        crc2 = t5 ^ t2 ^ t1

    struct.pack_into(">II", buffer, 0x10, crc1, crc2)

    log("CIC.fixChecksum -> CRC1: %s, CRC2: %s" % (hexstr(crc1), hexstr(crc2)))


def _get_checksum_seed(bootcode):
    if bootcode in (6101, 6102):
        return 0xF8CA4DDC
    if bootcode == 6103:
        return 0xA3886759
    if bootcode == 6105:
        return 0xDF26F436
    if bootcode == 6106:
        return 0x1FEA617A
    raise ValueError("CIC._getChecksumSeed: Bad bootcode %s" % bootcode)


def _get_game_cic(buffer):
    n64_bc_size = 0x1000 - N64_HEADER_SIZE
    if len(buffer) < N64_HEADER_SIZE + n64_bc_size:
        raise IndexError("Invalid typed array length")
    crc = _crc32(memoryview(buffer)[N64_HEADER_SIZE:N64_HEADER_SIZE + n64_bc_size])
    return {
        0x6170A4A1: Type["6101"],
        0x90BB6CB5: Type["6102"],
        0x0B050EE0: Type["6103"],
        0x98BC2C86: Type["6105"],
        0xACC8580A: Type["6106"],
    }.get(crc, Type["6105"])  # Why is this the default?


def _crc32(arr):
    return zlib.crc32(arr) & _M
