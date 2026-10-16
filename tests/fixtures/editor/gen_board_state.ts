// Differential reference for partyplanner64/editor (boardState.ts + store.ts's redux-undo).
// Usage: node ref/run.mjs ref/editor_board_state.ts <scenarios.json> <out.json>
import * as fs from "fs";
import { createHash } from "crypto";
import "../packages/lib/events/builtin/events.include";
import { setEventLibraryImplementation } from "../packages/lib/events/EventLibrary";
import { createCustomEvent } from "../packages/lib/events/customevents";
import { fixPotentiallyOldBoard } from "../packages/lib/boards";
import { store } from "../apps/partyplanner64/store";
import * as bs from "../apps/partyplanner64/boardState";
import { _makeDefaultBoard } from "../apps/partyplanner64/boards";
import { ReduxEventLibrary } from "../apps/partyplanner64/events/ReduxEventLibrary";
import { ActionCreators } from "redux-undo";

setEventLibraryImplementation(new ReduxEventLibrary());

const [scenarioFile, outFile] = process.argv.slice(2);
const scenarios = JSON.parse(fs.readFileSync(scenarioFile, "utf-8"));

function makeBoard(spec: any) {
  if (spec.default) return _makeDefaultBoard(spec.default[0], spec.default[1]);
  return fixPotentiallyOldBoard(JSON.parse(JSON.stringify(spec.board)));
}

function snapshot() {
  const s: any = store.getState().data;
  const p = s.present;
  const customEvents: any = {};
  for (const id in p.eventLibrary) {
    if (p.eventLibrary[id].custom) customEvents[id] = p.eventLibrary[id].asm;
  }
  // Image data URLs are shortened to a hash (the Python test does the same).
  return JSON.parse(JSON.stringify({
    boards: p.boards,
    romBoards: p.romBoards,
    currentBoardIndex: p.currentBoardIndex,
    currentBoardIsROM: p.currentBoardIsROM,
    selectedSpaceIndices: Object.keys(p.selectedSpaceIndices).map(Number).sort((a, b) => a - b),
    highlightedSpaceIndices: p.highlightedSpaceIndices,
    temporaryConnections: p.temporaryConnections,
    customEvents,
    past: s.past.length,
    future: s.future.length,
  }), (k, v) => typeof v === "string" && v.startsWith("data:image/")
    ? "img:" + createHash("sha1").update(v).digest("hex").slice(0, 12) : v);
}

const actionCreators: any = bs;
const results: any[] = [];
for (const scenario of scenarios) {
  // Reset the singleton store.
  store.dispatch(bs.setBoardsAction({ boards: scenario.boards.map(makeBoard) }));
  store.dispatch(bs.clearBoardsFromROMAction());
  for (const rb of scenario.romBoards || []) {
    const b = makeBoard(rb);
    b._rom = true;
    store.dispatch(bs.addBoardAction({ board: b, rom: true }));
  }
  store.dispatch(bs.setCurrentBoardAction({ index: 0, rom: false }));
  store.dispatch(bs.clearSelectedSpacesAction());
  for (const id in bs.selectEventLibrary(store.getState())) {
    const e = bs.selectEventLibrary(store.getState())[id];
    if (e.custom) store.dispatch(bs.removeEventFromLibraryAction({ eventId: id }));
  }
  store.dispatch(ActionCreators.clearHistory());

  const steps: any[] = [];
  for (const step of scenario.steps) {
    let error: string | null = null;
    try {
      if (step.undo) store.dispatch(ActionCreators.undo());
      else if (step.redo) store.dispatch(ActionCreators.redo());
      else if (step.clear) store.dispatch(ActionCreators.clearHistory());
      else {
        let args = JSON.parse(JSON.stringify(step.args ?? null));
        const name = step.op.endsWith("Action") || step.op === "setTemporaryUIConnections" ? step.op : step.op + "Action";
        if (name === "addEventToLibraryAction" || name === "includeEventInBoardAction") {
          args = { event: createCustomEvent(args.event.language, args.event.asm) };
        }
        if (name === "addBoardAction") args = { ...args, board: makeBoard(args.board) };
        const creator = actionCreators[name];
        if (!creator) throw new Error("No action " + name);
        store.dispatch(args === null ? creator() : creator(args));
      }
    } catch (e: any) {
      error = String(e && e.message || e);
    }
    steps.push({ error: error !== null, state: snapshot() });
  }
  results.push({ name: scenario.name, steps });
}
fs.writeFileSync(outFile, JSON.stringify(results));
console.log("wrote", results.length, "scenarios");
