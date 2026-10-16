"""FORM files: models and their textures (port of models/FORM.ts).

FORM.unpack returns a dict: "entries" (the types in file order) and, per
type ("OBJ1", "VTX1", "FAC1", "BMP1", ...), a list of entries
{"raw": bytearray, "parsed": ...}. Parsed values are dicts with snake_case
keys (pos_x, face_index, vtx_entries, global_index, ...).
"""

import logging

from ..utils.dataview import DataView
from ..utils.debug import hexstr

logger = logging.getLogger("partyplanner64")

# IFormObjType
FORM_OBJ_TYPES = ("FORM", "HBINMODE", "OBJ1", "COL1", "MAT1", "ATR1", "VTX1", "FAC1", "MTN1",
                  "BMP1", "PAL1", "SKL1", "STRG", "MAP1")


def _from_u32(u32):
    return "".join(chr((u32 >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def _view(view_or_buffer):
    if isinstance(view_or_buffer, DataView):
        return view_or_buffer
    if isinstance(view_or_buffer, memoryview):
        view_or_buffer = bytearray(view_or_buffer)
    return DataView(view_or_buffer)


class FORM:
    """Extracts a FORM file into a usable format."""

    @staticmethod
    def unpack(form_view):
        form_view = _view(form_view)

        if not FORM.is_form(form_view):
            return None

        form_obj = {"entries": []}

        cur_offset = 8
        while cur_offset < form_view.byte_length - 2:
            # Roughly-ish the end
            type_ = _from_u32(form_view.get_uint32(cur_offset))
            if type_ == "HBIN":
                cur_offset += 4
                type_ += _from_u32(form_view.get_uint32(cur_offset))  # "MODE"

            form_obj["entries"].append(type_)

            cur_offset += 4
            length = form_view.get_uint32(cur_offset)
            cur_offset += 4

            # (The TypeScript sliced the underlying buffer, ignoring the view's offset.)
            start = form_view.byte_offset + cur_offset
            entry = {"raw": bytearray(form_view.buffer[start:start + length])}

            parsed = FORM.parse_type(type_, entry["raw"])
            if parsed is not None:
                entry["parsed"] = parsed

            form_obj.setdefault(type_, []).append(entry)

            cur_offset += length + (length % 2)

        # With all BMPs and PALs parsed, now we can decode the BMPs.
        if form_obj.get("BMP1"):
            for bmp_entry in form_obj["BMP1"]:
                bmp_entry["parsed"] = FORM.parse_bmp(bmp_entry["raw"], form_obj.get("PAL1"))

        return form_obj

    @staticmethod
    def pack(form_obj):
        form_buffer = bytearray(FORM.get_byte_length(form_obj))
        form_view = DataView(form_buffer)

        form_view.set_uint32(0, 0x464F524D)  # "FORM"
        form_view.set_uint32(4, len(form_buffer) - 8)  # Don't count the "FORM____" at the top.

        entry_write_state = {}
        cur_index = 8
        for entry_type in form_obj["entries"]:
            entry_num = entry_write_state.get(entry_type, 0)
            entry_write_state[entry_type] = entry_num + 1

            # Write the type name.
            for ch in entry_type:
                form_view.set_uint8(cur_index, ord(ch))
                cur_index += 1

            entry = form_obj[entry_type][entry_num]

            # Write the entry length.
            entry_size = len(entry["raw"])
            form_view.set_uint32(cur_index, entry_size)
            cur_index += 4

            # Copy in the actual data.
            form_buffer[cur_index:cur_index + entry_size] = entry["raw"]
            cur_index += entry_size + (entry_size % 2)

        return form_buffer

    @staticmethod
    def is_form(view_or_buffer):
        if view_or_buffer is None:
            return False
        view = _view(view_or_buffer)
        if view.byte_length < 4:
            return False
        return view.get_uint32(0) == 0x464F524D  # "FORM"

    @staticmethod
    def get_byte_length(form_obj):
        byte_len = 0
        for type_, entries in form_obj.items():
            if type_ == "entries":
                continue
            for entry in entries:
                raw_len = len(entry["raw"])
                # The raw data + rounded up to 16-bit boundary + the TYPE text + entry length value.
                byte_len += raw_len + (raw_len % 2) + len(type_) + 4
        return byte_len + 8  # Add the "FORM____" at the beginning.

    @staticmethod
    def parse_type(type_, raw):
        parser = {
            "HBINMODE": FORM.parse_hbinmode,
            "OBJ1": FORM.parse_obj1,
            "COL1": FORM.parse_col1,
            "MAT1": FORM.parse_mat1,
            "ATR1": FORM.parse_atr1,
            "VTX1": FORM.parse_vtx1,
            "FAC1": FORM.parse_fac1,
            "PAL1": FORM.parse_pal1,
            "SKL1": FORM.parse_skl1,
            "STRG": FORM.parse_strg,
        }.get(type_)
        if parser:
            return parser(raw)
        return None

    @staticmethod
    def parse_hbinmode(raw):
        raw_view = DataView(raw)
        result = {
            "e": raw_view.get_uint8(0x14),
            "f": raw_view.get_uint8(0x15),
            "g": raw_view.get_uint8(0x16),
        }

        if result["e"] != 0x45 or result["f"] != 0x46 or result["g"] != 0x47:
            logger.warning("HBINMODE unexpected EFG => %s", result)  # Corresponds to ZYX rotation?

        return result

    @staticmethod
    def parse_obj1(raw):
        raw_view = DataView(raw)
        result = {
            "objects": [],
            "mystery1": raw_view.get_uint16(2),
        }

        obj_count = raw_view.get_uint16(0)
        object_offset = 4
        for _ in range(obj_count):
            obj_size = raw_view.get_uint16(object_offset)
            obj_type = raw_view.get_uint8(object_offset + 2)
            global_index = raw_view.get_uint16(object_offset + 3)

            object_offset += 5

            if obj_type == 0x3D:
                obj = {"children": []}
                sub_obj_count = raw_view.get_uint16(object_offset)
                for j in range(sub_obj_count):
                    obj["children"].append(raw_view.get_uint16(object_offset + 2 + 2 * j))
                obj.update(FORM._parse_obj1_transforms(raw_view, object_offset + 2 + 2 * sub_obj_count))
            elif obj_type == 0x3A:
                obj = {
                    "mystery1": raw_view.get_uint8(object_offset),
                    "face_index": raw_view.get_uint16(object_offset + 1),
                    "face_count": raw_view.get_uint16(object_offset + 3),
                }
                obj.update(FORM._parse_obj1_transforms(raw_view, object_offset + 5))
            elif obj_type == 0x10:  # Points to skeleton entry // 9/11 mp1
                obj = {"skeleton_global_index": raw_view.get_uint16(object_offset)}
                obj.update(FORM._parse_obj1_transforms(raw_view, object_offset + 2))
            elif obj_type == 0x3B:
                # TODO mp3 25/2
                obj = {}
                logger.warning("Object type 0x3B")
            elif obj_type == 0x3E:
                # TODO
                obj = {}
            elif obj_type == 0x61:
                # TODO this is common, don't know what it is, just has transform
                obj = {}
                obj.update(FORM._parse_obj1_transforms(raw_view, object_offset))
            elif obj_type == 0x5D:
                # TODO mp3 13/0
                # Refers to objects of type 0x61
                obj = {}
                logger.warning("Object type 0x5D")
            else:
                logger.warning("Unrecognized object type %s", hexstr(obj_type))
                obj = {}

            obj["obj_type"] = obj_type
            obj["global_index"] = global_index

            result["objects"].append(obj)

            object_offset += obj_size - 3  # -3 because +5 above included 3 from objSize

        return result

    @staticmethod
    def _parse_obj1_transforms(raw_view, offset):
        return {
            "pos_x": raw_view.get_float32(offset),
            "pos_y": raw_view.get_float32(offset + 4),
            "pos_z": raw_view.get_float32(offset + 8),
            "rot_x": raw_view.get_float32(offset + 12),
            "rot_y": raw_view.get_float32(offset + 16),
            "rot_z": raw_view.get_float32(offset + 20),
            "scale_x": raw_view.get_float32(offset + 24),
            "scale_y": raw_view.get_float32(offset + 28),
            "scale_z": raw_view.get_float32(offset + 32),
        }

    @staticmethod
    def parse_col1(raw):
        raw_view = DataView(raw)
        colors = []
        color_count = raw_view.get_uint16(0)
        color_offset = 2
        for _ in range(color_count):
            colors.append(raw_view.get_uint32(color_offset))
            color_offset += 4
        return colors

    @staticmethod
    def parse_mat1(raw):
        raw_view = DataView(raw)
        result = {"materials": []}
        material_count = raw_view.get_uint16(0)
        material_offset = 2
        for _ in range(material_count):
            result["materials"].append({
                "mystery1": raw_view.get_uint16(material_offset),
                "color_index": raw_view.get_uint16(material_offset + 2),
                "mystery3": raw_view.get_uint16(material_offset + 4),
                "mystery4": raw_view.get_float32(material_offset + 6),
                "mystery5": raw_view.get_uint16(material_offset + 10),
            })
            material_offset += 12
        return result

    @staticmethod
    def parse_atr1(raw):
        raw_view = DataView(raw)
        result = {"atrs": []}
        atr_count = raw_view.get_uint16(0)
        atr_offset = 2
        for _ in range(atr_count):
            atr = {
                "size": raw_view.get_uint16(atr_offset),
                # 2A
                # FF FF
                "x_behavior": raw_view.get_uint8(atr_offset + 0x5),
                "y_behavior": raw_view.get_uint8(atr_offset + 0x6),
                # 2F 2F 01
                "bmp_global_index": raw_view.get_uint16(atr_offset + 0xA),
            }
            result["atrs"].append(atr)

            atr_offset += atr["size"] + 2
        return result

    @staticmethod
    def parse_vtx1(raw):
        raw_view = DataView(raw)
        result = {
            "vertices": [],
            "scale": raw_view.get_float32(4),
        }
        vertex_count = raw_view.get_uint16(0)
        vertex_offset = 8
        for _ in range(vertex_count):
            result["vertices"].append({
                "x": raw_view.get_int16(vertex_offset),
                "y": raw_view.get_int16(vertex_offset + 2),
                "z": raw_view.get_int16(vertex_offset + 4),
                "normal_x": raw_view.get_int8(vertex_offset + 6),
                "normal_y": raw_view.get_int8(vertex_offset + 7),
                "normal_z": raw_view.get_int8(vertex_offset + 8),
            })
            vertex_offset += 9
        return result

    @staticmethod
    def parse_fac1(raw):
        raw_view = DataView(raw)
        result = {"faces": []}
        face_count = raw_view.get_uint16(0)
        face_offset = 8
        for _ in range(face_count):
            face_type = raw_view.get_uint8(face_offset)

            if face_type != 0x35 and face_type != 0x16 and face_type != 0x30:
                # 0x30 in mainfs 9/81 mp1
                raise ValueError("Unrecognized faceType in FAC1: %s" % hexstr(face_type))

            face = {"vtx_entries": []}
            result["faces"].append(face)

            face_offset += 1  # Start after face_type

            if face_type == 0x30:
                logger.warning("Unsupported face type 0x30")
                face_offset += 6  # TODO: What is 0x30 type? VTX num VTX?
            else:
                vtx_entry_count = 4 if face_type == 0x35 else 3
                for _j in range(vtx_entry_count):
                    face["vtx_entries"].append({
                        "vertex_index": raw_view.get_uint16(face_offset),
                        "material_index": raw_view.get_int16(face_offset + 2),
                        "u": raw_view.get_float32(face_offset + 4),
                        "v": raw_view.get_float32(face_offset + 8),
                    })
                    face_offset += 12  # sizeof(FAC1VtxEntry)

            face["material_index"] = raw_view.get_int16(face_offset)
            face["atr_index"] = raw_view.get_int16(face_offset + 2)
            face["mystery3"] = raw_view.get_uint8(face_offset + 4)  # 0x36

            # TODO 0x38 in mp2 31/5
            # mp3 81/2 flip x, 0x37 ?
            if face["mystery3"] != 0x36:
                logger.debug("Unsupported FAC1 mystery3 %s", hexstr(face["mystery3"]))

            face_offset += 5
        return result

    @staticmethod
    def parse_pal1(raw):
        raw_view = DataView(raw)
        result = {
            "colors": [],
            "bpp": 0,
            "global_index": raw_view.get_uint16(0),
        }
        color_count = raw_view.get_uint16(2)
        if color_count == 0:
            raise ValueError("FORM.parseType(PAL1): bpp: NaN")
        result["bpp"] = ((len(raw) - 4) // color_count) * 8
        color_offset = 4
        for _ in range(color_count):
            if result["bpp"] == 32:
                result["colors"].append(raw_view.get_uint32(color_offset))
            elif result["bpp"] == 16:
                result["colors"].append(raw_view.get_uint16(color_offset))
            elif result["bpp"] == 8:
                result["colors"].append(raw_view.get_uint8(color_offset))
            else:
                raise ValueError("FORM.parseType(PAL1): bpp: %s" % result["bpp"])

            color_offset += result["bpp"] // 8
        return result

    @staticmethod
    def parse_skl1(raw):
        raw_view = DataView(raw)

        skl_count = raw_view.get_uint8(2)
        result = {
            "global_index": raw_view.get_uint16(0),
            "skls": [],
        }

        skl_offset = 3
        for _ in range(skl_count):
            skl = {
                "mystery1": raw_view.get_uint8(skl_offset),
                "obj_global_index": raw_view.get_uint16(skl_offset + 1),
                "next_sibling_relative_index": raw_view.get_uint16(skl_offset + 0x33),
                "is_parent_node": raw_view.get_uint16(skl_offset + 0x35),
                "mystery2": raw_view.get_uint8(skl_offset + 0x36),
            }
            skl.update(FORM._parse_obj1_transforms(raw_view, skl_offset + 3))
            result["skls"].append(skl)
            skl_offset += 56  # sizeof(SKL1Entry)

        return result

    @staticmethod
    def parse_strg(raw):
        raw_view = DataView(raw)
        strings = []
        str_count = raw_view.get_uint16(0)
        str_offset = 2 + str_count
        for i in range(str_count):
            str_len = raw_view.get_uint8(2 + i)
            strings.append("".join(chr(raw_view.get_uint8(str_offset + j)) for j in range(str_len)))
            str_offset += str_len
        return strings

    @staticmethod
    def parse_bmp(raw, pal1):
        from ..utils.img.bmp import bm_pto_rgba
        from ..utils.img.rgba5551 import rgba5551to_rgba32

        raw_view = DataView(raw)
        format_ = raw_view.get_uint16(0x2)
        width = raw_view.get_uint16(0x05)
        height = raw_view.get_uint16(0x07)

        if format_ == 0x128 or format_ == 0x228:
            # Traditional bitmap format
            # 0x128 is just a bitmap
            # 0x228 starts out the same, but TODO it also has some sort of extra RGBA data appended.
            #   mp1 0/93, 0/94, 0/95, 46/2, 48/15, 54/5, 57/3
            if not pal1:
                raise ValueError("Palette needed for BMP format %s" % hexstr(format_))

            palette_global_index = raw_view.get_uint16(0x09)
            in_bmp_size = raw_view.get_uint16(0x0F)

            # Find associated palette by global index
            palette = None
            for pal in pal1:
                if pal["parsed"]["global_index"] == palette_global_index:
                    palette = pal["parsed"]
                    break
            if not palette:
                raise ValueError("Could not locate palette at global index %s" % palette_global_index)

            # Doesn't appear to indicate BPP, but we can calculate from size and dimens.
            pixels = width * height
            if pixels == 0 or in_bmp_size == 0:
                in_bpp = float("inf") if pixels == 0 and in_bmp_size else 0
            else:
                in_bpp = 8 / (pixels / in_bmp_size)
                if in_bpp == int(in_bpp):
                    in_bpp = int(in_bpp)
            out_bpp = palette["bpp"]
            in_bmp_data = DataView(raw, 0x11, in_bmp_size)

            return {
                "global_index": raw_view.get_uint16(0),
                "orig_format": format_,
                "palette_global_index": palette_global_index,
                "width": width,
                "height": height,
                "src": bm_pto_rgba(in_bmp_data, palette["colors"], in_bpp, out_bpp),
            }
        elif format_ == 0x127:
            # mp1 9/138
            # Just raw RGBA already
            bpp = raw_view.get_uint8(0x4)
            image_byte_length = raw_view.get_uint16(0xB)
            if bpp == 16:
                return {
                    "global_index": raw_view.get_uint16(0),
                    "orig_format": format_,
                    "width": width,
                    "height": height,
                    "src": rgba5551to_rgba32(bytearray(raw[0xD:0xD + image_byte_length]), width, height),
                }
            elif bpp == 32:
                return {
                    "global_index": raw_view.get_uint16(0),
                    "orig_format": format_,
                    "width": width,
                    "height": height,
                    "src": bytearray(raw[0xD:0xD + image_byte_length]),
                }
            else:
                logger.warning("BMP1 0x127 had unsupported bpp %s", bpp)
        elif format_ == 0x126:
            # 0x126 mp1 9/25
            # 24 bits per color
            # TODO: Are the bits right, or is there alpha?
            image_byte_length = raw_view.get_uint16(0xB)

            out_buffer = bytearray(width * height * 4)
            out_view = DataView(out_buffer)
            i = 0
            while i < image_byte_length / 3:
                in_byte1 = raw_view.get_uint8(0xD + i)
                in_byte2 = raw_view.get_uint8(0xD + i + 1)
                in_byte3 = raw_view.get_uint8(0xD + i + 2)
                rgba32 = (in_byte1 << 24) | (in_byte2 << 16) | (in_byte3 << 8) | 0xFF
                out_view.set_uint32(i * 4, rgba32)
                i += 1

            return {
                "global_index": raw_view.get_uint16(0),
                "orig_format": format_,
                "width": width,
                "height": height,
                "src": out_buffer,
            }
        elif format_ == 0x125:
            # Grayscale?
            # TODO: I don't think this is right? Some sort of shadow mask?
            image_byte_length = raw_view.get_uint16(0xB)

            out_buffer = bytearray(image_byte_length * 4)
            for i in range(image_byte_length):
                in_byte = raw_view.get_uint8(0xD + i)
                alpha = (in_byte & 0x0F) | ((in_byte & 0x0F) << 4)
                grayscale = (in_byte & 0xF0) | ((in_byte & 0xF0) >> 4)
                out_buffer[i * 4:i * 4 + 4] = bytes((grayscale, grayscale, grayscale, alpha))

            return {
                "global_index": raw_view.get_uint16(0),
                "orig_format": format_,
                "width": width,
                "height": height,
                "src": out_buffer,
            }
        elif format_ == 0x124:
            # 0x124 mp3 11/51
            # Grayscale?
            # TODO: I don't think this is right? Some sort of shadow mask?
            image_byte_length = raw_view.get_uint16(0xB)

            out_buffer = bytearray(image_byte_length * 8)
            out_loc = 0
            for i in range(image_byte_length):
                in_byte = raw_view.get_uint8(0xD + i)

                out1byte = (in_byte & 0xF0) >> 4
                out1byte |= in_byte & 0xF0
                out_buffer[out_loc:out_loc + 4] = bytes((out1byte, out1byte, out1byte, 0xFF))
                out_loc += 4

                out2byte = in_byte & 0x0F
                out2byte |= out2byte << 4
                out_buffer[out_loc:out_loc + 4] = bytes((out2byte, out2byte, out2byte, 0xFF))
                out_loc += 4

            return {
                "global_index": raw_view.get_uint16(0),
                "orig_format": format_,
                "width": width,
                "height": height,
                "src": out_buffer,
            }

        # TODO: Other formats

        logger.warning("Could not parse BMP format %s", hexstr(format_))
        return {
            "global_index": raw_view.get_uint16(0),
            "orig_format": format_,
            "width": width,
            "height": height,
            "src": bytearray(width * height * 4),
        }

    @staticmethod
    def replace_bmp(form_obj, bmp_index, buffer, palette):
        """Write a new bitmap (same properties) and palette over BMP1/PAL1 entry bmp_index.

        Args:
            palette: A dict with "colors" (as BMPfromRGBA gives).
        """
        # FIXME?: For now, this assumes that the new BMP has the same properties basically.

        # Just write over the bitmap data directly.
        raw = form_obj["BMP1"][bmp_index]["raw"]
        buffer = bytes(buffer.bytes() if isinstance(buffer, DataView) else buffer)
        if 0x11 + len(buffer) > len(raw):
            raise IndexError("Offset is outside the bounds of the DataView")
        raw[0x11:0x11 + len(buffer)] = buffer

        # Write the palette, which needs some care.
        form_obj["PAL1"][bmp_index]["parsed"] = palette
        old_pal_global_index = DataView(form_obj["PAL1"][bmp_index]["raw"]).get_uint16(0)
        new_raw = form_obj["PAL1"][bmp_index]["raw"] = bytearray(4 + len(palette["colors"]) * 4)
        new_palette_view = DataView(new_raw)
        new_palette_view.set_uint16(0, old_pal_global_index)
        new_palette_view.set_uint16(2, len(palette["colors"]))
        cur_out_offset = 4
        for color in palette["colors"]:
            new_palette_view.set_uint32(cur_out_offset, color)
            cur_out_offset += 4

        # TODO: This was another implementation: write raw RGBA with type 0x127.
        # But the board select wouldn't show up when I tried this.

    @staticmethod
    def get_by_global_index(form, section, global_index):
        """Retrieves a value (or possibly multiple values) by global index."""
        if not form.get(section):
            return None

        values = []
        for entry in form[section]:
            parsed_value = entry.get("parsed")
            if parsed_value is None:
                raise ValueError("No parsed value for %s" % section)

            if isinstance(parsed_value, dict) and "global_index" in parsed_value:
                if parsed_value["global_index"] == global_index:
                    values.append(parsed_value)
            else:
                arr_to_search = parsed_value
                if section == "OBJ1":
                    arr_to_search = parsed_value["objects"]

                for val in arr_to_search:
                    if not isinstance(val, dict) or "global_index" not in val:
                        raise ValueError("globalIndex is not a property of the searched %s array "
                                         "in getByGlobalIndex" % section)
                    if val["global_index"] == global_index:
                        values.append(val)

        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return values

    @staticmethod
    def get_objects_by_type(form, type_):
        objs = form["OBJ1"][0]["parsed"]["objects"]
        return [obj for obj in objs if obj["obj_type"] == type_]
