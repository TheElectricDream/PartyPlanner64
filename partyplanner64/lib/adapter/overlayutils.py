"""Helpers shared by the board overlays (port of adapter/overlayutils.ts).

Also holds the small helpers that render values the way a JavaScript template
literal does, so that the generated overlay assembly is identical to the
TypeScript's.
"""

import math
from decimal import Decimal
import re
import sys
from functools import lru_cache
from importlib import resources

from ..utils.number import distance


def get_shuffle_seed_data(n):
    """Fixed data for the shuffle algorithm used by the board overlays.

    Returns:
        A dict {"order": [...], "bias": [...]}.
    """
    if n == 8:
        return {
            "order": [1, 2, 3, 0, 4, 5, 6, 7],
            "bias": [0, 0, 0, 1, 1, 1, 1, 2],
        }
    if n == 7:
        return {
            "order": [3, 5, 6, 0, 1, 2, 4],
            "bias": [0, 0, 0, 1, 1, 1, 3],
        }
    if n == 6:
        return {
            "order": [0, 1, 2, 3, 4, 5],
            "bias": [0, 0, 0, 1, 1, 1],
        }
    if n == 5:
        return {
            "order": [0, 1, 2, 3, 4],
            "bias": [0, 0, 0, 1, 1],
        }
    if n == 4:
        return {
            "order": [0, 1, 2, 3],
            "bias": [0, 0, 0, 1],
        }
    if n == 3:
        return {
            "order": [0, 1, 2],
            "bias": [0, 0, 1],
        }
    if n == 2:
        return {
            "order": [0, 1],
            "bias": [0, 0],
        }
    if n == 0:
        return {
            "order": [0],
            "bias": [0],
        }

    # Should never reach here, but whatever.
    return {
        "order": [
            0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
            21, 22, 23,
        ],
        "bias": [
            0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4,
            4, 4, 5, 6, 6, 6,
        ],
    }


# --- Shared by the create_board_overlay functions ---

def get_mainfs_event_file(board_info):
    """The [dir, file] of the board's MainFS event file (boardInfo.mainfsEventFile!)."""
    mainfs_event_file = board_info.get("mainfs_event_file")
    if not mainfs_event_file:
        # The TypeScript fails here too (destructuring undefined), e.g. for duel boards.
        raise TypeError("The board info has no mainfs_event_file")
    return mainfs_event_file


def get_spaces_of_subtype(subtype, board):
    """boards.getSpacesOfSubType (looked up lazily: boards imports the adapters)."""
    from .. import boards
    fn = getattr(boards, "get_spaces_of_sub_type", None) or boards.get_spaces_of_subtype
    return fn(subtype, board)


def event_id(event):
    """The id of a built-in event object (BankEvent.id, ...)."""
    if isinstance(event, dict):
        return event["id"]
    return event.id


def find_closest_spaces(board, event_spaces, target_spaces):
    """For each event space, the closest target space (or the dead space if none).

    This is the "Find the closest Bank subtype space for each bank event space" loop
    of the MP2/MP3 overlays. Like the TypeScript, it gets the dead space index
    (creating the dead space) for every event space.
    """
    from ..boards import get_dead_space_index
    best_for_event_spaces = []
    for space_index in event_spaces:
        event_space = board["spaces"][space_index]
        best_distance = sys.float_info.max
        best_idx = get_dead_space_index(board)
        for target_idx in target_spaces:
            target_space = board["spaces"][target_idx]
            dist = distance(event_space["x"], event_space["y"], target_space["x"], target_space["y"])
            if dist < best_distance:
                best_distance = dist
                best_idx = target_idx
        best_for_event_spaces.append(best_idx)
    return best_for_event_spaces


def find_toad_indices(board, star_indices, toad_spaces):
    """Determine the toad spaces (closest toad to each star), using distance formula for now."""
    toad_indices = []
    for star_index in star_indices:
        star_space = board["spaces"][star_index]
        best_distance = sys.float_info.max
        best_toad_idx = star_index  # By default, no toad spaces = put toad on star space for now.
        for toad_idx in toad_spaces:
            toad_space = board["spaces"][toad_idx]
            dist = distance(star_space["x"], star_space["y"], toad_space["x"], toad_space["y"])
            if dist < best_distance:
                best_distance = dist
                best_toad_idx = toad_idx
        toad_indices.append(best_toad_idx)
    return toad_indices


def get_star_indices(board):
    """Indices of the spaces that have a star."""
    return [i for i, space in enumerate(board["spaces"]) if space.get("star")]


def get_arrow_rotation_instructions(board, game):
    """The instructions that add the arrow angles (AddArrowAngle), MP2 and MP3."""
    from ..symbols.symbols import get_symbol
    from .boardinfo import get_arrow_rotation_limit
    from ..utils.debug import hexstr
    from ..utils.number import get_raw_float32_format
    from ..types import Space

    rotations = []
    for space in board["spaces"]:
        if space["type"] == Space.ARROW:
            rotations.append(space.get("rotation") or 0)
    add_arrow_angle_addr = get_symbol(game, "AddArrowAngle")
    total_arrows_to_write = get_arrow_rotation_limit()
    arrow_rotation_instructions = []
    loop_limit = min(total_arrows_to_write, len(rotations))
    for i in range(loop_limit):
        arrow_rotation_instructions.append(
            "LUI A0 hi(" + hexstr(get_raw_float32_format(rotations[i])) + ")")
        arrow_rotation_instructions.append("JAL " + js_str(add_arrow_angle_addr))
        arrow_rotation_instructions.append("MTC1 A0 F12")
    return arrow_rotation_instructions


def ensure_at_least_two(indices, board):
    """Pad a list of space indices to 2 entries with the dead space ("Ensure at least 2")."""
    from ..boards import get_dead_space_index
    for _ in range(2):
        if len(indices) < 2:
            indices.append(get_dead_space_index(board))
    return indices


# --- JavaScript string conversion, for the overlay templates ---

def js_str(value):
    """Convert a value to a string as JavaScript's String(value) does."""
    if value is None:
        return "undefined"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        text = repr(value)
        if "e" in text:
            mantissa, exp = text.split("e")
            exp_num = int(exp)
            if -7 < exp_num < 21:
                return format(Decimal(text), "f")
            return "%se%s%d" % (mantissa, "+" if exp_num > 0 else "-", abs(exp_num))
        return text
    if isinstance(value, (list, tuple)):
        return js_join(value, ",")
    return str(value)


def js_join(values, sep=","):
    """Array.prototype.join: null/undefined elements become empty strings."""
    return sep.join("" if v is None else js_str(v) for v in values)


def js_at(values, index):
    """values[index] in JavaScript: undefined (None) when out of range."""
    if values is None:
        raise TypeError("Cannot read properties of undefined (reading '%d')" % index)
    if 0 <= index < len(values):
        return values[index]
    return None


# --- Overlay templates ---

_PLACEHOLDER_RE = re.compile(r"<<([a-z0-9_A-Z]+)>>")


@lru_cache(maxsize=None)
def load_overlay_template(name):
    """Read (and cache) an overlay template from the overlays/ data folder."""
    path = resources.files(__package__).joinpath("overlays", name)
    with path.open("r", encoding="utf-8", newline="") as f:
        return f.read()


def fill_overlay_template(name, values):
    """Fill the <<name>> placeholders of an overlay template.

    Each value is converted with js_str. Placeholders are replaced in one pass, so
    text inside the values (custom user code) is never treated as a placeholder.
    """
    template = load_overlay_template(name)

    def _replace(match):
        key = match.group(1)
        if key not in values:
            raise KeyError("Missing overlay template value: " + key)
        return js_str(values[key])

    return _PLACEHOLDER_RE.sub(_replace, template)
