"""The editor's store: the board state with its undo history (port of store.ts).

`store` is the singleton the app uses (the TypeScript's Redux store).
`store.dispatch(type, payload)` runs one reducer of board_state.py on a draft
of the present state and records the result in the history as redux-undo
did; `dispatch_many` runs several as one undo step. Everything happens under
`store.lock`, so the threaded server can use it.

Listeners (`store.subscribe(fn)`) are called with a set of what changed:
"board" (the current board's content), "boards" (the board list, a board's
summary, or which board is current), "ui" (selection and other UI state),
"events" (the event library) and "history" (only the undo history).

The event library (ReduxEventLibrary) is kept by the store too, but outside the
undo history: in the TypeScript it was part of the undoable state, so undoing
could bring back a deleted custom event; here the library only changes when
asked.
"""

import threading

from . import board_state as bs
from .history import History


def normalize_action_type(name):
    """The Redux action type for an op name ("setBoardName" -> "setBoardNameAction")."""
    if not isinstance(name, str) or not name:
        raise ValueError("No op given.")
    if name in bs.REDUCERS or name in bs.LIBRARY_ACTIONS:
        return name
    if name + "Action" in bs.REDUCERS or name + "Action" in bs.LIBRARY_ACTIONS:
        return name + "Action"
    if name.endswith("Action") and name[:-6] in bs.REDUCERS:
        return name[:-6]           # setTemporaryUIConnections(Action)
    raise ValueError("Unknown board op: %s" % name)


def _summary_key(state):
    def key(boards):
        return tuple((b.get("name"), b.get("game"), b.get("type"),
                      len(b.get("spaces") or ()), b.get("description"),
                      (b.get("bg") or {}).get("src") if isinstance(b.get("bg"), dict) else None)
                     for b in boards)
    return (state.current_board_index, state.current_board_is_rom,
            key(state.boards), key(state.rom_boards))


class EditorStore:
    """The board state, its undo history and the event library."""

    def __init__(self):
        self.lock = threading.RLock()
        self.history = History(bs.BoardState())
        self.revision = 0
        self.event_library = {}       # id -> event (EventMap)
        self._listeners = []

    # Reading

    @property
    def state(self):
        """The present BoardState (don't change it)."""
        return self.history.present

    @property
    def can_undo(self):
        return self.history.can_undo

    @property
    def can_redo(self):
        return self.history.can_redo

    def subscribe(self, fn):
        """Call fn(changes) after each change; returns a function that unsubscribes."""
        self._listeners.append(fn)
        return lambda: self._listeners.remove(fn) if fn in self._listeners else None

    def _notify(self, changes):
        if not changes:
            return
        for fn in list(self._listeners):
            fn(set(changes))

    # Changing

    def dispatch(self, action_type, payload=None):
        """Apply one action (a reducer name and its payload). Returns whether anything changed."""
        return self.dispatch_many([(action_type, payload)])

    def dispatch_many(self, actions, check_current=False):
        """Apply several actions as one undo step, all or nothing.

        Args:
            actions: (type, payload) pairs; types as normalize_action_type takes them.
            check_current: Refuse (IndexError) a result without a current board
                (the TypeScript allowed it for a moment, e.g. clearing the ROM's
                boards while one of them was current).

        Returns:
            Whether anything changed.
        """
        actions = [(normalize_action_type(t), p) for t, p in actions]
        with self.lock:
            changes = set()
            board_actions = [(t, p) for t, p in actions if t not in bs.LIBRARY_ACTIONS]
            library_actions = [(t, p) for t, p in actions if t in bs.LIBRARY_ACTIONS]
            # Library actions first: a batch may add an event and use it.
            for t, p in library_actions:
                if self._library_action(t, p):
                    changes.add("events")
            if board_actions:
                changes |= self._board_actions(board_actions, check_current)
                # middleware.ts: clear highlighted spaces after the user does anything else.
                if (any(t != "setHighlightedSpacesAction" for t, _ in board_actions)
                        and self.history.present.highlighted_space_indices):
                    changes |= self._board_actions([("setHighlightedSpacesAction",
                                                     {"spaceIndices": None})])
            if changes - {"ui"}:
                self.revision += 1
        self._notify(changes)
        return bool(changes)

    def _board_actions(self, actions, check_current=False):
        present = self.history.present
        before = _summary_key(present)
        draft = present.draft(edit_board=False)
        for action_type, payload in actions:
            if action_type not in bs.UI_ACTIONS and action_type not in bs.LIST_ACTIONS:
                draft.clone_current_board()
            bs.REDUCERS[action_type](draft, payload if payload is not None else {},
                                     self.event_library)
        if check_current or any(t == "setCurrentBoardAction" for t, _ in actions):
            collection = draft.rom_boards if draft.current_board_is_rom else draft.boards
            if not (isinstance(draft.current_board_index, int)
                    and 0 <= draft.current_board_index < len(collection)):
                raise IndexError("There is no %sboard %s."
                                 % ("ROM " if draft.current_board_is_rom else "",
                                    draft.current_board_index))
        result = present if draft.unchanged_from(present) else draft
        if not self.history.apply([t for t, _ in actions], result):
            return set()
        if result is present:
            return {"history"}
        changes = set()
        if all(t in bs.UI_ACTIONS for t, _ in actions):
            changes.add("ui")
        else:
            changes.add("board")
        if _summary_key(result) != before:
            changes.add("boards")
        return changes

    def _library_action(self, action_type, payload):
        if action_type == "addEventToLibraryAction":
            event = payload["event"]
            self.event_library[event.id] = event
            return True
        event_id = payload["eventId"]
        if not self.event_library.get(event_id):
            raise ValueError("Cannot remove event %s, as it isn't in the event library"
                             % event_id)
        if not self.event_library[event_id].custom:
            raise ValueError("Cannot remove event %s, as it is a built-in event" % event_id)
        del self.event_library[event_id]
        return True

    def undo(self):
        """Undo one step; returns whether there was one."""
        return self._jump(self.history.undo)

    def redo(self):
        """Redo one step; returns whether there was one."""
        return self._jump(self.history.redo)

    def _jump(self, fn):
        with self.lock:
            before = _summary_key(self.history.present)
            if not fn():
                return False
            self.revision += 1
            changes = {"board", "history"}
            if _summary_key(self.history.present) != before:
                changes.add("boards")
        self._notify(changes)
        return True

    def clear_history(self):
        """ActionCreators.clearHistory()."""
        with self.lock:
            had = self.history.can_undo or self.history.can_redo
            self.history.clear()
        if had:
            self._notify({"history"})

    def reset(self):
        """Back to an empty state and library (tests)."""
        with self.lock:
            self.history = History(bs.BoardState())
            self.event_library = {}
            self.revision += 1


store = EditorStore()
