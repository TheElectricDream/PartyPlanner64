"""HVQ background tiles (port of utils/img/HVQ.ts).

Real HVQ decoding was never implemented in PartyPlanner64: HVQ-compressed
tiles decode to black, while the run-length/LZ "type 3" tiles that the
editor writes (and Mario Party 2/3 accept) decode properly.
"""

from ..arrays import _region, copy_range
from ..compression import compress, decompress
from ..dataview import DataView

_black_rgb16 = None


def decode(hvq_view):
    """Return the RGBA5551 bytes of a background tile."""
    if not isinstance(hvq_view, DataView):
        hvq_view = DataView(hvq_view if not isinstance(hvq_view, memoryview) else bytearray(hvq_view))
    first_word = hvq_view.get_uint32(0)
    is_hvq = (first_word & 0xFFFFFF00) == 0x48565100  # "HVQ"
    if first_word == 0x00000003:
        # MP2+ can have run-length instead
        # (As in the TypeScript, the data is read from offset 8 of the
        # underlying buffer, not of the view.)
        file_start_view = DataView(hvq_view.buffer, 8)
        decompressed_size = hvq_view.get_uint32(4)
        return decompress(3, file_start_view, decompressed_size)
    if not is_hvq:
        return hvq_view.bytes()

    global _black_rgb16
    if _black_rgb16 is None:
        _black_rgb16 = bytes(b"\x00\x01" * (0x1800 // 2))

    return bytearray(_black_rgb16)  # FIXME LOL


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
