"""Validating a board before it overwrites a ROM board (validation.ts).

validate_current_board_for_overwrite returns the TypeScript's
IValidationResult list, as dicts with snake_case keys:

    [{"errors": [...], "warnings": [...]},             # rules for the game
     {"name": rom board name, "unavailable": bool,     # one per ROM board
      "forced_disabled": bool, "errors": [...], "warnings": [...],
      "rom_board_index": i},                           # (rom_board_index: Python addition)
     ...]

validate_board flattens that into [{"level": 1|2, "message": str}] for one
target ROM board (1 = error, 2 = warning), the shape the server sends.
"""

from ..types import BoardType, Game, ValidationLevel
from . import validation_mp1, validation_mp2, validation_mp3
from .validationrules import get_rule


def _romhandler():
    from ..romhandler import romhandler
    return romhandler


def _overwrite_available(board_info):
    if board_info.get("can_overwrite"):
        return True
    return False


def _dont_show_in_ui(rom_board, board_type):
    if not isinstance(board_type, str):
        # Because default is normal
        return rom_board.get("type") == BoardType.DUEL
    return rom_board.get("type") != board_type


def _get_rules_for_game(game_id):
    """Returns validation rules that apply for a specific game,
    regardless of the ROM board being overwritten."""
    rules = [
        get_rule("HASSTART"),
        get_rule("GAMEVERSION"),
        get_rule("DEADEND"),
        get_rule("TOOMANYSPACES"),
        get_rule("UNRECOGNIZEDEVENTS"),
        get_rule("UNSUPPORTEDEVENTS"),
        get_rule("CUSTOMEVENTFAIL"),
        get_rule("CUSTOMEVENTBADPARAMS"),
        get_rule("TOOMANYPATHOPTIONS"),
        get_rule("CHARACTERSONPATH"),
        get_rule("SPLITATNONINVISIBLESPACE"),
        get_rule("AUDIODETAILSISSUE"),
    ]

    if game_id in (Game.MP1_USA, Game.MP1_JPN):
        rules = rules + validation_mp1.get_validation_rules(game_id)
    elif game_id in (Game.MP2_USA, Game.MP2_JPN):
        rules = rules + validation_mp2.get_validation_rules(game_id)
    elif game_id in (Game.MP3_USA, Game.MP3_JPN):
        rules = rules + validation_mp3.get_validation_rules(game_id)

    return rules


def _get_rules_for_board(game_id, board_index):
    """Returns any validation rules specific to a particular game + board."""
    rules = []

    if game_id in (Game.MP2_USA, Game.MP2_JPN):
        rules = rules + validation_mp2.get_validation_rules_for_board(game_id, board_index)

    return rules


def _evaluate(rules, context, errors, warnings):
    for rule in rules:
        failure_result = rule.fails(context)
        if failure_result:
            if rule.level == ValidationLevel.ERROR:
                errors.append(failure_result)
            elif rule.level == ValidationLevel.WARNING:
                warnings.append(failure_result)


def validate_current_board_for_overwrite(rom_boards, board, skip_validation=False):
    """Validates `board` for the loaded ROM. Returns the result list (see the
    module docstring), or None when no ROM is loaded."""
    from ..adapter.boardinfo import get_board_infos
    from ..adapter.boardinfobase import dummy_board_info

    game_id = _romhandler().get_rom_game()
    if not game_id:
        return None

    results = []

    # Evaluate rules common to all boards.
    game_level_errors = []
    game_level_warnings = []
    if not skip_validation:
        _evaluate(_get_rules_for_game(game_id), {"board": board, "board_info": dummy_board_info},
                  game_level_errors, game_level_warnings)
    results.append({
        "errors": game_level_errors,
        "warnings": game_level_warnings,
    })

    forced_disabled = not skip_validation and len(game_level_errors) > 0

    # Evaluate any rules specific to certain ROM board targets.
    # As we switch to common overlays, these cases are dwindling.
    board_infos = get_board_infos(game_id)
    if board_infos:
        for board_index in range(len(rom_boards)):
            rom_board = rom_boards[board_index]
            if _dont_show_in_ui(rom_board, rom_board.get("type")):
                continue

            board_info = board_infos[board_index]
            unavailable = not _overwrite_available(board_info)

            board_level_errors = []
            board_level_warnings = []
            if not unavailable and not skip_validation:
                # (As in the TypeScript, the ROM board itself is what these rules see.)
                _evaluate(_get_rules_for_board(game_id, board_index),
                          {"board": rom_board, "board_info": board_info},
                          board_level_errors, board_level_warnings)

            results.append({
                "name": rom_board.get("name"),
                "unavailable": unavailable,
                "forced_disabled": forced_disabled,
                "errors": board_level_errors,
                "warnings": board_level_warnings,
                "rom_board_index": board_index,
            })

    return results


def validate_board(rom_boards, board, rom_board_index=None, skip_validation=False):
    """Flattened results for the server: [{"level": 1|2, "message": str}].

    Includes the game-level results and, when rom_board_index is given, that
    ROM board's results (plus an error if it can't be overwritten).
    """
    results = validate_current_board_for_overwrite(rom_boards, board, skip_validation)
    if results is None:
        return [{"level": int(ValidationLevel.ERROR), "message": "No ROM is loaded."}]

    messages = []

    def add(result):
        for message in result["errors"]:
            messages.append({"level": int(ValidationLevel.ERROR), "message": message})
        for message in result["warnings"]:
            messages.append({"level": int(ValidationLevel.WARNING), "message": message})

    add(results[0])
    if rom_board_index is not None:
        for result in results[1:]:
            if result["rom_board_index"] == rom_board_index:
                if result["unavailable"]:
                    messages.append({"level": int(ValidationLevel.ERROR),
                                     "message": "This board cannot be overwritten."})
                add(result)
    return messages
