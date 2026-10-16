"""MP1 validation rules (validation.MP1.ts)."""

from . import validation_common  # noqa: F401  (creates the rules)
from .validationrules import get_rule

_common_rules = [
    get_rule("TOOMANYGATES", {"limit": 0}),
    get_rule("ADDITIONALBGCODEISSUE"),
    get_rule("GETAUDIOINDEXCODEISSUE"),
    get_rule("TOOMANYBOOS", {"limit": 2}),
    get_rule("TOOMANYBOWSERS", {"limit": 1}),
    get_rule("TOOMANYKOOPAS", {"limit": 1}),
    get_rule("BADSTARCOUNT", {"low": 0, "high": 7, "disallowed": {1: True}}),
    get_rule("WARNNOSTARSPACES"),
]


def get_validation_rules(game_id):
    return _common_rules[:]
