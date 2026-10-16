"""MP2 validation rules (validation.MP2.ts)."""

from . import validation_common  # noqa: F401  (creates the rules)
from .validationrules import get_rule

_common_rules = [
    get_rule("TOOMANYBOWSERS", {"limit": 0}),
    get_rule("TOOMANYKOOPAS", {"limit": 0}),
    get_rule("TOOMANYGATES", {"limit": 0}),  # Someday
]


def get_validation_rules(game_id):
    from ..adapter.boardinfo import get_arrow_rotation_limit

    rules = _common_rules[:]

    total_arrows_to_write = get_arrow_rotation_limit()
    rules.append(get_rule("TOOMANYARROWROTATIONS", {"limit": total_arrows_to_write}))

    return rules


def get_validation_rules_for_board(game_id, board_index):
    if board_index == 0:
        return [
            get_rule("TOOMANYBANKS", {"limit": 2}),
            get_rule("TOOMANYITEMSHOPS", {"limit": 1}),
            get_rule("TOOMANYBOOS", {"limit": 2}),
            get_rule("BADSTARCOUNT", {"low": 7, "high": 7}),
        ]

    return []
