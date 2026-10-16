"""The game fonts are packaged in a special file format (port of utils/img/FontPack.ts).

```
struct FontPack {
  u32 palette_offset;
  u32 images_offset;
  u32 chars_offset;
  u16 palette[]; // RGBA5551. If palette_offset > 0
  u8 images[]; // 8-bit BMP. If images_offset > 0
  u8 chars[]; // 4-bit intensity BMP.
}
```

IFontPack is a dict: {"images": [bytearray], "chars": [bytearray], "bpp",
"char_width", "char_height"}.
"""

from ..arrays import _region
from ..dataview import DataView
from .bmp import bm_pto_rgba
from .rgba5551 import rgba5551to_rgba32

# The known font size configurations from the game.
SIZE_CONFIGS = [
    {"w": 10, "h": 12},
    {"w": 8, "h": 8},
]


def _bytes(buffer):
    buf, start, length = _region(buffer)
    return bytes(buf[start:start + length])


def is_font_pack(buffer):
    """Does the given file appear to be a font pack?"""
    data = _bytes(buffer)
    view = DataView(data)

    # Sanity check size and offsets.
    if len(data) < 32:
        return False

    palette_offset = view.get_uint32(0)
    images_offset = view.get_uint32(4)
    chars_offset = view.get_uint32(8)
    if palette_offset > images_offset or images_offset > chars_offset:
        return False
    if palette_offset == images_offset and palette_offset != 0:
        return False
    if palette_offset != 12 and images_offset != 12 and chars_offset != 12:
        return False

    palette_size = images_offset - palette_offset
    if palette_size % 2 != 0:
        return False

    return bool(_find_matching_size_config(images_offset, chars_offset, len(data)))


def _find_matching_size_config(images_offset, chars_offset, byte_length):
    for config in SIZE_CONFIGS:
        char_pixels = config["w"] * config["h"]

        if images_offset > 0:
            images_size = chars_offset - images_offset
            if images_size % char_pixels != 0:
                continue

        chars_size = byte_length - chars_offset
        if chars_size % (char_pixels / 2) != 0:
            continue

        return config

    return None


def is_known_font_pack(game, dir, file):
    """Checks if file is a known font pack from a specific game."""
    # switch (game) {
    #   case Game.MP1_USA:
    #     if (dir === 0) {
    #       if (file === 134) {
    #         return true;
    #       }
    #     }
    #     break;
    # }
    return False


def font_pack_to_rgba32(buffer):
    """Return the font pack's images and characters as RGBA32 bytes."""
    data = _bytes(buffer)
    view = DataView(data)
    palette_offset = view.get_uint32(0)
    images_offset = view.get_uint32(4)
    chars_offset = view.get_uint32(8)

    config = _find_matching_size_config(images_offset, chars_offset, len(data))
    if not config:
        raise ValueError("Unrecongized font size")

    char_pixels = config["w"] * config["h"]

    pack = {
        "images": [],
        "chars": [],
        "bpp": 32,
        "char_width": config["w"],
        "char_height": config["h"],
    }

    # Extract palette.
    palette5551 = []
    if palette_offset > 0:
        palette_len = (images_offset - palette_offset) / 2
        i = 0
        while i < palette_len:
            palette5551.append(view.get_uint16(palette_offset + i * 2))
            i += 1

    if images_offset > 0:
        cur_image_offset = images_offset
        while cur_image_offset < chars_offset:
            rgba5551 = bm_pto_rgba(DataView(data, cur_image_offset, char_pixels), palette5551, 8, 16)
            rgba32 = rgba5551to_rgba32(rgba5551, config["w"], config["h"])
            pack["images"].append(rgba32)
            cur_image_offset += char_pixels

    # Intensity palette.
    fake_palette = [0]
    for i in range(1, 16):
        fake_palette.append(int(0xFF * ((i + 1) / 16)))

    half = char_pixels // 2
    cur_char_offset = chars_offset
    while cur_char_offset < len(data):
        rgba32 = bm_pto_rgba(DataView(data, cur_char_offset, half), fake_palette, 4, 32)
        pack["chars"].append(rgba32)
        cur_char_offset += half

    return pack
