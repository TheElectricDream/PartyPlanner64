// Assembles printed instructions (from inst.json) one line at a time, in JS, as reference.
import { assemble } from "mips-assembler";
import * as fs from "fs";
const inst = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const lines: string[] = [];
for (const c of inst.printCases) if (typeof c.out === "string") lines.push(c.out);
for (const c of inst.parseCases) lines.push(c.s);
const picked = lines.filter((_, i) => i % 3 === 0);
const out = picked.map((line) => {
  try {
    const hex = Buffer.from(new Uint8Array(assemble(".org 0x80001000\n" + line) as ArrayBuffer)).toString("hex");
    const text = (assemble(".org 0x80001000\n" + line, { text: true }) as string[]).join("|");
    return [line, hex, text];
  } catch (e: any) { return [line, null, String(e.message)]; }
});
console.log(JSON.stringify(out));
