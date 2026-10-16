"""The image cache, JavaScript-style JSON, the undo history and the board functions."""

import pytest

from partyplanner64.editor import boards, images, jsjson
from partyplanner64.editor.history import History
from partyplanner64.editor.store import EditorStore, normalize_action_type, store


def test_images():
    images.clear()
    url = images.register("data:image/png;base64,AAEC")
    assert url.startswith("/api/image/") and len(url) == len("/api/image/") + 40
    assert images.get(url.rsplit("/", 1)[1]) == ("image/png", b"\x00\x01\x02")
    assert images.resolve(url) == "data:image/png;base64,AAEC"
    assert images.resolve("/api/image/" + "f" * 40) == "/api/image/" + "f" * 40
    board = {"bg": {"src": "data:image/png;base64,AAEC"}, "animbg": ["data:image/gif,%41"],
             "audioData": [{"data": "data:audio/midi;base64,AA=="}], "name": "x"}
    ext = images.externalize(board)
    assert ext["bg"]["src"] == url and ext["animbg"][0].startswith("/api/image/")
    assert ext["audioData"][0]["data"] == "data:audio/midi;base64,AA=="
    assert board["bg"]["src"].startswith("data:")              # the original is unchanged
    assert images.internalize(ext) == board
    assert images.get(ext["animbg"][0].rsplit("/", 1)[1]) == ("image/gif", b"A")
    assert images.get("0" * 40) is None


def test_jsjson():
    assert jsjson.stringify({"b": 1, "10": 2, "2": 3, "a": [1.0, 2.5, True, None]}) == \
        '{"2":3,"10":2,"b":1,"a":[1,2.5,true,null]}'
    assert jsjson.stringify({1: "x", "01": "y"}) == '{"1":"x","01":"y"}'
    assert jsjson.stringify("é🎲") == '"é🎲"'
    assert jsjson.parse(b"\xef\xbb\xbf[1]") == [1]
    assert jsjson.stringify(float("nan")) == "null"


def test_history_semantics():
    h = History("s0")
    assert not h.apply(["setBoardNameAction"], "s0")                # no change
    h.apply(["setBoardNameAction"], "s1")
    h.apply(["setSelectedSpaceAction"], "s1-selected")              # filtered
    assert h.past == ["s0"] and h.present == "s1-selected"
    h.apply(["setSpacePositionsAction"], "s2")
    h.apply(["setSpacePositionsAction"], "s3")                      # grouped
    assert h.past == ["s0", "s1"] and h.present == "s3"
    assert h.undo() and h.present == "s1" and h.future == ["s3"]
    assert h.undo() and h.present == "s0" and not h.undo()
    assert h.redo() and h.redo() and not h.redo() and h.present == "s3"
    h.clear()
    assert not h.can_undo and not h.can_redo and h.present == "s3"


def test_normalize_action_type():
    assert normalize_action_type("setBoardName") == "setBoardNameAction"
    assert normalize_action_type("setBoardNameAction") == "setBoardNameAction"
    assert normalize_action_type("setTemporaryUIConnections") == "setTemporaryUIConnections"
    assert normalize_action_type("setTemporaryUIConnectionsAction") == \
        "setTemporaryUIConnections"
    assert normalize_action_type("addEventToLibrary") == "addEventToLibraryAction"
    with pytest.raises(ValueError):
        normalize_action_type("nope")


def test_states_are_snapshots():
    s = EditorStore()
    s.dispatch("setBoardsAction", {"boards": [boards._make_default_board(1)]})
    before = s.state
    s.dispatch("setBoardNameAction", {"name": "New"})
    assert before.boards[0]["name"] == "Untitled"
    assert s.state.boards[0]["name"] == "New"
    assert s.state.boards[0]["bg"]["src"] is before.boards[0]["bg"]["src"]   # strings shared


def test_listeners():
    s = EditorStore()
    seen = []
    s.subscribe(seen.append)
    s.dispatch("setBoardsAction", {"boards": [boards._make_default_board(1)]})
    s.dispatch("setBoardNameAction", {"name": "New"})
    s.dispatch("setSelectedSpaceAction", 0)
    s.undo()
    assert seen == [{"board", "boards"}, {"board", "boards"}, {"ui"},
                    {"board", "boards", "history"}]


def test_board_functions(tmp_path):
    from partyplanner64 import state
    state.configure(str(tmp_path))
    assert boards.get_board_count() == 1
    index = boards.add_board(None, game=2)
    assert index == 1 and boards.get_boards()[1]["game"] == 2
    boards.set_current_board(1)
    assert boards.get_current_board_index() == 1 and not store.can_undo
    boards.set_board_name("Two")
    assert boards.get_current_board()["name"] == "Two" and store.can_undo
    assert boards.add_space(10, 10, 1) == 1
    assert boards.copy_board(0, make_current=False) == 1
    assert [b["name"] for b in boards.get_boards()] == ["Untitled", "Copy of Untitled", "Two"]
    assert boards.get_current_board_index() == 2
    boards.delete_board(2)
    assert boards.get_current_board_index() == 1
    assert boards.strip_private_props({"_rom": True, "a": {"_x": 1, "b": [{"_c": 2}]}}) == \
        {"a": {"b": [{}]}}
    assert len(boards._theme()) == 11
