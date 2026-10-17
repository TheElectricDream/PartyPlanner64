"""The HVQ background tile decoders (utils/img/hvq.py).

The games' tiles are only in the ROMs, so the real decodes are checked
against hashes of tiles decoded here and checked by eye, when the ROMs are
in `roms/` (or $PP64_ROMS). The building blocks are tested on their own.
"""

import hashlib
import os
import struct

import pytest

from partyplanner64.lib.utils.dataview import DataView
from partyplanner64.lib.utils.img import hvq
from partyplanner64.lib.utils.img.hvq import BitReader, HuffmanTree, HVQMPS, decode, predict_flat_block

ROM_DIRS = [os.environ.get("PP64_ROMS", ""),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "roms")]


def _bits(s):
    """Bytes from a string of 0s and 1s (MSB first, zero padded)."""
    s = s.replace(" ", "")
    s += "0" * (-len(s) % 32)
    return int(s, 2).to_bytes(len(s) // 8, "big")


def test_bit_reader_reads_msb_first_in_words():
    r = BitReader(_bits("1 0 1 1 00001111 10000000"), 0)
    assert [r.bit() for _ in range(4)] == [1, 0, 1, 1]
    assert r.byte() == 0x0F
    assert r.bit() == 1
    # Past the end: zeros, as if the next word were blank.
    r = BitReader(b"\x80\x00\x00\x00", 0)
    assert r.bit() == 1
    assert [r.bit() for _ in range(40)] == [0] * 40


def test_huffman_tree_layout():
    # A branch: 1, then its 0 child and 1 child. Leaves: 0 + 8 bits.
    #   root -> 0: 'A' (0x41), 1: branch -> 0: 'B', 1: 'C'
    data = _bits("1 0 01000001 1 0 01000010 0 01000011   0 10 11 0")
    r = BitReader(data, 0)
    tree = HuffmanTree(r)
    assert tree.root == 0x100
    assert tree.left[0x100] == 0x41
    assert tree.right[0x100] == 0x101
    assert (tree.left[0x101], tree.right[0x101]) == (0x42, 0x43)
    assert [tree.decode(r) for _ in range(4)] == [0x41, 0x42, 0x43, 0x41]


def test_flat_block_prediction():
    plane = hvq._Plane(3, 3)
    plane.dc = [10, 20, 30,
                40, 100, 60,
                70, 80, 90]
    out = predict_flat_block(plane, 1, 1)
    s, u, b, l, r = 100, 20, 80, 40, 60
    assert out[0] == (6 * s + 2 * u + 2 * l - b - r + 4) >> 3
    assert out[5] == (10 * s - b - r + 4) >> 3
    assert out[15] == (6 * s + 2 * b + 2 * r - u - l + 4) >> 3
    # A neighbour that is not flat counts as the block's own DC.
    plane.mode[1] = 3
    out2 = predict_flat_block(plane, 1, 1)
    assert out2[5] == out[5]
    assert out2[0] == (6 * s + 2 * s + 2 * l - b - r + 4) >> 3
    # Off the plane: the block's own DC too, so a lone block is flat.
    lone = hvq._Plane(1, 1)
    lone.dc = [77]
    assert predict_flat_block(lone, 0, 0) == [77] * 16


def test_clamp_tables():
    assert hvq._CLAMP8[0] == 0 and hvq._CLAMP8[256 + 200] == 200 & 0xF8 and hvq._CLAMP8[0x2FF] == 0xF8
    a, b = hvq._CLAMP_A, hvq._CLAMP_B
    assert a[255] == 0 and b[255] == 1                  # below 0: black, alpha set
    assert a[256 + 200] == (200 >> 2) & 0x3E and b[256 + 200] == a[256 + 200] | 1
    assert a[0x2FF] == 0x3E and b[0x2FF] == 0x3F
    assert hvq._RECIP[1] == 0x1000 and hvq._RECIP[3] == 0x1000 // 3 and hvq._RECIP[0] == 0


def test_undecodable_hvq_tiles_read_as_black():
    black = b"\x00\x01" * (0x1800 // 2)
    assert bytes(decode(DataView(bytearray(b"HVQ 2.0" + b"\0" * 25)))) == black   # truncated
    assert bytes(decode(DataView(bytearray(b"HVQS" + b"\0" * 60)))) == black      # no HVQ-MPS
    assert bytes(decode(DataView(bytearray(b"HVQX" + b"\0" * 60)))) == black      # unknown
    with pytest.raises(ValueError):
        HVQMPS(b"HVQS" + b"\0" * 60)


def _find_rom(names):
    for d in ROM_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if any(name.lower().startswith(n) and name.lower().endswith((".z64", ".n64", ".v64"))
                   for n in names):
                return os.path.join(d, name)
    return None


@pytest.fixture
def load_rom():
    """Loads a ROM into the (global) romhandler, and clears it after."""
    from partyplanner64.cli import _load_rom, _setup_library
    from partyplanner64.lib.romhandler import romhandler

    def load(rom_file):
        _setup_library()
        assert _load_rom(rom_file)
        return romhandler.get_rom()

    yield load
    romhandler.clear()


# (background directory, tile file, sha1 of the tile, sha1 of its RGBA5551)
REAL = {
    "mp1": (("mario party (", "mario party (u", "mario party (usa"), 0, [
        (1, "5afcda1b66f2e671ff4d0b431411e20c46127814", "fcd6ff6bc17caa1d715e52aab34b35c8f1d83fde"),
        (2, "811a297427709d224424ad9350298fb7a75f6b1f", "bacf5a4007a00867130b7f5d3c1d2363519f65f9"),
        (8, "2a8ecce478e08fb29b5282d28194539f3a01c4f7", "ebe64ab2d3be4f9634e81eea8f498720a2b14b27"),
    ]),
    "mp2": (("mario party 2",), 3, [
        (2, "1ff08093b6353e24f79f588fe5de8d4d82afab5f", "c26516fe2044869b00f936297b3fb05cbb335d17"),
        (3, "a71c50f986b5f985137b1defd03e67b91357c70a", "fc66a286666f935c8a4b0be9aa96280f3d564f3b"),
        (9, "c6b24841aefc68934fb064ea482b67f6075f8411", "9b147a3bb302aaa5010933c444fb30d717badb92"),
    ]),
    "mp3": (("mario party 3",), 3, [
        (2, "b9c2efe89ee9ea2cab18ab89fc23d3a3885468a6", "24f79ed8e30201843516da57ae10d213f817be98"),
        (3, "035aa963a730ba95da192985f33028da0c863b4b", "f05930a611f21aceccd4d23af5385cd189a14af8"),
        (9, "6850e37e437a604cd67814da396b855b11aecb60", "8db29428a2fb6670f9e80dd131f71a42985489dd"),
    ]),
}


@pytest.mark.parametrize("game", sorted(REAL))
def test_real_tiles(game, load_rom):
    names, bg_dir, tiles = REAL[game]
    rom_file = _find_rom(names)
    if not rom_file:
        pytest.skip("no %s ROM in roms/ or $PP64_ROMS" % game)
    rom = load_rom(rom_file)
    hvqfs = rom.get_hvqfs()
    files = hvqfs._hvq_cache[bg_dir]
    mps = hvqfs._get_mps(bg_dir)
    assert (mps is None) == (game == "mp1")
    for file, tile_sha1, out_sha1 in tiles:
        tile = bytes(files[file])
        if hashlib.sha1(tile).hexdigest() != tile_sha1:
            pytest.skip("the %s ROM is not the one the hashes are from" % game)
        out = decode(DataView(bytearray(tile)), mps)
        assert len(out) == 64 * 48 * 2
        assert hashlib.sha1(bytes(out)).hexdigest() == out_sha1
        # The editor wants opaque pixels.
        assert all(out[i] & 1 for i in range(1, len(out), 2))
    if mps is not None:
        assert (mps.width, mps.height, mps.hsub, mps.vsub) == (64, 48, 2, 1)
        assert len(mps.nest) == 70 * 38
    # The whole board background reads (no exception, nothing black).
    img = hvqfs.read_background_img_data(bg_dir)
    assert img.width == 64 * hvqfs.get_metadata(bg_dir)["tileCountX"]
    assert any(img.data[i] for i in range(0, 4 * 1000, 4))
