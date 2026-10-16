// Generates tests/fixtures/core/strings.json: strToBytes with each game's character map.
import * as fs from "fs";
import { romhandler, ROM } from "../packages/lib/romhandler";
import { strToBytes } from "../packages/lib/fs/strings";
import { getROMAdapter } from "../packages/lib/adapter/adapters";
const out: any = {};
const texts = ["Hello World!", "Mario's 10 coins　", "<RED>Star</RED>\n〉 x3 〈", "éü 😀 end", "", "〇【】 Z"];
for (const id of ["CLBE", "NMWE", "NMVE"]) {
  const buf = new Uint8Array(0x40); buf.set([0x80, 0x37, 0x12, 0x40]); for (let i = 0; i < 4; i++) buf[0x3b + i] = id.charCodeAt(i);
  romhandler._rom = new ROM(buf.buffer);
  out[id] = { map: getROMAdapter({})!.getCharacterMap(), results: texts.map(t => [t, strToBytes(t)]) };
}
fs.writeFileSync(process.argv[2], JSON.stringify(out));
