"""AI decision trees (aitrees.ts).

A tree is a list of nodes, {"type", "data", "decision"}, where "decision" is
either a sub-tree (list of nodes) or a result {"value": 0|1, "probability":
[...3 or 4 values]}. Boards store them on spaces as "aiTree" (camelCase JSON).
"""

from enum import IntEnum


class DecisionTreeNodeType(IntEnum):
    leaf = 0
    # Node is accepted if player has the amount of coins.
    hasCoins = 1
    # Node is accepted if the current star matches a flagged bit.
    star = 2
    # Node is accepted if `node_data & (1 << remaining_spaces)` is non-zero.
    remainingSpaces = 3
    stateComparison = 4
    winningHeuristic = 5
    # Node is accepted if function returns true.
    customCode = 6
    # Node is accepted if the number of turns elapsed is at least equal to the value in node_data.
    turnsElapsed = 7
    # Node is accepted if the player has the specified item.
    hasItem = 8
    # There are more, but they're in the sequels and less useful.


def parse_decision_tree(view, offset, base, game):
    """Reads a decision tree at `offset` of the DataView. `base` converts
    RAM addresses (without the 0x80000000 prefix) to view offsets."""
    nodes = []

    while True:
        type = view.get_uint8(offset)
        data = view.get_uint32(offset + 4)
        decision = view.get_uint32(offset + 8)
        if decision & 0x80000000:
            nodes.append({
                "type": type,
                "data": data,
                "decision": parse_decision_tree(view, (decision & 0x7FFFFFFF) - base, base, game),
            })
        else:
            nodes.append({
                "type": type,
                "data": data,
                "decision": _parse_decision_tree_result(decision, game),
            })
        offset += 12
        if type == DecisionTreeNodeType.leaf:
            break

    return nodes


def _parse_decision_tree_result(res, game_version):
    if game_version == 3:
        # Decision, Super Hard, Hard, Normal, Easy
        # DDDD SSSS SSSH HHHH HHNN NNNN NEEE EEEE
        return {
            "value": (res & 0xF0000000) >> 28,
            "probability": [
                res & 0x0000007F,
                (res & 0x00003F80) >> 7,
                (res & 0x001FC000) >> 14,
                (res & 0x0FE00000) >> 21,
            ],
        }
    return {
        "value": (res & 0xFFFF0000) >> 16,
        "probability": [res & 0x000000FF, (res & 0x0000FF00) >> 8],
    }
