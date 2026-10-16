"""ImgPack, a container of images (port of utils/img/ImgPack.ts).

Aside from raw RGB5551, there is also a format with a header followed by
one or more images sequentially. May be raw or bitmap with palette.

All offsets are SEEK_START.

struct ImgPack {
  u32 entry_offset; // Offset to the first ImgPack_Entry
  u32 unknown_offset; // This segment only has contents with multiple images packed
  u32 images_offset; // Offset to the start of the first image data (redundant)
  u32 pallete_offset; // If no palette, just points to end of file
  u16 image_count;
  u16 unknown; // Palette presence bool?
  u16 total_width; // Sum of widths of all images
  u16 total_height; // Sum of heights of all images
  u8 unknown; // Value is 80 in at least one instance, so this isn't the upper half of a u16
  u8 pixel_bit_count; // Number of bits per pixel (not factoring in size of palette colors)
  u16 unknown;
  u32 / u16*2 unknown; // Zeroes to fill to reach entry_offset?

  // Follows by contiguous ImgPack_Entry[image_count]
  // Then, some unknown data if unknown_offset is in play.
  // Then, the raw image data, and then the pallete.
  // Technically, the first few offsets could change this order.
}

struct ImgPack_Entry {
  u32 img_start_offset;
  u16 width;
  u16 height;
  s16 origin_x;
  s16 origin_y;
}

IImgInfo is a dict: {"width", "height", "src" (RGBA bytes: a bytearray, or
an ImageData's data), "bpp", and "_bmp_data" (set by to_pack)}.
"""

from ..arrays import _region, byte_length, copy_range
from ..dataview import DataView
from .bmp import bm_pto_rgba, bm_pfrom_rgba
from .grayscale import grayscale_to_rgba32
from .rgba5551 import rgba5551to_rgba32, rgba5551from_rgba32


def img_info_src_to_array_buffer(img_info_src):
    """Return the bytes of an image info's src (a copy for views)."""
    if isinstance(img_info_src, (bytearray, bytes)):
        return img_info_src
    buf, start, length = _region(img_info_src)
    return bytearray(buf[start:start + length])


def img_info_src_to_data_view(img_info_src):
    """Return a DataView over an image info's src."""
    if isinstance(img_info_src, DataView):
        return img_info_src
    if isinstance(img_info_src, memoryview):
        img_info_src = bytearray(img_info_src)
    return DataView(img_info_src)


def from_pack(buffer):
    """Rips each image from a ImgPack and returns a list of image infos (RGBA32)."""
    buf, start, length = _region(buffer)
    data = bytes(buf[start:start + length])
    in_view = DataView(data)
    entry_offset = in_view.get_uint32(0)
    palette_offset = in_view.get_uint32(12)
    image_count = in_view.get_uint16(16)
    bit_count = in_view.get_uint8(25)

    # Pull out the pallete values, if applicable.
    has_palette = palette_offset != length
    palette = []
    if has_palette:
        if palette_offset > length or (length - palette_offset) % 2:
            # The TypeScript reads past the end here.
            raise IndexError("Offset is outside the bounds of the DataView")
        palette = [int.from_bytes(data[i:i + 2], "big") for i in range(palette_offset, length, 2)]

    # Loop and convert to output images.
    output = []
    cur_entry_offset = entry_offset
    if cur_entry_offset > length:
        raise IndexError("Start offset is outside the bounds of the buffer")
    for _ in range(image_count):
        cur_entry_view = DataView(data, cur_entry_offset)
        img_offset = cur_entry_view.get_uint32(0)
        img_width = cur_entry_view.get_uint16(4)
        img_height = cur_entry_view.get_uint16(6)
        if bit_count >= 8:
            img_byte_count = (bit_count * img_width * img_height) / 8
        else:
            img_byte_count = (img_width * img_height) / (8 / bit_count) if bit_count else 0
        end = int(img_offset + img_byte_count)
        raw_img_buffer = bytearray(data[img_offset:end])

        if has_palette:
            raw_img_buffer = bm_pto_rgba(raw_img_buffer, palette, bit_count, 16)
        img_info = {"width": img_width, "height": img_height}
        if bit_count == 32:
            img_info["src"] = raw_img_buffer
        elif bit_count == 16 or has_palette:
            img_info["src"] = rgba5551to_rgba32(raw_img_buffer, img_width, img_height)
        elif bit_count in (4, 8):
            img_info["src"] = grayscale_to_rgba32(raw_img_buffer, img_width, img_height, bit_count)
        output.append(img_info)

        cur_entry_offset += 12  # sizeof(ImgPack_Entry)
        if cur_entry_offset > length:
            raise IndexError("Start offset is outside the bounds of the buffer")

    return output


def _uint(value, bits):
    """ToUint16/ToUint32 of a JS number (truncates fractions, wraps)."""
    return int(value) & ((1 << bits) - 1)


def to_pack(img_info_arr, out_bpp, bmp_bpp, old_pack=None):
    """Creates a new ImgPack from a list of image infos.

    old_pack: the old pack being replaced, used for grabbing mystery values.
    """
    new_pack_size = get_byte_length(img_info_arr, out_bpp)

    bmp_data = palette = None
    if bmp_bpp:
        # FIXME: There could be multiple images and the palette needs to be comprehensive.
        bmp_data, palette = bm_pfrom_rgba(img_info_arr[0]["src"], img_info_arr[0].get("bpp"), 8)
        img_info_arr[0]["_bmp_data"] = bmp_data
        new_pack_size += len(palette["colors"]) * (out_bpp / bmp_bpp)
        new_pack_size -= byte_length(img_info_arr[0]["src"]) - len(bmp_data)

    new_pack = bytearray(int(new_pack_size))
    new_view = DataView(new_pack)

    old_view = DataView(old_pack) if old_pack is not None else None

    # Write initial header offsets.
    new_view.set_uint32(0, 0x00000020)  # First entry offset.
    new_view.set_uint32(4, 0x0000002C)  # FIXME: Unknown offset.
    new_view.set_uint32(8, 0x0000002C)  # First image offset.
    if palette:
        new_view.set_uint32(0xC, _uint(new_pack_size - len(palette["colors"]) * (out_bpp / bmp_bpp), 32))  # Palette offset
    else:
        new_view.set_uint32(0xC, _uint(new_pack_size, 32))  # Palette offset
    new_view.set_uint16(0x10, len(img_info_arr))  # Image count
    new_view.set_uint16(0x12, 0)  # FIXME: Palette presence?

    width_sum = 0
    height_sum = 0
    for img_info in img_info_arr:
        width_sum += img_info["width"]
        height_sum += img_info["height"]
    new_view.set_uint16(0x14, _uint(width_sum, 16))  # Total width
    new_view.set_uint16(0x16, _uint(height_sum, 16))  # Total height

    if old_view:
        new_view.set_uint8(0x18, old_view.get_uint8(0x18))
    else:
        new_view.set_uint8(0x18, 0)

    new_view.set_uint8(0x19, bmp_bpp or out_bpp)  # Bpp of the data in the ImgPack.

    if palette:
        new_view.set_uint8(0x1A, len(palette["colors"]))
        palette_offset = int(new_pack_size - len(palette["colors"]) * (out_bpp / bmp_bpp))
        for i, color in enumerate(palette["colors"]):
            new_view.set_uint16(palette_offset + i * 2, color)  # FIXME: 16bit hardcoded

    # Followed by zeroes...

    cur_offset = 0x20
    for img_info in img_info_arr:
        cur_offset = _write_entry(new_view, cur_offset, img_info, out_bpp, old_view)

    return new_pack


def get_byte_length(img_info_arr, out_bpp):
    length = 0x20  # Fixed-size header
    for img_info in img_info_arr:
        length += 0xC
        if img_info.get("bpp") == out_bpp:
            length += byte_length(img_info["src"])
        elif img_info.get("bpp") == 32 and out_bpp == 16:
            length += byte_length(img_info["src"]) // 2
    return length


def _write_entry(new_view, cur_offset, img_info, out_bpp, old_view=None):
    new_view.set_uint32(cur_offset, cur_offset + 0xC)  # Absolute offset of image data.
    cur_offset += 4
    new_view.set_uint16(cur_offset, _uint(img_info["width"], 16))
    cur_offset += 2
    new_view.set_uint16(cur_offset, _uint(img_info["height"], 16))
    if old_view:
        cur_offset += 2
        new_view.set_uint32(cur_offset, old_view.get_uint32(cur_offset))  # Assumes we can directly map mystery values.
        cur_offset += 4
    else:
        # Is it really just the actual h x w in the buffer?
        cur_offset += 2
        new_view.set_uint16(cur_offset, _uint(img_info["width"] / 2, 16))  # FIXME
        cur_offset += 2
        new_view.set_uint16(cur_offset, _uint(img_info["height"] / 2, 16))
        cur_offset += 2

    if img_info.get("_bmp_data") is not None:
        src = img_info["_bmp_data"]
    elif img_info.get("bpp") == out_bpp:
        src = img_info["src"]
    elif img_info.get("bpp") == 32 and out_bpp == 16:
        src = rgba5551from_rgba32(img_info["src"], img_info["width"], img_info["height"])
    else:
        raise ValueError("Cannot create ImgPack (yet) with inBpp=%s and outBpp=%s."
                         % (img_info.get("bpp"), out_bpp))

    src_length = byte_length(src)
    copy_range(new_view, src, cur_offset, 0, src_length)
    return cur_offset + src_length


