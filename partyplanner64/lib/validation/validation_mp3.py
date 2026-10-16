"""MP3 validation rules (validation.MP3.ts)."""

from . import validation_common  # noqa: F401  (creates the rules)
from .validationrules import get_rule

_common_rules = [
    get_rule("TOOMANYBOWSERS", {"limit": 0}),
    get_rule("TOOMANYKOOPAS", {"limit": 0}),
    get_rule("GATESETUP"),
    get_rule("OVERRECOMMENDEDSPACES", {"max": 128}),
    get_rule("ADDITIONALBGCODEISSUE"),
    get_rule("GETAUDIOINDEXCODEISSUE"),
]


def get_validation_rules(game_id):
    from ..adapter.boardinfo import get_arrow_rotation_limit
    from ..events.builtin.events_common import BankEvent, ItemShopEvent

    rules = _common_rules[:]

    total_arrows_to_write = get_arrow_rotation_limit()
    rules.append(get_rule("TOOMANYARROWROTATIONS", {"limit": total_arrows_to_write}))

    rules.append(get_rule("TOOMANYOFEVENT", {"event": BankEvent, "high": 2}))
    rules.append(get_rule("TOOMANYBANKS", {"limit": 2}))
    rules.append(get_rule("TOOMANYOFEVENT", {"event": ItemShopEvent, "high": 2}))
    rules.append(get_rule("TOOMANYITEMSHOPS", {"limit": 2}))

    # TODO: gamemasterplc: @PartyPlanner64 replace 0x323AAC in ROM with a NOP if you want more boos
    rules.append(get_rule("TOOMANYBOOS", {"limit": 1}))
    rules.append(get_rule("TOOMANYGATES", {"limit": 2}))

    rules.append(get_rule("BADSTARCOUNT", {"low": 0, "high": 8, "disallowed": {1: True}}))
    rules.append(get_rule("WARNNOSTARSPACES"))

    # No longer needed? See MP3 onAfterOverwrite.
    # rules.push(getRule("TOOFEWBLUESPACES", { low: 14 }));
    # rules.push(getRule("TOOFEWREDSPACES", { low: 1 }));

    return rules
