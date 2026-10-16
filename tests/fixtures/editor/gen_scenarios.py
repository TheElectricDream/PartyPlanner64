"""Writes board_state_scenarios.json: action sequences for the differential tests.

    python3 tests/fixtures/editor/gen_scenarios.py
    cd tsref && node ref/run.mjs ref/editor_board_state.ts \
        <repo>/tests/fixtures/editor/board_state_scenarios.json \
        <repo>/tests/fixtures/editor/board_state_expected.json

(gen_board_state.ts, next to this file, is ref/editor_board_state.ts.)
"""

import json
from pathlib import Path

BLUE, RED, HAPPENING, STAR, CHANCE, START, BANK, ITEM, BATTLE, OTHER = 1, 2, 4, 5, 6, 7, 12, 10, 11, 0

EVENT_ASM = """; NAME: Test Event
; GAMES: MP1_USA,MP2_USA,MP3_USA
; EXECUTION: Direct
; PARAM: Space|target
; PARAM: Space[]|spaces
; PARAM: Number|count
ADDIU SP SP -4
JR RA
ADDIU SP SP 4
"""

EVENT2_ASM = """; NAME: Other Event
; GAMES: MP1_USA,MP2_USA,MP3_USA
; EXECUTION: Process
JR RA
NOP
"""

PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
       "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def op(name, args=None):
    return {"op": name, "args": args}


UNDO, REDO, CLEAR = {"undo": True}, {"redo": True}, {"clear": True}


def spaces(*pts, type=BLUE):
    return [op("addSpace", {"x": x, "y": y, "type": type}) for x, y in pts]


scenarios = []

scenarios.append({"name": "spaces and connections (MP1)", "boards": [{"default": [1, "NORMAL"]}],
                  "steps": [
    *spaces((100, 100), (200, 100), (300, 100), (400, 100)),
    op("addSpace", {"x": 500, "y": 200, "type": RED}),
    op("addSpace", {"x": 600, "y": 200, "type": HAPPENING, "subtype": 2}),
    op("addConnection", {"startSpaceIndex": 0, "endSpaceIndex": 1}),
    op("addConnection", {"startSpaceIndex": 1, "endSpaceIndex": 2}),
    op("addConnection", {"startSpaceIndex": 2, "endSpaceIndex": 3}),
    op("addConnection", {"startSpaceIndex": 2, "endSpaceIndex": 4}),
    op("addConnection", {"startSpaceIndex": 2, "endSpaceIndex": 4}),     # again: no change
    op("addConnection", {"startSpaceIndex": 3, "endSpaceIndex": 3}),     # self: no change
    op("addConnection", {"startSpaceIndex": 4, "endSpaceIndex": 5}),
    op("addConnection", {"startSpaceIndex": 5, "endSpaceIndex": 1}),
    op("addConnection", {"startSpaceIndex": 6, "endSpaceIndex": 0}),
    op("setSpacePositions", {"spaceIndices": [1], "coords": [{"x": 210}]}),
    op("setSpacePositions", {"spaceIndices": [1], "coords": [{"x": 220, "y": 110}]}),
    op("setSpacePositions", {"spaceIndices": [1, 2], "coords": [{"x": 230}, {"y": 120, "z": 5}]}),
    UNDO,
    REDO,
    op("setSpaceType", {"spaceIndices": [3, 4], "type": RED}),
    op("setSpaceType", {"spaceIndices": [3], "type": HAPPENING, "subtype": 1}),
    op("setSpaceSubtype", {"spaceIndices": [3], "subtype": 3}),
    op("setSpaceSubtype", {"spaceIndices": [3]}),
    op("setSpaceHostsStar", {"spaceIndices": [0, 1], "hostsStar": True}),
    op("setSpaceHostsStar", {"spaceIndices": [0], "hostsStar": False}),
    op("removeSpace", {"index": 2}),
    UNDO,
    op("removeSpace", {"index": 99}),
    op("removeSpaces", {"spaceIndices": [1, 3]}),
    op("eraseConnections", {"x": 150, "y": 100}),
    UNDO, UNDO, UNDO,
    REDO,
    op("eraseConnections", {"x": 350, "y": 100}),
    op("eraseConnections", {"x": 0, "y": 0}),
    UNDO, UNDO, UNDO, UNDO, UNDO, UNDO, REDO, REDO,
]})

scenarios.append({"name": "rotation, grouping and filtered actions (MP3)",
                  "boards": [{"default": [3, "NORMAL"]}], "steps": [
    *spaces((100, 100), (200, 100)),
    op("setSpaceRotation", {"spaceIndex": 1, "angleYAxisDeg": 10.4}),
    op("setSpaceRotation", {"spaceIndex": 1, "angleYAxisDeg": 22.5}),
    op("setSpaceRotation", {"spaceIndex": 1, "angleYAxisDeg": -12.5}),
    op("setSpacePositions", {"spaceIndices": [0], "coords": [{"x": 5}]}),
    op("setSelectedSpace", 1),
    op("setSpacePositions", {"spaceIndices": [0], "coords": [{"x": 6}]}),
    op("setSpaceType", {"spaceIndices": [1], "type": RED}),
    op("setSpaceRotation", {"spaceIndex": 7, "angleYAxisDeg": 1}),       # error
    UNDO,
    op("setSelectedSpaces", [0, 1]),
    op("setBoardName", {"name": "Untitled"}),        # no change, but after a filtered action
    UNDO,
    op("addSelectedSpace", 2),
    op("clearSelectedSpaces"),
    op("setHighlightedSpaces", {"spaceIndices": [0, 1]}),
    op("setSelectionBoxCoords", {"selectionCoords": [1, 2, 3, 4]}),     # clears highlights
    op("setTemporaryUIConnections", {"connections": [[0, 0, 5, 5]]}),
    op("addConnection", {"startSpaceIndex": 0, "endSpaceIndex": 1}),
    op("setHoveredBoardEventIndex", {"eventIndex": 2}),
    UNDO, REDO, REDO,
    CLEAR,
    UNDO,
]})

scenarios.append({"name": "board details and audio (MP2)", "boards": [{"default": [2, "NORMAL"]}],
                  "steps": [
    op("setBoardName", {"name": "My Board"}),
    op("setBoardDescription", {"description": "Line one\nline two"}),
    op("setBoardDifficulty", {"difficulty": 5}),
    op("setBoardCostumeTypeIndex", {"costumeType": 3}),
    op("setBackground", {"bg": PNG}),
    op("setBoardOtherBg", {"name": "boardlogo", "value": PNG}),
    op("addAnimationBackground", {"bg": PNG}),
    op("addAnimationBackground", {"bg": PNG + "A"}),
    op("removeAnimationBackground", {"index": 5}),
    op("removeAnimationBackground", {"index": 0}),
    op("addAdditionalBackground", {"bg": PNG}),
    op("removeAdditionalBackground", {"index": -1}),
    op("removeAdditionalBackground", {"index": 0}),
    op("removeAdditionalBackground", {"index": 0}),
    op("setAdditionalBackgroundCode", {"code": "; code", "language": 0}),
    op("setAdditionalBackgroundCode", {"code": "", "language": 0}),
    op("setAudioSelectCode", {"code": "int x;", "language": 1}),
    op("setBoardAudio", {"audioChanges": {"gameAudioIndex": 7}}),
    op("setBoardAudio", {"audioChanges": {"audioType": 1}}),
    op("setBoardAudio", {"audioChanges": {"customAudioIndex": 0}}),
    op("setBoardAudio", {"audioChanges": {"customAudioIndex": 0, "midiName": "song.mid",
                                          "midiData": "data:audio/midi;base64,AAAA",
                                          "soundbankIndex": 2}}),
    op("setBoardAudio", {"audioChanges": {"customAudioIndex": 1, "midiName": "b.mid"}}),
    op("setBoardAudio", {"audioChanges": {"customAudioIndex": 0, "delete": True}}),
    op("setBoardAudio", {"audioChanges": {"audioType": 0}}),
    UNDO, UNDO, UNDO, UNDO, UNDO, UNDO, UNDO, UNDO, UNDO, UNDO,
    REDO, REDO, REDO,
]})

scenarios.append({"name": "board list", "boards": [{"default": [1, "NORMAL"]},
                                                     {"default": [2, "NORMAL"]},
                                                     {"default": [3, "DUEL"]}],
                  "romBoards": [{"default": [3, "NORMAL"]}], "steps": [
    op("setCurrentBoard", {"index": 1, "rom": False}),
    op("copyCurrentBoard", {}),
    op("copyCurrentBoard", {"makeCurrent": True}),
    op("setBoardName", {"name": "Copied"}),
    UNDO, UNDO, REDO,
    op("deleteBoard", {"boardIndex": 0}),
    op("deleteBoard", {"boardIndex": 99}),
    op("deleteBoard", {"boardIndex": 1}),
    op("setCurrentBoard", {"index": 0, "rom": True}),
    op("copyCurrentBoard", {}),
    op("copyCurrentBoard", {"makeCurrent": True}),
    op("setCurrentBoard", {"index": 0, "rom": True}),
    op("setSpaceRotation", {"spaceIndex": 0, "angleYAxisDeg": 1}),        # ROM board: error
    op("addBoard", {"board": {"default": [1, "NORMAL"]}}),
    op("addBoard", {"board": {"default": [2, "NORMAL"]}, "rom": True}),
    op("clearBoardsFromROM"),
    op("setCurrentBoard", {"index": 2, "rom": False}),
    op("deleteBoard", {"boardIndex": 2}),
    op("deleteBoard", {"boardIndex": 0}),
    op("deleteBoard", {"boardIndex": 0}),
    op("deleteBoard", {"boardIndex": 0}),
    op("deleteBoard", {"boardIndex": 0}),
    op("deleteBoard", {"boardIndex": 0}),
    UNDO, UNDO,
]})

scenarios.append({"name": "events", "boards": [{"default": [1, "NORMAL"]}], "steps": [
    *spaces((100, 100), (200, 100), (300, 100), (400, 100), (500, 100)),
    op("addEventToLibrary", {"event": {"language": 0, "asm": EVENT_ASM}}),
    op("addEventToLibrary", {"event": {"language": 0, "asm": EVENT2_ASM}}),
    op("addEventToSpaces", {"event": {"id": "Test Event", "activationType": 3,
                                      "executionType": 1, "custom": True},
                            "spaceIndices": [1, 2]}),
    op("setSpaceEventsEventParameter", {"spaceIndices": [1, 2], "eventIndices": [0, 0],
                                        "name": "target", "value": 4}),
    op("setSpaceEventsEventParameter", {"spaceIndices": [1], "eventIndices": [0],
                                        "name": "spaces", "value": [0, 3, 4, 2]}),
    op("setSpaceEventsActivationType", {"spaceIndices": [2], "eventIndices": [0],
                                        "activationType": 1}),
    op("setSelectedSpace", 3),
    op("addEventToSpace", {"event": {"id": "Other Event", "activationType": 3,
                                     "executionType": 2, "custom": True}}),
    op("addEventToSpace", {"event": {"id": "Test Event", "activationType": 3,
                                     "executionType": 1, "custom": True,
                                     "parameterValues": {"target": 2}}, "toStart": True}),
    op("setSpaceEventEventParameter", {"eventIndex": 0, "name": "count", "value": 3}),
    op("setSpaceEventActivationType", {"eventIndex": 1, "activationType": 1}),
    op("removeSpace", {"index": 3}),
    op("removeSpace", {"index": 0}),
    op("addEventToBoard", {"event": {"id": "Test Event", "activationType": -2,
                                     "executionType": 1, "custom": True}}),
    op("setBoardEventEventParameter", {"eventIndex": 0, "name": "target", "value": 1}),
    op("setBoardEventActivationType", {"eventIndex": 0, "activationType": -3}),
    op("removeSpace", {"index": 1}),
    op("setSelectedSpace", 0),
    op("removeEventFromSpace", {"eventIndex": 0}),
    op("removeEventsFromSpaces", {"eventIndices": [0], "spaceIndices": [1]}),
    op("removeEventFromBoard", {"eventIndex": 0}),
    op("removeEventFromBoard", {"eventIndex": 5}),
    op("includeEventInBoard", {"event": {"language": 0, "asm": EVENT2_ASM}}),
    op("excludeEventFromBoard", {"eventId": "Test Event"}),
    op("changeCurrentEvent", {"id": "Other Event", "type": 1}),
    UNDO, UNDO, UNDO, REDO,
    op("removeEventFromLibrary", {"eventId": "Other Event"}),
]})

scenarios.append({"name": "special spaces (adapters)", "boards": [{"default": [1, "NORMAL"]},
                                                                   {"default": [2, "NORMAL"]},
                                                                   {"default": [3, "NORMAL"]}],
                  "steps": [
    op("addSpace", {"x": 10, "y": 10, "type": STAR}),
    op("addSpace", {"x": 20, "y": 10, "type": CHANCE}),
    op("addSpace", {"x": 30, "y": 10, "type": BANK}),
    op("setCurrentBoard", {"index": 1, "rom": False}),
    op("addSpace", {"x": 10, "y": 10, "type": BANK}),
    op("addSpace", {"x": 20, "y": 10, "type": ITEM}),
    op("addSpace", {"x": 30, "y": 10, "type": BATTLE}),
    op("addSpace", {"x": 40, "y": 10, "type": OTHER, "subtype": 7}),
    op("addSpace", {"x": 50, "y": 10, "type": OTHER, "subtype": 5}),
    op("addSpace", {"x": 60, "y": 10, "type": STAR}),
    op("setCurrentBoard", {"index": 2, "rom": False}),
    op("addSpace", {"x": 10, "y": 10, "type": BANK}),
    op("addSpace", {"x": 20, "y": 10, "type": ITEM}),
    op("addSpace", {"x": 40, "y": 10, "type": OTHER, "subtype": 8}),
    op("addSpace", {"x": 60, "y": 10, "type": STAR}),
    op("removeSpace", {"index": 1}),
]})

out = Path(__file__).with_name("board_state_scenarios.json")
out.write_text(json.dumps(scenarios, indent=1))
print("wrote", out)
