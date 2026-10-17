"""A ROM board's "background can't be shown" flag goes once it has a background of its own."""

from partyplanner64.editor.board_state import BoardState, set_background_action


def test_set_background_clears_hvq_flag():
    state = BoardState()
    state.boards = [{"bg": {"src": "data:black"}, "_bgHvq": True}]
    state.current_board_index = 0
    set_background_action(state, {"bg": "data:mine"}, None)
    assert state.boards[0]["bg"]["src"] == "data:mine"
    assert "_bgHvq" not in state.boards[0]
