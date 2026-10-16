// Reference outputs of patches/gameshark for the Python port's tests.
import { Parser } from "../packages/lib/patches/gameshark/parser";
import { Compiler } from "../packages/lib/patches/gameshark/compiler";
import { currentCheats, resetCheats } from "../packages/lib/patches/gameshark/cheats";
import { applyHook, romSupportsCheats } from "../packages/lib/patches/gameshark/hook";
import { romhandler } from "../packages/lib/romhandler";
import { Game } from "../packages/lib/types";

const codeStrings = [
  "810657EE 0005",
  "810657EE 0005\nD00657EE 00FF 800657EF 1234",
  "D1012345 FFFF  D2012345 0001\n  D3012346 8000 80123456 0x7F",
  "",
  "   ",
  "810657EE",
  "00000000 0000",
  "zz 0001",
  "12345678 0001",
  "81000000 zz",
  "80000000 zz",
  "-81000000 0001",
];
const parsed: any[] = [];
for (const s of codeStrings) {
  const codes = Parser.parse(s);
  let compiled: any = null;
  if (codes) {
    try {
      const buf = new Compiler().compile(codes);
      compiled = buf ? Buffer.from(new Uint8Array(buf)).toString("hex") : null;
    } catch (e: any) { compiled = { error: String(e.message) }; }
  }
  parsed.push({ s, codes, compiled });
}

const hooks: any[] = [];
for (const [game, version] of [[Game.MP1_USA, 1], [Game.MP2_USA, 2], [Game.MP3_USA, 3], [Game.MP1_JPN, 1]] as [Game, number][]) {
  const writes: any[] = [];
  (romhandler as any).getGameVersion = () => version;
  (romhandler as any).getROMGame = () => game;
  (romhandler as any).getRom = () => ({ getMainFS: () => ({ write: (d: number, f: number, buf: ArrayBuffer) => {
    writes.push({ d, f, hex: Buffer.from(new Uint8Array(buf)).toString("hex") }); } }) });
  const rom = new Uint8Array(0xE0000);
  for (let i = 0; i < rom.length; i++) rom[i] = (i * 13 + (i >> 8)) & 0xFF;
  const before = rom.slice();
  resetCheats();
  applyHook(rom.buffer); // No cheats: nothing happens.
  for (const s of [codeStrings[1], codeStrings[2]]) currentCheats.push(new Compiler().compile(Parser.parse(s)!)!);
  applyHook(rom.buffer);
  const diffs: any[] = [];
  for (let i = 0; i < rom.length; i++) {
    if (rom[i] !== before[i]) {
      const last = diffs[diffs.length - 1];
      if (last && last.offset + last.bytes.length / 2 === i) last.bytes += rom[i].toString(16).padStart(2, "0");
      else diffs.push({ offset: i, bytes: rom[i].toString(16).padStart(2, "0") });
    }
  }
  hooks.push({ game, version, supported: romSupportsCheats(), writes, diffs });
}
console.log(JSON.stringify({ parsed, hooks }));
