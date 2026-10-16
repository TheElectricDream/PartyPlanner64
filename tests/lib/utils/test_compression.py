import base64
import json
import os
import random

import pytest

from partyplanner64.lib.utils.compression import (
    compress, decompress, get_compressed_size, DecompressedBuffer)
from partyplanner64.lib.utils.dataview import DataView

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "core")


def _load():
    with open(os.path.join(FIXTURES, "compression.json")) as f:
        return json.load(f)


DATA = _load()
b64 = base64.b64decode


@pytest.mark.parametrize("case", DATA["compress"], ids=lambda c: "t%d-%d" % (c["type"], len(c["input"])))
def test_compress_matches_typescript(case):
    data = bytearray(b64(case["input"]))
    if case["output"] is None and case["type"] == 5:
        # The TypeScript's compress05 always throws (it reads past the end of
        # its input and copies literals with a doubled stride); the port is
        # the working algorithm, checked by round trip.
        out = compress(5, DataView(data))
        assert bytes(decompress(5, out, len(data))) == bytes(data)
        return
    if case["output"] is None:
        with pytest.raises(Exception):
            compress(case["type"], DataView(data))
        return
    out = compress(case["type"], DataView(data))
    assert bytes(out) == b64(case["output"])
    # And it decompresses back.
    back = decompress(case["type"], DataView(out), len(data))
    assert bytes(back) == bytes(data)
    assert back.compressed_size == len(out)


@pytest.mark.parametrize("case", DATA["decompress"], ids=lambda c: "t%d-%d" % (c["type"], c["size"]))
def test_decompress_matches_typescript(case):
    src = bytearray(b64(case["input"]))
    out = decompress(case["type"], DataView(src), case["size"])
    assert isinstance(out, DecompressedBuffer)
    assert bytes(out) == b64(case["output"])
    assert out.compressed_size == case["compressedSize"]
    assert get_compressed_size(case["type"], DataView(src), case["size"]) == case["compressedSize"]


def test_dataview_offset_and_other_sources():
    data = bytearray(b"\x00" * 5 + bytes(compress(1, bytearray(b"hello world"))))
    view = DataView(data, 5)
    assert bytes(decompress(1, view, 11)) == b"hello world"
    assert bytes(decompress(1, bytes(data[5:]), 11)) == b"hello world"
    assert bytes(decompress(1, memoryview(data)[5:], 11)) == b"hello world"


@pytest.mark.parametrize("type", [1, 2, 3, 4, 5, 0])
def test_roundtrip_random(type):
    rng = random.Random(type)
    for n in [0, 32, 64, 320, 6144]:
        for kind in range(3):
            if kind == 0:
                data = bytearray(rng.getrandbits(8) for _ in range(n))
            elif kind == 1:
                data = bytearray(n)
            else:
                data = bytearray((i // 7) & 3 for i in range(n))
            out = compress(type, data)
            assert bytes(decompress(type, out, n)) == bytes(data)


def test_unknown_type():
    out = decompress(9, bytearray(4), 4)
    assert bytes(out) == bytes(4) and out.compressed_size is None


def test_compress05_known_output():
    assert bytes(compress(5, bytearray([1, 1, 1, 2]))) == bytes([3, 1, 0x81, 2])
    assert bytes(compress(5, bytearray([1, 2, 3]))) == bytes([0x83, 1, 2, 3])
    assert bytes(compress(5, bytearray([7] * 130))) == bytes([127, 7, 3, 7])
