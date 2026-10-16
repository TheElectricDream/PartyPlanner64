// Outputs of every built-in event's write() for a set of event instances.
import "../packages/lib/events/builtin/events.include";
import { getEventsInLibrary } from "../packages/lib/events/EventLibrary";
import { Gate3 } from "../packages/lib/events/builtin/MP3/U/GateEvent3";
import { GateClose3 } from "../packages/lib/events/builtin/MP3/U/GateCloseEvent3";
import { StarEvent1 } from "../packages/lib/events/builtin/MP1/U/StarEvent1";
const evs: any = { ...getEventsInLibrary(), GATE3: Gate3, GATECLOSE3: GateClose3, STAR1: StarEvent1 };
const pvs: any[] = [
  {},
  { chain: 3, spaceIndex: 2, prevSpace: 7, chains: [4, 5], gateIndex: 1,
    spaceIndexArgs: [10, 11], chainArgs: [1, 2], altChain: [6, 9], reverse: true, hasgate: false },
  { chain: 0, spaceIndex: 0, prevSpace: 0, chains: [1], gateIndex: 0,
    spaceIndexArgs: [5], chainArgs: [3], altChain: [], reverse: false },
  { chains: [], spaceIndexArgs: [], chainArgs: [] },
];
const out: any[] = [];
const results: any[] = [];
const resultIndex: any = {};
for (const id in evs) {
  const e = evs[id];
  if (!e.write) continue;
  for (const gameVersion of [1, 2, 3]) {
    for (const boardIndex of [0, 1, 9]) {
      for (let p = 0; p < pvs.length; p++) {
        const inst = { id, activationType: 1, executionType: 1, parameterValues: pvs[p] };
        let result: any;
        try {
          result = e.write(new DataView(new ArrayBuffer(16)), inst, { gameVersion, boardIndex }, {});
          if (result === undefined) result = "__undefined__";
        } catch (err: any) {
          result = { error: err.constructor.name + ": " + err.message };
        }
        const key = JSON.stringify(result);
        if (!(key in resultIndex)) { resultIndex[key] = results.length; results.push(result); }
        out.push([id, gameVersion, boardIndex, p, resultIndex[key]]);
      }
    }
  }
}
console.log(JSON.stringify({ pvs, results, out }));
