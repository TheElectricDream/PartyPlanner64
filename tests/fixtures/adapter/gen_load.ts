// Reference outputs for AdapterBase.loadBoards: boards written by overwriteBoard to a fake ROM
// (as in gen_overwrite.ts) are read back, with and without the stashed board JSON.
// Image parsing is skipped (the fake ROM has no images).
// Everything the adapter writes is recorded: MainFS files, scene overlays and scene bytes,
// strings, background metadata, animation counts and ROM bytes. Image writing
// (onOverwritePromises) is skipped: it resamples images, which Pillow does differently.
import { romhandler } from "../packages/lib/romhandler";
import { getAdapter } from "../packages/lib/adapter/adapters";
import "../packages/lib/events/builtin/events.include";
import { getBoardInfos } from "../packages/lib/adapter/boardinfo";
import { create as createBoardDef } from "../packages/lib/adapter/boarddef";
import { getSymbol } from "../packages/lib/symbols/symbols";
import { parse as parseInst } from "mips-inst";

// Fill the fake ROM with what the stock boards would have: a board def for every board,
// and in each board's scene the values the board info points at and an event table
// reached through a call to EventTableHydrate.
function prefill(game: number, adapter: any, rom: any) {
  const gameId = gameIds[game];
  const mainfs = rom.getMainFS();
  const scenes = rom.getScenes();
  const loop: any = {
    spaces: [0, 1, 2, 1, 1, 2, 1, 1].map((type, i) => ({ type, x: 10 * i, y: 5 * i, z: i })),
    links: { 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 0 },
  };
  const jal = parseInst(`JAL ${getSymbol(gameId, "EventTableHydrate")}`);
  getBoardInfos(gameId)!.forEach((info: any, j: number) => {
    mainfs.write(adapter.boardDefDirectory, info.boardDefFile, createBoardDef(loop, [[0, 1, 2, 3, 4, 5, 6, 7]]));
    if (typeof info.sceneIndex !== "number") return;
    const v: DataView = scenes.getDataView(info.sceneIndex);
    ["koopaSpaceInst", "bowserSpaceInst", "goombaSpaceInst", "booSpaceInst", "toadSpaceInst"].forEach((k, n) => {
      if (info[k]) v.setUint16(info[k] + 2, n + 1);
    });
    const list = (o: any) => (o === undefined ? [] : Array.isArray(o) ? o : [o]);
    for (const off of list(info.starSpaceArrOffset)) for (let i = 0; i < (info.starSpaceCount || 0); i++) v.setUint16(off + 2 * i, (i % 7) + 1);
    for (const off of list(info.toadSpaceArrOffset)) for (let i = 0; i < (info.starSpaceCount || 0); i++) v.setUint16(off + 2 * i, (i % 5) + 2);
    if (info.boosLoopFnOffset) {
      v.setUint16(info.boosLoopFnOffset + 0x2a, 2);
      v.setInt16(info.boosReadbackFnOffset + 0xd2, 0x1000);
      v.setUint16(0x1000, 5);
      v.setUint16(0x1002, 6);
    }
    for (const off of list(info.bankArrOffset)) for (let i = 0; i < (info.bankCount || 0); i++) v.setUint16(off + 2 * i, 7 + i);
    for (const off of list(info.bankCoinArrOffset)) for (let i = 0; i < (info.bankCount || 0); i++) v.setUint16(off + 2 * i, 1 + i);
    for (const off of list(info.itemShopArrOffset)) for (let i = 0; i < (info.itemShopCount || 0); i++) v.setUint16(off + 2 * i, 2 + i);
    for (const off of list(info.booArrOffset)) for (let i = 0; i < (info.booCount || 0); i++) v.setUint16(off + 2 * i, 3 + i);
    if (info.audioIndexOffset) v.setUint16(info.audioIndexOffset, 0x12 + j);
    v.setUint32(0x100, 0x3c048010); // LUI A0, 0x8010
    v.setUint32(0x104, jal);
    v.setUint32(0x108, 0x24840800); // ADDIU A0, A0, 0x800
    v.setInt16(0x800, 1); v.setUint32(0x804, 0x80100900); v.setInt16(0x808, -1);
    v.setUint16(0x900, 1); v.setUint16(0x902, 1); v.setUint32(0x904, 0x80100a00);
  });
}
import * as fs from "fs";

import * as crypto from "crypto";
const hex = (b: ArrayBufferLike) => {
  const data = Buffer.from(new Uint8Array(b));
  if (data.length <= 0x1000) return data.toString("hex");
  return `len=${data.length} sha1=${crypto.createHash("sha1").update(data).digest("hex")}`;
};
const fullHex = (b: ArrayBufferLike) => Buffer.from(new Uint8Array(b)).toString("hex");
function runs(buf: ArrayBufferLike) {
  const u8 = new Uint8Array(buf);
  const out: [number, string][] = [];
  let i = 0;
  while (i < u8.length) {
    if (u8[i] === 0) { i++; continue; }
    let j = i;
    while (j < u8.length && (u8[j] !== 0 || (j + 1 < u8.length && u8[j + 1] !== 0) || (j + 2 < u8.length && u8[j + 2] !== 0) || (j + 3 < u8.length && u8[j + 3] !== 0))) j++;
    out.push([i, Buffer.from(u8.slice(i, j)).toString("hex")]);
    i = j;
  }
  return out;
}

class Rec { log: any[] = []; }
function makeRom(game: string, rec: Rec) {
  const files = new Map<string, ArrayBuffer>();
  const mainfs = {
    __files: files,
    get(d: number, f: number) { const k = `${d}/${f}`; if (!files.has(k)) files.set(k, new ArrayBuffer(0x2000)); return files.get(k)!; },
    has(d: number, f: number) { return files.has(`${d}/${f}`); },
    write(d: number, f: number, c: ArrayBuffer) {
      files.set(`${d}/${f}`, c);
      rec.log.push(["mainfs.write", d, f, hex(c)]);
      if (fullDir) fs.writeFileSync(`${fullDir}/${game}_${d}_${f}.hex`, fullHex(c));
    },
  };
  const sceneBufs: { [i: number]: ArrayBuffer } = {};
  const scenes = {
    getInfo(i: number) {
      const base = 0x80100000;
      return { rom_start: 0x200000 + i * 0x40000, rom_end: 0x200000 + i * 0x40000 + 0x30000, ram_start: base,
        code_start: base, code_end: base + 0x20000, rodata_start: base + 0x20000, rodata_end: base + 0x28000,
        bss_start: base + 0x28000, bss_end: base + 0x30000 };
    },
    getDataView(i: number) { if (!sceneBufs[i]) sceneBufs[i] = new ArrayBuffer(0x30000); return new DataView(sceneBufs[i]); },
    getCodeDataView(i: number) { if (!sceneBufs[i]) sceneBufs[i] = new ArrayBuffer(0x30000); return new DataView(sceneBufs[i]); },
    replace(i: number, buf: ArrayBuffer, info: any) {
      rec.log.push(["scenes.replace", i, hex(buf), info]);
      if (fullDir) fs.writeFileSync(`${fullDir}/${game}_scene${i}.hex`, fullHex(buf));
    },
  };
  const hvqfs = {
    updateMetadata(dir: number, values: any) { rec.log.push(["hvqfs.updateMetadata", dir, JSON.parse(JSON.stringify(values))]); },
    writeBackground(dir: number) { rec.log.push(["hvqfs.writeBackground", dir]); },
    getDirectoryCount() { return 100; },
    readBackground(dir: number) { return { ...BG, src: "bg" + dir }; },
  };
  const strings = { write(i: number, buf: ArrayBuffer) { rec.log.push(["strings.write", i, hex(buf)]); }, read(i: number) { return STRS[game] + i; } };
  const strings3 = { write(l: string, d: number, i: number, buf: ArrayBuffer) { rec.log.push(["strings3.write", l, d, i, hex(buf)]); },
    read(l: string, d: number, i: number) { return STRS[game] + d + "/" + i; } };
  const animationfs = { setSetEntryCount(s: number, c: number) { rec.log.push(["animationfs.setSetEntryCount", s, c]); } };
  const audio = { getSequenceTable() { return { midis: [] }; } };
  const rom = {
    getGame: () => game, getMainFS: () => mainfs, getScenes: () => scenes, getHVQFS: () => hvqfs,
    getStrings: () => strings, getStrings3: () => strings3, getAnimationFS: () => animationfs, getAudio: () => audio,
  };
  return { rom, sceneBufs };
}

const STRS: any = {
  CLBE: "\u3014<GREEN>Fake Board<DEFAULT>\nFirst line\nSecond line\n<BLUE>Map Difficulty  \u3009\u3009\u3009<DEFAULT>",
  NMWE: "\u3014<BLUE>Fake Board\u0019<PURPLE>\t\tDifficulty\u0019 : \u3013\u3013\nFirst line\nSecond line",
  NMVE: "\u3014<GREEN>xFake Board{5}\nFirst line\nSecond \u3013 line",
};
let BG: any = {};
const gameIds: any = { 1: "CLBE", 2: "NMWE", 3: "NMVE" };
const fullDir = process.argv[3]; // Optional: also save full buffers here, for debugging.
const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const results: any = {};
const SAVED: any = {};
for (const g of ["CLBE", "NMWE", "NMVE"]) SAVED[g] = getBoardInfos(g as any)!.map((i: any) => i.spaceEventTables === undefined ? undefined : JSON.stringify(i.spaceEventTables));
(async () => {
  for (const tc of input.cases) {
    const rec = new Rec();
    const { rom, sceneBufs } = makeRom(gameIds[tc.game], rec);
    const romBuf = new ArrayBuffer(0xd0000);
    (romhandler as any).getRom = () => rom;
    (romhandler as any).getROMGame = () => gameIds[tc.game];
    (romhandler as any).getGameVersion = () => tc.game;
    (romhandler as any).getDataView = () => new DataView(romBuf);
    BG = { ...tc.board.bg };
    const adapter: any = getAdapter(tc.game, {});
    prefill(tc.game, adapter, rom);
    rec.log.length = 0;
    adapter.onOverwritePromises = async () => {};
    await adapter.overwriteBoard(tc.boardIndex, JSON.parse(JSON.stringify(tc.board)));
    for (const stashed of [true, false]) {
      const files: Map<string, ArrayBuffer> = (rom.getMainFS() as any).__files;
      if (!stashed) {
        // Forget the stashed board JSON, so the board def and events are parsed.
        for (const info of [ [10, 423], [10, 429], [10, 683], [19, 619], [19, 621] ]) files.delete(`${info[0]}/${info[1]}`);
      }
      const loader: any = getAdapter(tc.game, {});
      loader.onParseBoardSelectImg = () => {};
      loader.onParseBoardLogoImg = () => {};
      loader._parseBoardSelectIcon = () => {};
      loader._readAnimationBackgrounds = () => {};
      const res: any = {};
      try {
        res.boards = JSON.parse(JSON.stringify(loader.loadBoards()));
      } catch (e: any) {
        res.error = String(e && e.message || e).slice(0, 2000);
      }
      res.spaceEventTables = getBoardInfos(gameIds[tc.game])!.map((info: any) => info.spaceEventTables || null);
      results[tc.name + (stashed ? ":stashed" : ":parsed")] = res;
      // Start the next load (and case) with the board infos as they were.
      getBoardInfos(gameIds[tc.game])!.forEach((info: any, j: number) => {
        if (SAVED[gameIds[tc.game]][j] === undefined) delete info.spaceEventTables;
        else info.spaceEventTables = JSON.parse(SAVED[gameIds[tc.game]][j]);
      });
    }
  }
  console.log(JSON.stringify(results));
})();
