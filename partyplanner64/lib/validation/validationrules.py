"""Validation rule registry (validationrules.ts).

A rule's fails(context, args) returns False when the board passes, or a
message (str). The context is a dict {"board": IBoard, "board_info": IBoardInfo}.
"""

from ..types import ValidationLevel

_rules = {}


class ValidationRule:
    """IValidationRule: id, name, level and fails(context, args=None)."""

    def __init__(self, id="", name="", level=ValidationLevel.ERROR):
        self.id = id
        self.name = name
        self.level = level

    def fails(self, context, args=None):
        raise NotImplementedError("fails not implemented")

    def set_fails(self, fn):
        """Decorator: sets fn(context, args) as this rule's fails."""
        self.fails = fn
        return fn


def create_rule(id, name, level):
    rule = ValidationRule(id, name, level)
    _rules[id] = rule
    return rule


def get_rule(id, args=None):
    """A rule bound to the given args: its fails(context) takes only the context."""
    rule = _rules[id]
    new_rule = ValidationRule(rule.id, rule.name, rule.level)
    new_rule.fails = lambda context, _args=None: rule.fails(context, args)
    return new_rule
