import "../packages/lib/events/builtin/events.include";
import { getEventsInLibrary } from "../packages/lib/events/EventLibrary";
const evs = getEventsInLibrary();
const out: any[] = [];
for (const id in evs) {
  const e: any = evs[id];
  out.push({ key: id, ...JSON.parse(JSON.stringify(e)), hasParse: !!e.parse, hasWrite: !!e.write });
}
console.log(JSON.stringify(out, null, 1));
