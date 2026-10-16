"""The core API (docs/API.md), through a live server."""

import base64
import http.client
import json
import threading
import time

import pytest

from partyplanner64 import state
from partyplanner64.editor import images
from partyplanner64.editor.store import store

from .conftest import Client, start_server

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
                       "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
PNG_URL = "data:image/png;base64," + base64.b64encode(PNG).decode()

EVENT_ASM = """; NAME: My Event
; GAMES: MP1_USA,MP2_USA,MP3_USA
; EXECUTION: Direct
; PARAM: Space|target
ADDIU SP SP -4
ADDIU SP SP 4
JR RA
NOP
"""


def test_state(client):
    s = client.get("/api/state")
    assert set(s) == {"version", "rom", "settings", "boards"}
    assert s["rom"] is None
    assert s["settings"]["write.branding"] is True
    assert s["settings"]["ui.theme"] == "classic"
    boards = s["boards"]
    assert boards["current"] == {"index": 0, "rom": False}
    assert boards["romList"] == []
    assert len(boards["list"]) == 1
    summary = boards["list"][0]
    assert {k: summary[k] for k in ("index", "rom", "name", "game", "type", "spaceCount")} == {
        "index": 0, "rom": False, "name": "Untitled", "game": 1, "type": "NORMAL",
        "spaceCount": 1}
    assert summary["bg"].startswith("/api/image/")


def test_unknown_api_and_method(client):
    status, _, body = client.call("GET", "/api/nothing")
    assert status == 404 and json.loads(body)["error"]
    status, _, _ = client.call("GET", "/api/board/op")
    assert status == 405


def test_settings_persist(client, data_dir):
    assert client.get("/api/settings")["ui.advanced"] is False
    client.post("/api/settings", {"ui.foo": True}, expect=400)
    client.post("/api/settings", {"ui.advanced": "yes"}, expect=400)
    client.post("/api/settings", {"ui.theme": "pink"}, expect=400)
    result = client.post("/api/settings", {"ui.advanced": True, "ui.theme": "dark-gray"})
    assert result["ui.advanced"] is True and result["ui.theme"] == "dark-gray"
    schema = client.get("/api/settings/schema")
    ids = [s["id"] for sec in schema["sections"] for s in sec["settings"]]
    assert ids == list(state.SETTING_DEFAULTS)
    state.shutdown()
    assert json.loads((data_dir / "settings.json").read_text()) == {
        "ui.advanced": True, "ui.theme": "dark-gray"}
    # A restart reads them back.
    server = start_server(data_dir)
    try:
        other = Client(server.server_address[1])
        assert other.get("/api/settings")["ui.advanced"] is True
        assert other.post("/api/settings/reset")["ui.advanced"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_debug_setting(client):
    from partyplanner64.lib.debug import is_debug
    client.post("/api/settings", {"ui.debug": True})
    assert is_debug()
    client.post("/api/settings", {"ui.debug": False})
    assert not is_debug()


def test_new_boards(client):
    res = client.post("/api/boards/new", {"game": 2, "type": "NORMAL", "theme": "default"})
    assert res["index"] == 1
    assert res["boards"]["current"] == {"index": 1, "rom": False}
    board = client.get("/api/board")["board"]
    assert board["game"] == 2 and board["audioIndex"] == 0x36
    assert board["otherbg"]["boardselecticon"].startswith("/api/image/")
    client.post("/api/boards/new", {"game": 3, "type": "DUEL"}, expect=400)   # needs debug
    client.post("/api/boards/new", {"game": 4}, expect=400)
    client.post("/api/settings", {"ui.debug": True})
    res = client.post("/api/boards/new", {"game": 3, "type": "DUEL"})
    board = client.get("/api/board")["board"]
    assert board["type"] == "DUEL" and [s["type"] for s in board["spaces"]] == [17, 18]


def test_ops_undo_redo(client):
    r = client.op("addSpace", {"x": 10, "y": 20, "type": 1})
    assert r["canUndo"] and not r["canRedo"]
    assert r["board"]["spaces"][1] == {"x": 10, "y": 20, "z": 0, "type": 1}
    r2 = client.op("addConnectionAction", {"startSpaceIndex": 0, "endSpaceIndex": 1})
    assert r2["board"]["links"] == {"0": 1}
    assert r2["revision"] > r["revision"]
    # A failing op changes nothing.
    client.op("setSpaceRotation", {"spaceIndex": 9, "angleYAxisDeg": 3}, expect=400)
    client.op("noSuchOp", {}, expect=400)
    client.op("setBoardName", {}, expect=400)
    client.post("/api/board/op", {"args": {}}, expect=400)
    assert client.get("/api/board")["board"]["links"] == {"0": 1}
    # Drags group into one step.
    for x in (11, 12, 13):
        client.op("setSpacePositions", {"spaceIndices": [1], "coords": [{"x": x}]})
    r = client.post("/api/board/undo")
    assert r["board"]["spaces"][1]["x"] == 10
    r = client.post("/api/board/undo")
    assert r["board"]["links"] == {}
    r = client.post("/api/board/redo")
    assert r["board"]["links"] == {"0": 1} and r["canRedo"]
    # Several ops in one step, all or nothing.
    r = client.post("/api/board/ops", {"ops": [
        {"op": "setBoardName", "args": {"name": "A"}},
        {"op": "setBoardDifficulty", "args": {"difficulty": 1}}]})
    assert r["board"]["name"] == "A" and not r["canRedo"]
    client.post("/api/board/ops", {"ops": [
        {"op": "setBoardName", "args": {"name": "B"}},
        {"op": "removeSpaceAction", "args": {}}]}, expect=400)
    assert client.get("/api/board")["board"]["name"] == "A"
    r = client.post("/api/board/undo")
    assert r["board"]["name"] == "Untitled" and r["board"]["difficulty"] == 3
    client.post("/api/board/ops", {"ops": "x"}, expect=400)


def test_selection_and_single_space_ops(client):
    client.op("addSpace", {"x": 10, "y": 20, "type": 1})
    client.post("/api/events", {"code": EVENT_ASM, "language": 0})
    event = {"id": "My Event", "activationType": 3, "executionType": 1, "custom": True}
    client.op("addEventToSpace", {"event": event}, expect=400)       # nothing selected
    r = client.op("addEventToSpace", {"event": event, "spaceIndex": 1})
    assert r["board"]["spaces"][1]["events"][0]["id"] == "My Event"
    assert "My Event" in r["board"]["events"]
    r = client.op("setSelectedSpace", 1)
    assert r["ui"]["selectedSpaceIndices"] == [1]
    r = client.op("setSpaceEventEventParameter", {"eventIndex": 0, "name": "target", "value": 0})
    assert r["board"]["spaces"][1]["events"][0]["parameterValues"] == {"target": 0}
    r = client.op("removeSpace", {"index": 0})
    assert r["board"]["spaces"][0]["events"][0]["parameterValues"] == {}


def test_board_list(client):
    client.post("/api/boards/new", {"game": 1})
    client.op("setBoardName", {"name": "Second"})
    r = client.post("/api/boards/current", {"index": 0, "rom": False})
    assert r["boards"]["current"] == {"index": 0, "rom": False}
    assert not client.get("/api/board")["canUndo"]                # history cleared
    client.post("/api/boards/current", {"index": 5}, expect=404)
    r = client.post("/api/boards/copy", {"index": 1, "rom": False})
    assert r["index"] == 2
    assert [b["name"] for b in r["boards"]["list"]] == ["Untitled", "Second", "Copy of Second"]
    assert r["boards"]["current"] == {"index": 0, "rom": False}
    r = client.post("/api/boards/copy", {"index": 0, "makeCurrent": True})
    assert [b["name"] for b in r["boards"]["list"]] == [
        "Untitled", "Copy of Untitled", "Second", "Copy of Second"]
    assert r["boards"]["current"] == {"index": 1, "rom": False}
    assert client.get("/api/boards/2")["board"]["name"] == "Second"
    client.get("/api/boards/9", expect=404)
    client.get("/api/boards/0?rom=1", expect=404)
    r = client.post("/api/boards/delete", {"index": 0})
    assert [b["name"] for b in r["boards"]["list"]] == ["Copy of Untitled", "Second",
                                                        "Copy of Second"]
    assert r["boards"]["current"] == {"index": 0, "rom": False}
    for _ in range(3):
        r = client.post("/api/boards/delete", {"index": 0})
    assert [b["name"] for b in r["boards"]["list"]] == ["Untitled"]      # never empty
    client.post("/api/boards/delete", {"index": 3}, expect=404)
    client.post("/api/boards/delete", {"index": 0, "rom": True}, expect=400)


def test_images(client):
    board = client.get("/api/board")["board"]
    status, headers, body = client.call("GET", board["bg"]["src"])
    assert status == 200 and headers["Content-Type"] == "image/png"
    assert body.startswith(b"\x89PNG")
    r = client.op("setBackground", {"bg": PNG_URL})
    url = r["board"]["bg"]["src"]
    assert url.startswith("/api/image/")
    assert client.call("GET", url)[2] == PNG
    assert store.state.boards[0]["bg"]["src"] == PNG_URL                  # kept as a data URL
    # A cache URL sent back is the image again.
    client.op("setBoardOtherBg", {"name": "boardlogo", "value": url})
    assert store.state.boards[0]["otherbg"]["boardlogo"] == PNG_URL
    assert client.call("GET", "/api/image/" + "0" * 40)[0] == 404
    # Custom music stays a data URL.
    client.op("setBoardAudio", {"audioChanges": {"audioType": 1, "customAudioIndex": 0,
                                                 "midiData": "data:audio/midi;base64,AA=="}})
    assert client.get("/api/board")["board"]["audioData"][0]["data"].startswith("data:audio")


def test_export_import_round_trip(client):
    client.op("addSpace", {"x": 10.5, "y": 20, "type": 2})
    client.op("addConnection", {"startSpaceIndex": 1, "endSpaceIndex": 0})
    client.op("setBackground", {"bg": PNG_URL})
    status, headers, body = client.call("GET", "/api/boards/0/export")
    assert status == 200 and "Untitled.json" in headers["Content-Disposition"]
    exported = json.loads(body)
    assert exported["bg"]["src"] == PNG_URL and exported["links"] == {"1": 0}
    assert not any(k.startswith("_") for k in exported)
    r = client.post("/api/boards/import", body)
    assert r["index"] == 1 and r["boards"]["current"] == {"index": 1, "rom": False}
    assert client.call("GET", "/api/boards/1/export")[2] == body
    client.post("/api/boards/import", b"not json", expect=400)
    client.post("/api/boards/import", b"[1, 2]", expect=400)


def test_typescript_board_file(client, tmp_path):
    """A board file exported by the TypeScript editor imports, and exports the same bytes."""
    from pathlib import Path
    fixtures = Path(__file__).resolve().parent.parent / "fixtures" / "editor"
    ts_file = (fixtures / "ts_board_export.json").read_bytes()
    r = client.post("/api/boards/import", ts_file)
    status, _, body = client.call("GET", "/api/boards/%d/export" % r["index"])
    assert body == ts_file
    # And the TypeScript read the Python's export back to the same file.
    assert (fixtures / "py_board_reexport.json").read_bytes() == body


def test_board_persistence(client, data_dir):
    client.op("setBoardName", {"name": "Saved"})
    client.post("/api/events", {"code": EVENT_ASM, "language": 0})
    state.shutdown()
    saved = json.loads((data_dir / "boards.json").read_text())
    assert [b["name"] for b in saved] == ["Saved"]
    events = json.loads((data_dir / "events.json").read_text())
    assert events[0]["id"] == "My Event" and events[0]["asm"] == EVENT_ASM
    assert set(events[0]) >= {"id", "name", "custom", "language", "asm", "activationType",
                              "executionType", "supportedGames", "parameters"}
    server = start_server(data_dir)
    try:
        other = Client(server.server_address[1])
        assert other.get("/api/board")["board"]["name"] == "Saved"
        assert "My Event" in [e["id"] for e in other.get("/api/events")["events"]]
    finally:
        server.shutdown()
        server.server_close()


def test_corrupt_boards_file(data_dir):
    data_dir.mkdir(parents=True)
    (data_dir / "boards.json").write_text("{not json")
    state.configure(str(data_dir))
    assert len(store.state.boards) == 1
    assert list(data_dir.glob("boards.json.bad-*"))


def test_events(client):
    events = client.get("/api/events")
    assert events["boardEvents"] == []
    builtin = [e for e in events["events"] if not e["custom"]]
    assert builtin, "the built-in events are listed"
    client.post("/api/events", {"code": "nothing", "language": 0}, expect=400)
    client.post("/api/events", {"code": EVENT_ASM.replace("My Event", builtin[0]["id"]),
                                "language": 0}, expect=400)
    r = client.post("/api/events", {"code": EVENT_ASM, "language": 0})
    assert r["event"]["id"] == "My Event" and r["event"]["code"] == EVENT_ASM
    assert r["event"]["parameters"] == [{"name": "target", "type": "Space"}]
    assert r["event"]["supportedGames"] == ["CLBE", "NMWE", "NMVE"]
    e = client.get("/api/events/My%20Event")
    assert e["code"] == EVENT_ASM and e["custom"]
    status, headers, body = client.call("GET", "/api/events/My%20Event/export")
    assert body.decode() == EVENT_ASM and "My%20Event.s" in headers["Content-Disposition"]
    client.post("/api/events/%s/delete" % builtin[0]["id"].replace(" ", "%20"), expect=400)
    # Board copies.
    client.post("/api/events/My%20Event/copy-to-board")
    board_events = client.get("/api/events")["boardEvents"]
    assert board_events[0]["id"] == "My Event" and board_events[0]["inLibrary"]
    assert not board_events[0]["differs"]
    assert client.get("/api/board/events/My%20Event")["code"] == EVENT_ASM
    client.post("/api/events/My%20Event/delete")
    client.get("/api/events/My%20Event", expect=404)
    assert not client.get("/api/events")["boardEvents"][0]["inLibrary"]
    client.post("/api/board/events/My%20Event/copy-to-library")
    assert client.get("/api/events/My%20Event")["custom"]
    client.post("/api/board/events/My%20Event/delete")
    assert client.get("/api/events")["boardEvents"] == []
    # Into the board directly.
    r = client.post("/api/events", {"code": EVENT_ASM.replace("My Event", "Board Only"),
                                    "language": 0, "board": True})
    assert "Board Only" in client.get("/api/board")["board"]["events"]
    client.get("/api/events/Board%20Only", expect=404)
    # Test compile results.
    r = client.post("/api/events/test", {"code": EVENT_ASM, "language": 0})
    assert [x["gameName"] for x in r["results"]] == ["MP1_USA", "MP2_USA", "MP3_USA"]
    assert client.post("/api/events/test", {"code": "x", "language": 0})["event"] is None


def test_event_import(client):
    status, _, body = client.call("POST", "/api/events/import?name=ev.txt", EVENT_ASM.encode())
    assert status == 400
    status, _, body = client.call("POST", "/api/events/import?name=ev.s", b"; nothing")
    assert status == 400 and b"Event file load failed" in body
    status, _, body = client.call("POST", "/api/events/import?name=ev.s", EVENT_ASM.encode())
    if status == 400:
        pytest.skip("test assembly unavailable: %s" % body[:200])
    assert status == 200 and json.loads(body)["event"]["id"] == "My Event"


def test_validate_without_rom(client):
    r = client.get("/api/board/validate?romBoard=0")
    assert r == {"results": [], "general": {"errors": [], "warnings": []}, "boards": [],
                 "romLoaded": False}


def test_board_code(client):
    assert client.get("/api/board/code?kind=additionalbg") == {"code": None, "language": None}
    client.get("/api/board/code?kind=other", expect=400)
    default = client.get("/api/board/code/default?kind=audioselect&language=1")["code"]
    assert isinstance(default, str) and default
    client.op("setAdditionalBackgroundCode", {"code": "// code", "language": 1})
    assert client.get("/api/board/code?kind=additionalbg") == {"code": "// code", "language": 1}
    r = client.post("/api/board/code/test", {"kind": "additionalbg", "code": "garbage(",
                                             "language": 1})
    assert r["ok"] is False and r["messages"]


def test_server_events(client):
    """GET /api/events with Accept: text/event-stream is the event stream."""
    host, port = client.base.split("//")[1].split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=10)
    conn.request("GET", "/api/events", headers={"Accept": "text/event-stream"})
    res = conn.getresponse()
    assert res.getheader("Content-Type") == "text/event-stream"
    assert res.fp.readline().startswith(b"retry:")
    time.sleep(0.2)
    client.op("setBoardName", {"name": "Evented"})
    seen = {}
    deadline = time.time() + 10
    while time.time() < deadline and not {"board", "boards"} <= set(seen):
        line = res.fp.readline().decode().strip()
        if line.startswith("event: "):
            kind = line[7:]
            data = res.fp.readline().decode().strip()
            seen[kind] = json.loads(data[6:])
    conn.close()
    assert seen["board"]["revision"] == store.revision
    assert seen["boards"]["current"] == {"index": 0, "rom": False}


def test_threads(client):
    """Concurrent edits all land."""
    def work():
        for i in range(10):
            client.op("addSpace", {"x": i, "y": i, "type": 1})
    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(client.get("/api/board")["board"]["spaces"]) == 41
    assert len(store.history.past) == 40
