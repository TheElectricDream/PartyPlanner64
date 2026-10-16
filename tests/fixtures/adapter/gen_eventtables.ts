// Reference outputs for SpaceEventTable and SpaceEventList (adapter/eventtable.ts, eventlist.ts).
import { SpaceEventTable } from "../packages/lib/adapter/eventtable";
import { SpaceEventList, createSpaceEventListLabel } from "../packages/lib/adapter/eventlist";

const hex = (b: ArrayBuffer) => Buffer.from(new Uint8Array(b)).toString("hex");
const out: any = {};

// Table: insertion order mixes negative and positive indices.
const tableEntries: [number, number][] = [
  [5, 0x80110000], [-2, 0x807b0010], [0, 0x80110010], [12, 0x80110020], [-5, 0x807b0040], [3, 0x80110030],
];
const table = new SpaceEventTable();
for (const [i, a] of tableEntries) table.add(i, a);
table.add(0, 0x80110018); // Replacing keeps the position.
const tableBuf = new ArrayBuffer(table.byteLength() + 16);
const written = table.write(tableBuf, 8);
out.table = {
  entries: tableEntries,
  written,
  byteLength: table.byteLength(),
  buffer: hex(tableBuf),
  assembly: table.getAssembly(),
};
const parsedTable = new SpaceEventTable();
parsedTable.parse(tableBuf, 8);
const parsedEntries: any[] = [];
parsedTable.forEach((e: any) => parsedEntries.push(e));
out.table.parsed = parsedEntries;

// List.
const list = new SpaceEventList(7);
list.add(1, 2, 0x807b0100);
list.add(3, 1, 0x807b0200);
list.add(8, 2, 0x80110300);
list.setAddress(1, -0x7f84fe00);
const listBuf = new ArrayBuffer(list.byteLength() + 4);
out.list = {
  written: list.write(listBuf, 4),
  byteLength: list.byteLength(),
  buffer: hex(listBuf),
  assembly: list.getAssembly(),
  staticByteLength: SpaceEventList.byteLength(5),
};
const parsedList = new SpaceEventList();
parsedList.parse(listBuf, 4);
const parsedListEntries: any[] = [];
parsedList.forEach((e: any) => parsedListEntries.push([e.activationType, e.executionType, e.address]));
out.list.parsed = parsedListEntries;

const symList = new SpaceEventList(-5);
symList.add(7, 1, 0);
symList.add(7, 1, "__PP64_INTERNAL_CURSE_POISON_DICEROLL_EVENT");
out.symList = { assembly: symList.getAssembly(), count: symList.count() };
try {
  symList.write(new ArrayBuffer(64), 0);
} catch (e: any) {
  out.symList.writeError = e.message;
}
out.labels = [createSpaceEventListLabel(0), createSpaceEventListLabel(-3), createSpaceEventListLabel(42)];
console.log(JSON.stringify(out));
