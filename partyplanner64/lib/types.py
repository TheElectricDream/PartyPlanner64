"""Commonly used types (port of packages/lib/types.ts).

The editor's View and Action enums were UI state of the React app and
live in the web UI now (partyplanner64/static), not here.
"""

from enum import Enum, IntEnum


class Space(IntEnum):
    OTHER = 0
    BLUE = 1
    RED = 2
    MINIGAME = 3
    HAPPENING = 4
    STAR = 5
    CHANCE = 6
    START = 7
    SHROOM = 8
    BOWSER = 9
    ITEM = 10
    BATTLE = 11
    BANK = 12
    ARROW = 13
    BLACKSTAR = 14
    GAMEGUY = 15
    DUEL_BASIC = 16
    DUEL_START_BLUE = 17
    DUEL_START_RED = 18
    DUEL_POWERUP = 19
    DUEL_REVERSE = 20


class SpaceSubtype(IntEnum):
    TOAD = 0
    BOWSER = 1
    KOOPA = 2
    BOO = 3
    GOOMBA = 4
    BANK = 5
    BANKCOIN = 6
    ITEMSHOP = 7
    GATE = 8


class BoardType(str, Enum):
    NORMAL = "NORMAL"
    DUEL = "DUEL"


class CostumeType(IntEnum):
    """Player costume types."""
    NORMAL = 0
    WESTERN = 1
    PIRATE = 2
    HORROR = 3
    SPACE = 4
    MYSTERY = 5


class Game(str, Enum):
    MP1_USA = "CLBE"
    MP1_JPN = "CLBJ"
    MP1_PAL = "NLBP"

    MP2_USA = "NMWE"
    MP2_JPN = "NMWJ"
    MP2_PAL = "NMWP"

    MP3_USA = "NMVE"
    MP3_JPN = "NMVJ"
    MP3_PAL = "NMVP"


# GameVersion is 1, 2 or 3 (a plain int).
GAME_VERSIONS = (1, 2, 3)


def get_game_name(game_id):
    """Return the Game member name for a game ID ("NMVE" -> "MP3_USA"), or None."""
    for game in Game:
        if game.value == game_id:
            return game.name
    return None


class EventCodeLanguage(IntEnum):
    """Supported languages for custom event code."""
    MIPS = 0
    C = 1


class EventActivationType(IntEnum):
    """What conditions the event code is executed."""
    WALKOVER = 1
    # "MYSTERY" = 2, executed after WALKOVER
    LANDON = 3
    # "MYSTERY" = 4, executed after LANDON

    # Indicates one of the negative space indices is used for this event.
    SPECIAL = 7

    # Not in some games?
    BEGINORWALKOVER = 8
    # "MYSTERY" = 9


class EditorEventActivationType(IntEnum):
    """What conditions the event code is executed, as the editor offers them."""
    WALKOVER = 1
    LANDON = 3

    # These aren't real activation types in the game, they're really
    # special space types. But assigning events to one of these is
    # effectively picking an activation type.

    # Before each player's dice roll.
    BEFORE_DICE_ROLL = -5
    # Just before a player's turn. (Right as "PLAYER START" appears on screen.)
    BEFORE_PLAYER_TURN = -4
    # After each turn. (After last player lands on space, before Mini-Game selection comes up.)
    AFTER_TURN = -3
    # Before each turn. (Right as "PLAYER START" appears for the first player.)
    BEFORE_TURN = -2

    BEGINORWALKOVER = 8


def get_event_activation_type_from_editor_type(editor_type):
    """Map an EditorEventActivationType to the game's EventActivationType."""
    if editor_type == EditorEventActivationType.LANDON:
        return EventActivationType.LANDON
    if editor_type == EditorEventActivationType.WALKOVER:
        return EventActivationType.WALKOVER
    if editor_type in (EditorEventActivationType.BEFORE_TURN,
                       EditorEventActivationType.AFTER_TURN,
                       EditorEventActivationType.BEFORE_PLAYER_TURN,
                       EditorEventActivationType.BEFORE_DICE_ROLL):
        return EventActivationType.SPECIAL
    if editor_type == EditorEventActivationType.BEGINORWALKOVER:
        return EventActivationType.BEGINORWALKOVER
    raise ValueError("Unrecognized editor activation type %s" % (editor_type,))


class EventExecutionType(IntEnum):
    DIRECT = 1
    PROCESS = 2


def get_execution_type_name(execution_type):
    if execution_type == 1:
        return "Direct"
    if execution_type == 2:
        return "Process"
    raise ValueError("Unknown execution type %s." % (execution_type,))


def get_execution_type_by_name(name):
    if name == "Direct":
        return EventExecutionType.DIRECT
    if name == "Process":
        return EventExecutionType.PROCESS
    return None


class ValidationLevel(IntEnum):
    ERROR = 1
    WARNING = 2


EVENT_PARAMETER_TYPES = ["Boolean", "Number", "+Number", "Number[]", "Space", "Space[]"]


class EventParameterType(str, Enum):
    """Types of event parameters allowed."""
    Boolean = "Boolean"
    Number = "Number"
    PositiveNumber = "+Number"
    NumberArray = "Number[]"
    Space = "Space"
    SpaceArray = "Space[]"


def is_array_event_parameter_type(param_type):
    """True if the event parameter type is an array value type."""
    return str(getattr(param_type, "value", param_type)).endswith("[]")
