"""Test-playing one event: a small board built around it, for a test ROM.

The board is a start space, an invisible space after it, and a loop of
LOOP_SPACES spaces back to the invisible space:

    start (0) -> invisible (1) -> loop (2) -> ... -> loop (11) -> invisible (1)

With "Land On", every loop space runs the event, so whatever the dice show (1 to
10 in Mario Party 3) the player lands on one; with "Walk Over", the invisible
space runs it, and every first move passes it (as the original boards' shops
and Boos are run). The indices are the same either way, so Space parameters
can point at any of them.

    settings = eventtest.normalize_settings(event, {"activation": 3})
    board = eventtest.build_board(new_board, event, settings)

new_board is a new board of the game (editor.boards._make_default_board), whose
background and images the test board keeps.
"""

import copy
import math

from ..types import EventActivationType, EventParameterType, Game, Space
from . import PlaytestError

LOOP_SPACES = 10          # the most a die shows, so every roll ends on the loop
START_INDEX = 0
INVISIBLE_INDEX = 1
FIRST_LOOP_INDEX = 2

ACTIVATIONS = [
    {"id": int(EventActivationType.LANDON), "name": "Land On"},
    {"id": int(EventActivationType.WALKOVER), "name": "Walk Over"},
]
_ACTIVATION_IDS = [a["id"] for a in ACTIVATIONS]

# The spaces a Land On event can be put on.
SPACE_TYPES = [
    {"id": int(Space.HAPPENING), "name": "Happening"},
    {"id": int(Space.BLUE), "name": "Blue"},
    {"id": int(Space.RED), "name": "Red"},
]
_SPACE_TYPE_IDS = [s["id"] for s in SPACE_TYPES]


def _plain(value):
    return getattr(value, "value", value)


def supports_game(event, game):
    """Whether the event's GAMES list has the game (a Game, or its ID)."""
    return _plain(game) in [_plain(g) for g in (event.supported_games or [])]


def spaces():
    """The spaces of the test board a Space parameter can name: [{index, name}]."""
    out = [{"index": START_INDEX, "name": "Start space"},
           {"index": INVISIBLE_INDEX, "name": "Invisible space (after the start)"}]
    for n in range(LOOP_SPACES):
        out.append({"index": FIRST_LOOP_INDEX + n, "name": "Loop space %d" % (n + 1)})
    return out


_SPACE_INDICES = [s["index"] for s in spaces()]


def _parameters(event):
    return [{"name": p["name"], "type": _plain(p["type"])} for p in (event.parameters or [])]


def _default_value(param_type):
    if param_type == EventParameterType.Boolean.value:
        return False
    if param_type == EventParameterType.PositiveNumber.value:
        return 1
    if param_type == EventParameterType.Space.value:
        return FIRST_LOOP_INDEX
    if param_type in (EventParameterType.SpaceArray.value, EventParameterType.NumberArray.value):
        return []
    return 0


def default_settings(event):
    """{activation, spaceType, parameterValues}: Land On, on Happening spaces."""
    return {
        "activation": int(EventActivationType.LANDON),
        "spaceType": int(Space.HAPPENING),
        "parameterValues": {p["name"]: _default_value(p["type"]) for p in _parameters(event)},
    }


def _whole(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value == int(value)


def _check_value(name, param_type, value):
    """The value, checked for its type; raises PlaytestError."""
    if param_type == EventParameterType.Boolean.value:
        if not isinstance(value, bool):
            raise PlaytestError("%s is true or false." % name)
        return value
    if param_type in (EventParameterType.Number.value, EventParameterType.PositiveNumber.value):
        if not _whole(value):
            raise PlaytestError("%s must be a whole number." % name)
        if param_type == EventParameterType.PositiveNumber.value and value <= 0:
            raise PlaytestError("%s must be a positive number." % name)
        return int(value)
    if param_type == EventParameterType.Space.value:
        if not _whole(value) or int(value) not in _SPACE_INDICES:
            raise PlaytestError("%s must be one of the test board's spaces." % name)
        return int(value)
    if param_type == EventParameterType.SpaceArray.value:
        if not isinstance(value, (list, tuple)) or \
                not all(_whole(v) and int(v) in _SPACE_INDICES for v in value):
            raise PlaytestError("%s must be a list of the test board's spaces." % name)
        return [int(v) for v in value]
    if param_type == EventParameterType.NumberArray.value:
        if not isinstance(value, (list, tuple)) or not all(_whole(v) for v in value):
            raise PlaytestError("%s must be a list of whole numbers." % name)
        return [int(v) for v in value]
    return value


def normalize_settings(event, settings=None, lenient=False):
    """Check an event test's settings and fill in what is missing; returns a new dict.

    settings (all optional):
        activation: 3 (Land On) or 1 (Walk Over).
        spaceType: the type of the loop's spaces for Land On (Happening, Blue, Red).
        parameterValues: {name: value} for the event's PARAMs. Space parameters are
            indices of the test board's spaces (see spaces()).
    Values for parameters the event does not have are dropped. Raises PlaytestError
    for bad values; with lenient, those are replaced by the defaults instead (for
    settings saved before the event's code changed).
    """
    out = default_settings(event)
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        if lenient:
            return out
        raise PlaytestError("The event test settings are an object.")

    def fail(message):
        if not lenient:
            raise PlaytestError(message)

    activation = settings.get("activation")
    if activation is not None:
        if activation in _ACTIVATION_IDS and not isinstance(activation, bool):
            out["activation"] = int(activation)
        else:
            fail("The activation is Land On (3) or Walk Over (1).")
    space_type = settings.get("spaceType")
    if space_type is not None:
        if space_type in _SPACE_TYPE_IDS and not isinstance(space_type, bool):
            out["spaceType"] = int(space_type)
        else:
            fail("The event's spaces are Happening, Blue or Red spaces.")
    values = settings.get("parameterValues")
    if values is not None and not isinstance(values, dict):
        fail("The parameter values are an object.")
        values = None
    for param in _parameters(event):
        if values is None or values.get(param["name"]) is None:
            continue
        try:
            out["parameterValues"][param["name"]] = \
                _check_value(param["name"], param["type"], values[param["name"]])
        except PlaytestError as e:
            fail(str(e))
    return out


def describe(event):
    """What the event test dialog offers: {activations, spaceTypes, parameters, spaces,
    loopSpaces, defaults}."""
    return {
        "activations": [dict(a) for a in ACTIVATIONS],
        "spaceTypes": [dict(s) for s in SPACE_TYPES],
        "parameters": _parameters(event),
        "spaces": spaces(),
        "loopSpaces": LOOP_SPACES,
        "defaults": default_settings(event),
    }


def build_board(new_board, event, settings):
    """The test board for the event (a new dict; new_board is not changed).

    new_board: a new Battle Royal board of the game, for its images and settings.
    event: the custom event (lib.events.Event, with its code). settings:
    normalize_settings' output.
    """
    if not event.custom or not event.asm:
        raise PlaytestError("Only custom events (with their code) can be test-played.")
    board = copy.deepcopy(new_board)
    board["name"] = "Event Test"
    board["description"] = "Testing %s." % event.name
    board["events"] = {event.id: {"language": int(_plain(event.language)), "code": event.asm}}
    width = board["bg"]["width"]
    height = board["bg"]["height"]

    # The loop: an ellipse, clockwise from the bottom, with the invisible space where it
    # closes and the start space below that.
    cx, cy = width / 2, height / 2
    rx, ry = width * 0.36, height * 0.32
    count = LOOP_SPACES + 1                    # the invisible space is on the loop too

    def at(slot):
        angle = math.pi / 2 + 2 * math.pi * slot / count
        return round(cx + rx * math.cos(angle)), round(cy + ry * math.sin(angle))

    loop_type = settings["spaceType"] if settings["activation"] == int(EventActivationType.LANDON) \
        else int(Space.BLUE)
    hub_x, hub_y = at(0)
    board["spaces"] = [
        {"x": hub_x, "y": min(height - 40, hub_y + 90), "z": 0, "type": int(Space.START)},
        {"x": hub_x, "y": hub_y, "z": 0, "type": int(Space.OTHER)},
    ]
    for n in range(LOOP_SPACES):
        x, y = at(n + 1)
        board["spaces"].append({"x": x, "y": y, "z": 0, "type": loop_type})

    last = FIRST_LOOP_INDEX + LOOP_SPACES - 1
    board["links"] = {START_INDEX: INVISIBLE_INDEX}
    for index in range(INVISIBLE_INDEX, last):
        board["links"][index] = index + 1
    board["links"][last] = INVISIBLE_INDEX

    def instance():
        return {
            "id": event.id,
            "activationType": settings["activation"],
            "executionType": int(event.execution_type),
            "parameterValues": copy.deepcopy(settings["parameterValues"]),
            "custom": True,
        }

    if settings["activation"] == int(EventActivationType.WALKOVER):
        board["spaces"][INVISIBLE_INDEX]["events"] = [instance()]
    else:
        for index in range(FIRST_LOOP_INDEX, last + 1):
            board["spaces"][index]["events"] = [instance()]
    return board


def unsupported_reason(event, game=Game.MP3_USA):
    """Why the event cannot be test-played in the game, or None."""
    if not event.custom:
        return "Only custom events can be test-played."
    if not supports_game(event, game):
        return ("%s does not list Mario Party 3 (USA) (MP3_USA) in its GAMES, so it "
                "cannot be tested in this ROM." % event.name)
    return None
