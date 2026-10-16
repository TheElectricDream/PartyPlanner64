"""Undo history, as store.ts configured redux-undo for the board state.

    undoable(boardStateReducer, {
      groupBy: groupByActionTypes([setSpacePositionsAction, setSpaceRotationAction]),
      filter: excludeAction([addEventToLibraryAction, clearSelectedSpacesAction,
        setSelectedSpaceAction, setSelectedSpacesAction, setSelectionBoxCoordsAction,
        setHighlightedSpacesAction, setHoveredBoardEventIndexAction,
        setTemporaryUIConnections]),
    })

This follows redux-undo 1.x: filtered (excluded) actions change the present
state without adding a step, and are lost when undoing or redoing (the
history keeps the last unfiltered state); consecutive actions of a grouped
type replace the present state instead of adding a step.
"""

GROUP_BY = frozenset(["setSpacePositionsAction", "setSpaceRotationAction"])

EXCLUDED = frozenset([
    "addEventToLibraryAction",
    "clearSelectedSpacesAction",
    "setSelectedSpaceAction",
    "setSelectedSpacesAction",
    "setSelectionBoxCoordsAction",
    "setHighlightedSpacesAction",
    "setHoveredBoardEventIndexAction",
    "setTemporaryUIConnections",
])


class History:
    """past, present, future and the bookkeeping redux-undo keeps."""

    def __init__(self, present, limit=None):
        self.limit = limit
        self.clear(present)

    def clear(self, present=None):
        """ActionCreators.clearHistory(): only the present remains."""
        if present is None:
            present = self.present
        self.past = []
        self.present = present
        self.future = []
        self.latest_unfiltered = present
        self.group = None

    @property
    def can_undo(self):
        return len(self.past) > 0

    @property
    def can_redo(self):
        return len(self.future) > 0

    def _new_history(self, past, present, future, group=None):
        self.past = past
        self.present = present
        self.future = future
        self.latest_unfiltered = present
        self.group = group

    def apply(self, action_types, new_present):
        """Record the state after an action (or a batch of actions).

        Args:
            action_types: The Redux type of each action applied.
            new_present: The resulting state, which is the present itself
                when nothing changed (as with immer).

        Returns:
            Whether the history changed.
        """
        if new_present is self.latest_unfiltered:
            return False
        filtered = all(t in EXCLUDED for t in action_types)
        if filtered:
            # newHistory(past, res, future, group), keeping _latestUnfiltered.
            latest = self.latest_unfiltered
            self.present = new_present
            self.latest_unfiltered = latest
            return True
        group = None
        if len(action_types) == 1 and action_types[0] in GROUP_BY:
            group = action_types[0]
        if group is not None and group == self.group:
            self._new_history(self.past, new_present, self.future, self.group)
            return True
        self._insert(new_present, group)
        return True

    def _insert(self, state, group):
        length_without_future = len(self.past) + 1
        overflow = self.limit and self.limit <= length_without_future
        past = self.past[1:] if overflow else list(self.past)
        if self.latest_unfiltered is not None:
            past.append(self.latest_unfiltered)
        self._new_history(past, state, [], group)

    def undo(self):
        """Go one step back; returns whether there was a step."""
        if not self.past:
            return False
        index = len(self.past) - 1
        new_future = self.past[index + 1:] + [self.latest_unfiltered] + self.future
        new_present = self.past[index]
        self._new_history(self.past[:index], new_present, new_future)
        return True

    def redo(self):
        """Go one step forward; returns whether there was a step."""
        if not self.future:
            return False
        new_past = self.past + [self.latest_unfiltered]
        new_present = self.future[0]
        self._new_history(new_past, new_present, self.future[1:])
        return True
