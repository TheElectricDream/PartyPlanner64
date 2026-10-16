"""Converts an unpacked MTNX into keyframe tracks (replaces MtnxToThreeJs.ts).

mtnx_to_animation returns what static/js/lib/model3d.js's buildAnimation
turns into the THREE.AnimationClip MtnxToThreeJs made:

    {"name": "MTNX", "duration": seconds,
     "tracks": [{"name": "0x0A.position[x]", "type": "vector",
                 "times": [seconds, ...], "values": [value, ...]}, ...]}

Track names address the scene nodes named by form_to_scene (the global
index of the OBJ1 object, in hex).
"""

import logging

from ..utils.debug import hexstr
from ..utils.number import degrees_to_radians
from .mtnx import MTNX, MTNXDimension, MTNXTrackType

logger = logging.getLogger("partyplanner64")


class MtnxToAnimation:
    def __init__(self, form):
        self.form = form

    def create_clip(self, mtnx):
        tracks = self._create_tracks(mtnx)
        duration = self._frames_to_seconds(mtnx["total_frames"])
        return {"name": "MTNX", "duration": duration, "tracks": tracks}

    def _create_tracks(self, mtnx):
        tracks = []
        for track in mtnx["tracks"]:
            created = self._create_track(track)
            if created:
                tracks.append(created)
        return tracks

    def _create_track(self, track):
        if track["type"] == MTNXTrackType.Transform:
            prop, convert = "position", None
        elif track["type"] == MTNXTrackType.Rotation:
            prop, convert = "rotation", degrees_to_radians
        elif track["type"] == MTNXTrackType.Scale:
            prop, convert = "scale", None
        else:
            logger.warning("Unsupported track type %s", hexstr(track["type"]))
            return None

        node_name = self._get_obj_name_from_index(track["obj_index"])
        dimension = self._get_dimension_property(track["dimension"])
        values = []
        for keyframe in track["keyframes"].values():
            value = keyframe["value1"]
            values.append(convert(value) if convert else value)
        return {
            "name": "%s.%s[%s]" % (node_name, prop, dimension),
            "type": "vector",
            "times": [self._frames_to_seconds(int(frame)) for frame in track["keyframes"]],
            "values": values,
        }

    @staticmethod
    def _get_dimension_property(dimension):
        if dimension == MTNXDimension.X:
            return "x"
        if dimension == MTNXDimension.Y:
            return "y"
        if dimension == MTNXDimension.Z:
            return "z"
        raise ValueError("Unknown dimension %s" % hexstr(dimension))

    def _get_obj_name_from_index(self, index):
        cur3d_index = -1
        for obj in self.form["OBJ1"][0]["parsed"]["objects"]:
            if obj["obj_type"] == 0x3D:
                cur3d_index += 1
                if cur3d_index == index:
                    return hexstr(obj["global_index"])

        logger.warning("Couldn't find associated object %s for track", index)
        return hexstr(index)  # Probably wrong

    @staticmethod
    def _frames_to_seconds(frames):
        return frames / 60


def mtnx_to_animation(mtnx, form):
    """Return the animation clip description of an unpacked MTNX (or MTNX bytes) for a FORM."""
    if not isinstance(mtnx, dict):
        mtnx = MTNX.unpack(mtnx)
        if mtnx is None:
            raise ValueError("Not an MTNX file")
    if not isinstance(form, dict):
        from .form import FORM
        form = FORM.unpack(form)
    return MtnxToAnimation(form).create_clip(mtnx)
