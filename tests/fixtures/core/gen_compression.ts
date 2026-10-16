// Generates tests/fixtures/core/compression.json: compress/decompress reference outputs.
import { compress, decompress } from "../packages/lib/utils/compression";
import * as fs from "fs";

let seed = 12345;
function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x80000000; }
function randBytes(n: number, alphabet = 256) { const a = new Uint8Array(n); for (let i = 0; i < n; i++) a[i] = Math.floor(rnd() * alphabet); return a; }
function runs(n: number) { const a = new Uint8Array(n); let i = 0; while (i < n) { const v = Math.floor(rnd() * 4); const len = 1 + Math.floor(rnd() * 300); for (let j = 0; j < len && i < n; j++) a[i++] = v; } return a; }
const b64 = (u: Uint8Array) => Buffer.from(u).toString("base64");

// Note: compress(5) throws in the TypeScript for any non-empty input (it reads past the end).

const inputs: Uint8Array[] = [];
for (const n of [0, 1, 2, 3, 7, 8, 9, 31, 32, 33, 64, 127, 128, 129, 255, 256, 1000]) {
  inputs.push(randBytes(n));
  inputs.push(randBytes(n, 2));
  inputs.push(runs(n));
  inputs.push(new Uint8Array(n));
}
inputs.push(randBytes(4096)); inputs.push(runs(4096));
const compressCases: any[] = [];
for (const input of inputs) {
  for (const type of [0, 1, 2, 3, 4, 5]) {
    let out: any;
    try {
      const view = new DataView(input.buffer);
      out = b64(new Uint8Array(compress(type, view) as ArrayBuffer));
    } catch (e) { out = null; }
    compressCases.push({ type, input: b64(input), output: out });
  }
}

// Decompression of random streams (exercises back-references and window wrap).
const decompressCases: any[] = [];
for (const type of [1, 2, 3, 5]) {
  let made = 0, tries = 0;
  while (made < 40 && tries < 20000) {
    tries++;
    const len = 4 + Math.floor(rnd() * 600);
    const stream = rnd() < 0.5 ? randBytes(len) : randBytes(len, 64);
    const size = Math.floor(rnd() * len * 2.5);
    try {
      const out = decompress(type, new DataView(stream.buffer), size);
      decompressCases.push({ type, input: b64(stream), size, output: b64(new Uint8Array(out)), compressedSize: (out as any).compressedSize });
      made++;
    } catch (e) {}
  }
}
fs.writeFileSync(process.argv[2], JSON.stringify({ compress: compressCases, decompress: decompressCases }));
console.log(compressCases.length, decompressCases.length);
