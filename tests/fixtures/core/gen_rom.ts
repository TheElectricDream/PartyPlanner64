// Generates tests/fixtures/core/rom_<game>.json(.gz parts): a synthetic ROM for each
// of MP1/MP2/MP3 (USA), built by the TypeScript's own saveROM from injected file
// system contents, plus what loading it gives and the md5s of saves after a fixed
// list of edits (see tests/lib/test_romhandler.py, which replays them).
// The audio section is replaced by a stub (prototype patch) on both sides.
import * as fs from "fs";
import * as zlib from "zlib";
import * as crypto from "crypto";
import { ROM, romhandler } from "../packages/lib/romhandler";
import { Scenes } from "../packages/lib/fs/scenes";
import { MainFS } from "../packages/lib/fs/mainfs";
import { Strings, StringTable } from "../packages/lib/fs/strings";
import { Strings3 } from "../packages/lib/fs/strings3";
import { HVQFS } from "../packages/lib/fs/hvqfs";
import { Animationfs } from "../packages/lib/fs/animationfs";
import { Audio } from "../packages/lib/fs/audio";
import { compress, decompress } from "../packages/lib/utils/compression";
import { getROMAdapter } from "../packages/lib/adapter/adapters";
import { setCreateCanvas, setCreateImage } from "../packages/lib/utils/canvas";
import { createCanvasNode, createImageNode } from "../apps/cli/CanvasImpl";
setCreateCanvas(createCanvasNode as any);
setCreateImage(createImageNode as any);

// Audio stub (same in the Python test).
(Audio.prototype as any).extract = function () {};
(Audio.prototype as any).getByteLength = function () { return 0x30; };
(Audio.prototype as any).pack = function (buf: ArrayBuffer, off: number) {
  const u = new Uint8Array(buf); for (let i = 0; i < 0x30; i++) u[off + i] = (0xa0 + i) & 0xff; return 0x30;
};
(Audio.prototype as any).setROMOffset = function (off: number, buf: ArrayBuffer) { new DataView(buf).setUint32(0x100, off); };

let seed = 4242;
function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
function randBytes(n: number, alphabet = 256) { const a = new Uint8Array(n); for (let i = 0; i < n; i++) a[i] = Math.floor(rnd() * alphabet); return a; }
const md5 = (b: ArrayBufferLike | Uint8Array) => crypto.createHash("md5").update(b instanceof Uint8Array ? b : new Uint8Array(b)).digest("hex");
const formula = (n: number, a: number, c: number) => { const u = new Uint8Array(n); for (let i = 0; i < n; i++) u[i] = (i * a + c) & 0xff; return u; };
function rle(data: Uint8Array) { const out: number[] = []; let i = 0; while (i < data.length) { let j = i; while (j < data.length && data[j] === data[i] && j - i < 127) j++; if (j - i >= 2) { out.push(j - i, data[i]); i = j; } else { let k = i; while (k < data.length && k - i < 127 && !(k + 1 < data.length && data[k] === data[k + 1])) k++; if (k === i) k++; out.push(0x80 | (k - i)); for (let m = i; m < k; m++) out.push(data[m]); i = k; } } return new Uint8Array(out); }
function lzStream(type: number, maxLen: number) {
  for (;;) {
    const stream = randBytes(64 + Math.floor(rnd() * maxLen), 64);
    const size = Math.floor(rnd() * stream.length * 2) + 1;
    try { const d = decompress(type, new DataView(stream.buffer), size); return { decompressed: d, compressed: stream.slice(0, (d as any).compressedSize).buffer }; } catch (e) {}
  }
}
function stringTable(strs: Uint8Array[]) {
  let len = 4 + 4 * strs.length; for (const s of strs) { len += 2 + s.length; len += len % 2; }
  const buf = new Uint8Array(len); const v = new DataView(buf.buffer); v.setUint32(0, strs.length);
  let off = 4 + 4 * strs.length;
  strs.forEach((s, i) => { v.setUint32(4 + 4 * i, off); v.setUint16(off, s.length); buf.set(s, off + 2); off += 2 + s.length; off += off % 2; });
  return buf;
}
function stringTableSet(dirs: Uint8Array[][]) {
  const packed = dirs.map((d, i) => { const t = stringTable(d); const type = i % 2; const c = type ? new Uint8Array(compress(1, new DataView(t.buffer)) as ArrayBuffer) : t; return { t, type, c }; });
  let len = 4 + 4 * dirs.length; for (const p of packed) { len += 8 + p.c.length; len += len % 2; }
  const buf = new Uint8Array(len + 64); const v = new DataView(buf.buffer); v.setUint32(0, dirs.length);
  let off = 4 + 4 * dirs.length;
  packed.forEach((p, i) => { v.setUint32(4 + 4 * i, off); v.setUint32(off, p.t.length); v.setUint32(off + 4, p.type); buf.set(p.c, off + 8); off += 8 + p.c.length; off += off % 2; });
  return buf;
}
const textBytes = (s: string) => new Uint8Array(Array.from(s).map(c => c.charCodeAt(0) & 0xff));

const GAMES: any = { MP1: { id: "CLBE", v: 1, maxOvl: { 0x01: 0x240, 0x82: 0x1330 } }, MP2: { id: "NMWE", v: 2 }, MP3: { id: "NMVE", v: 3 } };
const INITIAL_LEN = 0x102000;
const TABLE_OFFSET = 0xe0000;
const OVL_COUNT = 140;

function build(name: string) {
  const g = GAMES[name];
  const initial = new Uint8Array(INITIAL_LEN);
  const iv = new DataView(initial.buffer);
  iv.setUint32(0, 0x80371240);
  initial.set(randBytes(0xfc0), 0x40);
  for (let i = 0x1000; i < INITIAL_LEN; i += 0x400) iv.setUint32(i, Math.floor(rnd() * 0x100000000));
  initial.set(textBytes(g.id), 0x3b);
  const rom = new ROM(initial.buffer);
  romhandler._rom = rom;

  // Scenes: overlays big enough for every patch location.
  const hvqfsTmp = new HVQFS(rom);
  const need: number[] = new Array(OVL_COUNT).fill(0x20);
  for (const p of hvqfsTmp.getPatchOffsets() || []) if (typeof p.ovl === "number") need[p.ovl] = Math.max(need[p.ovl], p.lower + 2, p.upper + 2);
  const scenes = new Scenes(rom);
  const sinfos: any[] = [], ovls: ArrayBuffer[] = [];
  let romPos = INITIAL_LEN;
  for (let i = 0; i < OVL_COUNT; i++) {
    const size = Math.ceil((need[i] + (i % 5) * 16) / 16) * 16;
    const ovl = new Uint8Array(size); for (let k = 0; k < size; k += 64) ovl[k] = Math.floor(rnd() * 256);
    const ram = 0x80200000 + i * 0x40000;
    sinfos.push({ rom_start: romPos, rom_end: romPos + size, ram_start: ram, code_start: ram, code_end: ram + size - 16, rodata_start: ram + size - 16, rodata_end: ram + size, bss_start: ram + size, bss_end: ram + size + 0x20 });
    ovls.push(ovl.buffer); romPos += size;
  }
  for (let i = 0; i < OVL_COUNT; i++) { const s = sinfos[i]; [s.rom_start, s.rom_end, s.ram_start, s.code_start, s.code_end, s.rodata_start, s.rodata_end, s.bss_start, s.bss_end].forEach((x, k) => iv.setUint32(TABLE_OFFSET + i * 36 + k * 4, x)); }
  iv.setUint32(TABLE_OFFSET + OVL_COUNT * 36, 0x44200000);
  Object.assign(scenes as any, { _overlayTableRomOffset: TABLE_OFFSET, _overlays: ovls, _sceneInfo: sinfos });
  (rom as any)._scenes = scenes;

  // MainFS: every compression type.
  const mainfs = new MainFS(rom);
  const cache: any[] = [];
  for (let d = 0; d < 4; d++) {
    const files: any[] = [];
    for (let f = 0; f < 6 + d; f++) {
      const kind = (d * 7 + f) % 7;
      if (kind === 0) { const x = randBytes(40 + f); files.push({ compressionType: 0, decompressedSize: x.length, decompressed: x.buffer, compressed: x.slice().buffer }); }
      else if (kind === 1) { const x = randBytes(100 + f * 3, 4); files.push({ compressionType: 1, decompressedSize: x.length, decompressed: x.buffer, compressed: compress(1, new DataView(x.buffer)) }); }
      else if (kind === 2 || kind === 3) { const t = kind === 2 ? 1 : 2; const s = lzStream(t, 300); files.push({ compressionType: t, decompressedSize: s.decompressed.byteLength, decompressed: s.decompressed, compressed: s.compressed }); }
      else if (kind === 4) { const x = randBytes(64, 3); files.push({ compressionType: 4, decompressedSize: 64, decompressed: x.buffer, compressed: compress(4, new DataView(x.buffer)) }); }
      else if (kind === 5) { const x = randBytes(90, 2); const c = rle(x); files.push({ compressionType: 5, decompressedSize: 90, decompressed: x.buffer, compressed: c.buffer }); }
      else { const s = lzStream(3, 200); files.push({ compressionType: 3, decompressedSize: s.decompressed.byteLength, decompressed: s.decompressed, compressed: s.compressed }); }
    }
    cache.push(files);
  }
  (mainfs as any)._mainfsCache = cache;
  (rom as any)._mainfs = mainfs;

  // Strings.
  const strs = [0, 1, 2, 3, 4].map(i => textBytes("Str" + i + "\u0010\u0011ab " + "x".repeat(i)));
  if (g.v === 3) {
    // StringTableSet isn't exported: let Strings3.extract read the sets from a
    // scratch ROM whose patch locations point at them.
    const s3 = new Strings3(rom);
    const tmp = new Uint8Array(INITIAL_LEN + 0x10000); tmp.set(initial.slice(0, INITIAL_LEN));
    const tv = new DataView(tmp.buffer);
    let pos = INITIAL_LEN;
    for (const locale of s3.getLocales(g.id)) {
      const set = stringTableSet([strs.slice(0, 3), strs.slice(1), [textBytes(locale)]]);
      tmp.set(set, pos);
      let upper = pos >>> 16; const lower = pos & 0xffff; if (lower & 0x8000) upper += 1;
      for (const p of s3.getPatchOffsets(locale as any)!) { tv.setUint16(p.upper, upper); tv.setUint16(p.lower, lower); }
      pos += set.length + 16;
    }
    romhandler._rom = new ROM(tmp.buffer);
    s3.extract();
    romhandler._rom = rom;
    (rom as any)._strings3 = s3;
  } else {
    const s = new Strings(rom);
    (s as any)._strFsInstance = new StringTable(new DataView(stringTable(strs).buffer));
    (rom as any)._strings = s;
  }

  // HVQFS: 5 backgrounds of 2x2 tiles.
  const hvqfs = new HVQFS(rom);
  const hcache: any[] = [];
  for (let b = 0; b < 5; b++) {
    const meta = new Uint8Array(0x40); const mv = new DataView(meta.buffer);
    mv.setUint32(0, 64); mv.setUint32(4, 48); mv.setUint32(8, 2); mv.setUint32(12, 2);
    for (let k = 16; k < 60; k += 4) mv.setFloat32(k, (rnd() - 0.5) * 1000);
    const files: ArrayBuffer[] = [meta.buffer];
    if (g.v > 1) files.push(textBytes("HVQ-MPS dummy...").buffer);
    for (let t = 0; t < 4; t++) {
      const kind = (b + t) % 3;
      if (kind === 0) { const h = randBytes(0x40); h.set(textBytes("HVQ2"), 0); files.push(h.buffer); }
      else if (kind === 1 && g.v > 1) { const raw = randBytes(0x1800, 2); const c = new Uint8Array(compress(3, new DataView(raw.buffer)) as ArrayBuffer); const f = new Uint8Array(8 + c.length); new DataView(f.buffer).setUint32(0, 3); new DataView(f.buffer).setUint32(4, 0x1800); f.set(c, 8); files.push(f.buffer); }
      else { const raw = randBytes(0x1800, 2); raw[0] = 0x11; files.push(raw.buffer); }
    }
    hcache.push(files);
  }
  (hvqfs as any)._hvqCache = hcache;
  (hvqfs as any)._hvqMetadata = [];
  for (let b = 0; b < 5; b++) (hvqfs as any)._readMetadata(b);
  (rom as any)._hvqfs = hvqfs;

  (rom as any)._audio = new Audio(rom);

  if (g.v === 2) {
    const anim = new Animationfs(rom);
    const sets: any[] = [];
    for (let s = 0; s < 2; s++) {
      const entries: any[] = [];
      for (let e = 0; e < 3; e++) {
        const tiles: any = {};
        for (const idx of [4 - e, 1 + e, 2]) { const raw = randBytes(0x1800, 2); tiles[idx] = { compressionType: 3, decompressed: raw.buffer, compressed: compress(3, new DataView(raw.buffer)) }; }
        entries.push(tiles);
      }
      sets.push(entries);
    }
    (anim as any)._animfsCache = sets;
    (rom as any)._animationFS = anim;
  }

  return new Uint8Array(romhandler.saveROM(false) as ArrayBuffer);
}

function img(w: number, h: number, a: number, c: number) {
  const data = new Uint8ClampedArray(w * h * 4); for (let i = 0; i < data.length; i++) data[i] = (i * a + c + (i >> 9)) & 0xff;
  return { width: w, height: h, data } as any;
}

function describe(name: string) {
  const g = GAMES[name];
  const rom = romhandler.getRom()!;
  const r: any = {};
  const scenes = rom.getScenes();
  r.scenes = { count: scenes.count(), infos: md5(new TextEncoder().encode(JSON.stringify(Array.from({ length: scenes.count() }, (_, i) => scenes.getInfo(i))))), overlays: md5(new TextEncoder().encode(Array.from({ length: scenes.count() }, (_, i) => md5(scenes.getDataView(i).buffer)).join())) };
  const mainfs = rom.getMainFS();
  r.mainfs = [];
  for (let d = 0; d < mainfs.getDirectoryCount(); d++) {
    const files = [];
    for (let f = 0; f < mainfs.getFileCount(d); f++) { const e = (mainfs as any)._mainfsCache[d][f]; if (!e) { files.push(null); continue; } files.push([e.compressionType, e.decompressedSize, md5(e.decompressed), e.compressed ? md5(e.compressed) : null, mainfs.getFileHeaderSize(d, f), mainfs.getCompressedSize(d, f)]); }
    r.mainfs.push(files);
  }
  r.mainfsByteLength = [mainfs.getByteLength(false), mainfs.getByteLength(true)];
  const map = getROMAdapter({})!.getCharacterMap();
  r.charMap = map;
  if (g.v === 3) {
    const s3 = rom.getStrings3();
    r.strings3 = {};
    for (const locale of s3.getLocales(g.id)) {
      const dirs = [];
      for (let d = 0; d < s3.getDirectoryCount(locale as any); d++) { const ss = []; for (let s = 0; s < s3.getStringCount(locale as any, d); s++) ss.push([md5(s3.read(locale as any, d, s, true) as ArrayBuffer), s3.read(locale as any, d, s, false)]); dirs.push(ss); }
      r.strings3[locale] = dirs;
    }
    r.stringsByteLength = s3.getByteLength();
  } else {
    const s = rom.getStrings();
    r.strings = []; for (let i = 0; i < s.getStringCount(); i++) r.strings.push([md5(s.read(i, true) as ArrayBuffer), s.read(i, false)]);
    r.stringsByteLength = s.getByteLength();
  }
  const hvqfs = rom.getHVQFS();
  r.hvq = [];
  for (let b = 0; b < hvqfs.getDirectoryCount(); b++) r.hvq.push({ files: (hvqfs as any)._hvqCache[b].map((x: ArrayBuffer) => md5(x)), meta: hvqfs.getMetadata(b), bg: md5(hvqfs.readBackgroundImgData(b).data) });
  r.hvqByteLength = hvqfs.getByteLength();
  if (g.v === 2) {
    const anim = rom.getAnimationFS();
    r.anim = (anim as any)._animfsCache.map((set: any) => set.map((e: any) => Object.keys(e).map(k => [Number(k), e[k].compressionType, md5(e[k].decompressed), md5(e[k].compressed)])));
    r.animByteLength = anim.getByteLength();
  }
  r.romLength = rom.getBuffer().byteLength;
  return JSON.parse(JSON.stringify(r));
}

function edit(name: string) {
  const g = GAMES[name];
  const rom = romhandler.getRom()!;
  const mainfs = rom.getMainFS();
  mainfs.write(0, 1, formula(300, 13, 1).buffer);
  mainfs.write(1, mainfs.getFileCount(1) + 2, formula(77, 7, 0).buffer);
  mainfs.write(0, 0, mainfs.get(0, 0).slice(0));
  if (g.v === 3) { rom.getStrings3().write("en", 1, 0, formula(9, 1, 0x41).buffer); rom.getStrings3().write("jp", 0, 1, formula(9, 1, 0x41).buffer); }
  else rom.getStrings().write(2, formula(9, 1, 0x41).buffer);
  const hvqfs = rom.getHVQFS();
  hvqfs.writeBackground(1, img(128, 96, 3, 5), 128, 96);
  hvqfs.writeBackground(hvqfs.getDirectoryCount(), img(128, 96, 7, 1), 128, 96, { tileWidth: 64, tileHeight: 48, tileCountX: 2, tileCountY: 2, fov: 17.5, scaleFactor: 0.25, cameraEyePosX: 1, cameraEyePosY: 2, cameraEyePosZ: 3, lookatPointX: 4, lookatPointY: 5, lookatPointZ: 6, cameraUpVecX: 0, cameraUpVecY: 1, cameraUpVecZ: 0 });
  hvqfs.updateMetadata(0, { fov: 33.25, cameraEyePosZ: 1000 });
  if (g.v === 2) {
    const anim = rom.getAnimationFS();
    anim.writeAnimationBackground(0, 1, img(128, 96, 3, 5), img(128, 96, 3, 9), 128, 96);
    anim.setSetEntryCount(1, 0);
  }
  const scenes = rom.getScenes();
  scenes.replace(5, formula(0x40, 5, 3).buffer as ArrayBuffer, { code_end: scenes.getInfo(5).code_start + 0x40 });
}

async function main() {
const outDir = process.argv[2];
for (const name of Object.keys(GAMES)) {
  const original = build(name);
  romhandler.clear();
  const errors: string[] = [];
  const loaded = await romhandler.setROMBuffer(original.slice().buffer, true, (m) => errors.push(m));
  const result: any = { game: GAMES[name].id, originalMd5: md5(original), errors };
  result.loaded = describe(name);
  result.resaveMd5 = md5(romhandler.saveROM(false));
  edit(name);
  result.edited = describe(name);
  const saved = new Uint8Array(romhandler.saveROM(false) as ArrayBuffer);
  result.savedMd5 = md5(saved); result.savedLength = saved.length;
  const savedDecompressed = new Uint8Array(romhandler.saveROM(true) as ArrayBuffer);
  result.savedDecompressedMd5 = md5(savedDecompressed); result.savedDecompressedLength = savedDecompressed.length;
  fs.writeFileSync(`${outDir}/rom_${name}.json`, JSON.stringify(result));
  fs.writeFileSync(`${outDir}/rom_${name}.z64.gz`, zlib.gzipSync(original, { level: 9 }));
  if (process.env.DUMP_SAVED) { fs.writeFileSync(`${process.env.DUMP_SAVED}/saved_${name}.z64`, saved); fs.writeFileSync(`${process.env.DUMP_SAVED}/savedd_${name}.z64`, savedDecompressed); }
  console.log(name, loaded, errors, original.length);
}
}
main();
