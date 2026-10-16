"""RGBA32 helpers (port of utils/img/RGBA32.ts)."""


def make8_bit(u32arr, width, height):
    """Reduce each RGBA32 pixel to two bits per channel, in place.

    Used internally for now by board select image. Ideally we can implement
    fancy image color count reduction instead.

    u32arr is a bytearray of RGBA32 pixels (a Uint32Array over it in the
    TypeScript; the operation is per byte, so byte order doesn't matter) or a
    list of 32-bit values.
    """
    count = width * height
    if isinstance(u32arr, list):
        for i in range(count):
            val = u32arr[i] & 0xC0C0C0C0
            val |= val >> 2
            val |= val >> 2
            val |= val >> 2
            u32arr[i] = val
        return
    table = bytes(((v & 0xC0) | ((v & 0xC0) >> 2) | ((v & 0xC0) >> 4) | ((v & 0xC0) >> 6))
                  for v in range(256))
    u32arr[0:count * 4] = bytes(u32arr[0:count * 4]).translate(table)

