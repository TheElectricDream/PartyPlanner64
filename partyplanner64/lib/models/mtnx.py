"""MTNX: animation file handling (port of models/MTNX.ts).

MTNX.unpack returns {"total_frames", "tracks"}; a track is a dict (type,
dimension, mystery1..4, total_frames, obj_index, keyframe_count, d,
keyframes), keyframes mapping frame number -> {"value1", "value2", "value3"}
(in ascending frame order, as JavaScript iterated the integer keys).
"""

from enum import IntEnum

from ..utils.dataview import DataView


class MTNXDimension(IntEnum):
    X = 0x45
    Y = 0x46
    Z = 0x47


class MTNXTrackType(IntEnum):
    Transform = 0x17
    Rotation = 0x4C
    Scale = 0x1B


class MTNX:
    @staticmethod
    def is_mtnx(view_or_buffer):
        if view_or_buffer is None:
            return False
        if isinstance(view_or_buffer, memoryview):
            view_or_buffer = bytes(view_or_buffer)
        view = view_or_buffer if isinstance(view_or_buffer, DataView) else DataView(view_or_buffer)
        if view.byte_length < 4:
            return False
        return view.get_uint32(0) == 0x4D544E58  # "MTNX"

    @staticmethod
    def unpack(mtnx_view):
        if isinstance(mtnx_view, memoryview):
            mtnx_view = bytearray(mtnx_view)
        if not isinstance(mtnx_view, DataView):
            mtnx_view = DataView(mtnx_view)

        if not MTNX.is_mtnx(mtnx_view):
            return None

        mtnx_obj = {
            "total_frames": mtnx_view.get_uint16(0xA),
            "tracks": [],
        }

        total_tracks = mtnx_view.get_uint16(0x8)
        ds_offset = mtnx_view.get_uint32(0xC)
        keyframes_offset = mtnx_view.get_uint32(0x10)
        data_offset = mtnx_view.get_uint32(0x14)

        ds_view = DataView(mtnx_view.buffer, mtnx_view.byte_offset + ds_offset)
        keyframes_view = DataView(mtnx_view.buffer, mtnx_view.byte_offset + keyframes_offset)
        data_view = DataView(mtnx_view.buffer, mtnx_view.byte_offset + data_offset)

        for i in range(total_tracks):
            track_offset = mtnx_view.get_uint32(0x18 + i * 4)
            track_view = DataView(mtnx_view.buffer, mtnx_view.byte_offset + track_offset)

            mtnx_obj["tracks"].append(
                MTNX.parse_track(track_view, i, ds_view, keyframes_view, data_view))

        return mtnx_obj

    @staticmethod
    def parse_track(track_view, track_index, ds_view, keyframes_view, data_view):
        track_obj = {
            "type": track_view.get_uint8(0),
            "dimension": track_view.get_uint8(1),
            "mystery1": track_view.get_uint8(2),
            "mystery2": track_view.get_uint8(3),
            "mystery3": track_view.get_uint16(4),
            "total_frames": track_view.get_uint16(6),
            "mystery4": track_view.get_uint8(8),
            "obj_index": track_view.get_uint8(9),  # Not global!
            "keyframe_count": track_view.get_uint16(0xE),
        }

        track_obj["d"] = ds_view.get_uint8(track_index)  # TODO ?

        keyframes_index = track_view.get_uint16(0xA)
        data_index = track_view.get_uint16(0xC)

        keyframes = {}
        for k in range(track_obj["keyframe_count"]):
            keyframe = keyframes_view.get_uint16(keyframes_index * 2 + k * 2)
            keyframes[keyframe] = MTNX.parse_data(data_view, data_index, k)
        # JavaScript objects iterate integer keys in ascending order.
        track_obj["keyframes"] = dict(sorted(keyframes.items()))

        return track_obj

    @staticmethod
    def parse_data(data_view, data_index, keyframe_index):
        SIZEOF_FRAME_DATA = 3 * 4
        base = data_index * 4 + keyframe_index * SIZEOF_FRAME_DATA
        return {
            "value1": data_view.get_float32(base),
            "value2": data_view.get_float32(base + 4),
            "value3": data_view.get_float32(base + 8),
        }
