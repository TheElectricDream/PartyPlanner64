// Reference board files for partyplanner64 import/export tests.
// node ref/run.mjs ref/editor_board_files.ts <out_dir> [python_export.json]
//  - writes <out_dir>/ts_board_export.json: a board exported as header.tsx did;
//  - with a Python export, writes <out_dir>/py_board_reexport.json: that file loaded
//    (JSON.parse + fixPotentiallyOldBoard, as boardSelected/addBoard) and exported again.
import * as fs from "fs";
import "../packages/lib/events/builtin/events.include";
import { setEventLibraryImplementation } from "../packages/lib/events/EventLibrary";
import { createCustomEvent } from "../packages/lib/events/customevents";
import { fixPotentiallyOldBoard } from "../packages/lib/boards";
import { store } from "../apps/partyplanner64/store";
import * as bs from "../apps/partyplanner64/boardState";
import { _makeDefaultBoard } from "../apps/partyplanner64/boards";
import { ReduxEventLibrary } from "../apps/partyplanner64/events/ReduxEventLibrary";

setEventLibraryImplementation(new ReduxEventLibrary());

function stripPrivateProps(obj: any = {}): any {   // header.tsx
  if (typeof obj !== "object") return obj;
  obj = JSON.parse(JSON.stringify(obj));
  for (const prop in obj) {
    if (!obj.hasOwnProperty(prop)) continue;
    if (prop.charAt(0) === "_") delete obj[prop];
    if (typeof obj[prop] === "object" && obj[prop] !== null)
      obj[prop] = stripPrivateProps(obj[prop]);
  }
  return obj;
}

const [outDir, pyExport] = process.argv.slice(2);
const asm = "; NAME: Test Event\n; GAMES: MP1_USA,MP2_USA,MP3_USA\n; EXECUTION: Direct\n; PARAM: Space|target\nJR RA\nNOP\n";
store.dispatch(bs.addEventToLibraryAction({ event: createCustomEvent(0, asm) }));
const board: any = _makeDefaultBoard(3);
board.name = "Ünïcode \"board\" 🎲";
store.dispatch(bs.setBoardsAction({ boards: [fixPotentiallyOldBoard(board)] }));
const d = (a: any) => store.dispatch(a);
for (let i = 0; i < 12; i++) d(bs.addSpaceAction({ x: 50 + i * 37.5, y: 100 + (i % 3) * 20, type: 1 + (i % 3) }));
for (let i = 0; i < 11; i++) d(bs.addConnectionAction({ startSpaceIndex: i, endSpaceIndex: i + 1 }));
d(bs.addConnectionAction({ startSpaceIndex: 10, endSpaceIndex: 2 }));
d(bs.addConnectionAction({ startSpaceIndex: 12, endSpaceIndex: 0 }));
d(bs.setSpaceRotationAction({ spaceIndex: 3, angleYAxisDeg: 45.4 }));
d(bs.setSpacePositionsAction({ spaceIndices: [4], coords: [{ x: 1.25, y: 2.5, z: 3 }] }));
d(bs.setSpaceHostsStarAction({ spaceIndices: [5, 6], hostsStar: true }));
d(bs.addEventToSpacesAction({ event: { id: "Test Event", activationType: 3, executionType: 1, custom: true, parameterValues: { target: 9 } } as any, spaceIndices: [7] }));
d(bs.addEventToBoardAction({ event: { id: "Test Event", activationType: -2, executionType: 1, custom: true } as any }));
d(bs.setAdditionalBackgroundCodeAction({ code: "// c code", language: 1 }));
d(bs.setBoardAudioAction({ audioChanges: { audioType: 1, customAudioIndex: 0, midiName: "a.mid", midiData: "data:audio/midi;base64,TVRoZA==", soundbankIndex: 1 } }));
d(bs.setBoardDescriptionAction({ description: "Two\nlines" }));
const cur: any = bs.selectCurrentBoard(store.getState());
fs.writeFileSync(outDir + "/ts_board_export.json", JSON.stringify(stripPrivateProps({ ...cur, _rom: false, _deadSpace: 3 })));
if (pyExport) {
  const b = fixPotentiallyOldBoard(JSON.parse(fs.readFileSync(pyExport, "utf-8")));
  fs.writeFileSync(outDir + "/py_board_reexport.json", JSON.stringify(stripPrivateProps(b)));
}
console.log("ok");
