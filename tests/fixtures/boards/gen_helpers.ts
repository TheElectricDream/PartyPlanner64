// boards.ts helpers on the synthetic boards (fixtures/validation/boards.json) and old-format boards.
// Usage: node ref/run.mjs ref/boards_helpers.ts <fixtures dir> > boards/helpers.json
import * as fs from "fs";
import * as path from "path";
import "../packages/lib/events/builtin/events.include";
import {
  fixPotentiallyOldBoard, hasConnection, getConnections, addConnectionInternal, getBoardEvent,
  getAdditionalBackgroundCode, getAudioSelectCode, getDeadEnds, getStartSpaceIndex, getSpacesOfType,
  getSpacesOfSubType, getSpacesWithEvent, forEachEvent, forEachEventParameter, addEventToSpaceInternal,
  supportsAnimationBackgrounds, supportsAdditionalBackgrounds, getSpaceIndex,
} from "../packages/lib/boards";
import { getEventsInLibrary } from "../packages/lib/events/EventLibrary";
import { createEventInstance, getEvent, getAvailableEvents } from "../packages/lib/events/events";
import { createCustomEvent } from "../packages/lib/events/customevents";

const dir = process.argv[2];
const boards = JSON.parse(fs.readFileSync(path.join(dir, "validation", "boards.json"), "utf8"));
const oldBoards = JSON.parse(fs.readFileSync(path.join(dir, "boards", "old_boards.json"), "utf8"));
console.warn = () => {};
const out: any = { boards: {}, old: {}, available: {} };
for (const name of Object.keys(boards).sort()) {
  const b = boards[name];
  const n = b.spaces.length;
  const r: any = {};
  r.deadEnds = getDeadEnds(b);
  r.start = getStartSpaceIndex(b);
  r.types = [...Array(21).keys()].map((t) => getSpacesOfType(t, b));
  r.subtypes = [...Array(9).keys()].map((t) => getSpacesOfSubType(t, b));
  r.withBank = getSpacesWithEvent("BANK", b);
  r.connections = [];
  r.has = [];
  for (let i = -1; i <= Math.min(n, 12); i++) {
    r.connections.push(getConnections(i, b));
    const row = [hasConnection(i, "*", b), hasConnection(i, null as any, b)];
    for (let j = 0; j <= Math.min(n, 12); j++) row.push(hasConnection(i, j, b));
    r.has.push(row);
  }
  const visits: any[] = [];
  forEachEvent(b, (ev, ei, space, si) => visits.push([ev.id, ei, si === undefined ? null : si]));
  r.visits = visits;
  const params: any[] = [];
  try {
    forEachEventParameter(b, getEventsInLibrary(), (p, ev, ei, space, si) => params.push([p.name, p.type, ev.id, ei, si === undefined ? null : si]));
    r.params = params;
  } catch (e) { r.params = { error: String(e) }; }
  r.boardEvents = Object.keys(b.events).concat(["missing"]).map((id) => getBoardEvent(b, id));
  r.bgCode = getAdditionalBackgroundCode(b);
  r.audioCode = getAudioSelectCode(b);
  r.supports = [supportsAnimationBackgrounds(b), supportsAdditionalBackgrounds(b), getSpaceIndex(b.spaces[2], b), getSpaceIndex({} as any, b)];
  const c = JSON.parse(JSON.stringify(b));
  const ops = [[0, 0], [0, 1], [0, 2], [0, 3], [0, 2], [7, 1], [7, -1], [-1, 3], [8, 2], [8, 3], [8, 4], [99, 1]];
  for (const [s, e] of ops) addConnectionInternal(s, e, c);
  r.afterAdds = c.links;
  out.boards[name] = r;
}
for (const name of Object.keys(oldBoards).sort()) {
  out.old[name] = fixPotentiallyOldBoard(JSON.parse(JSON.stringify(oldBoards[name])));
}
// Adding events to spaces (custom events get their code included in the board).
const b = JSON.parse(JSON.stringify(boards.mp3_custom_events));
const lib = getEventsInLibrary();
const custom = createCustomEvent(0, b.events["Main Entry"].code);
const inst = createEventInstance(custom, { parameterValues: { enabled: true } });
const ce = getEvent("CRLF Event", b, lib);
b.events = {};
addEventToSpaceInternal(b, b.spaces[0], inst, true, { ...lib, [custom.id]: custom });
addEventToSpaceInternal(b, b.spaces[0], createEventInstance(lib.BANK), false, lib);
addEventToSpaceInternal(b, b.spaces[3], createEventInstance(lib.BOO, { activationType: 3 } as any), false, lib);
out.added = { events: b.events, spaces: [b.spaces[0], b.spaces[3]], crlf: JSON.parse(JSON.stringify(ce)) };
for (const g of [1, 2, 3]) out.available[g] = getAvailableEvents({ game: g } as any).map((e) => e.id);
process.stdout.write(JSON.stringify(out));
