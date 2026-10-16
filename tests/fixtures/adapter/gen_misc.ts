// Reference outputs for the rest of the adapters: the space writers (_writeStarInfo,
// _writeBoos, _writeBanks, _writeItemShops, _writeGates, _writeKoopa, _writeBowser),
// custom audio, hydrateSpace, address helpers, the parse of board select images and
// logos from image packs, animation backgrounds, and the name maps.
import { romhandler } from "../packages/lib/romhandler";
import { getAdapter, getROMAdapter } from "../packages/lib/adapter/adapters";
import { getBoardInfos } from "../packages/lib/adapter/boardinfo";
import { getArrowRotationLimit } from "../packages/lib/adapter/boardinfo";
import { setCreateCanvas, setCreateImage } from "../packages/lib/utils/canvas";
import { createCanvasNode, createImageNode } from "../apps/cli/CanvasImpl";
import { toPack } from "../packages/lib/utils/img/ImgPack";
import { addSpaceInternal } from "../packages/lib/boards";
import { getEventsInLibrary } from "../packages/lib/events/EventLibrary";
import "../packages/lib/events/builtin/events.include";
import * as fs from "fs";
import * as crypto from "crypto";

setCreateCanvas(createCanvasNode as any);
setCreateImage(createImageNode as any);

const blob = (b: ArrayBufferLike) => {
  const data = Buffer.from(new Uint8Array(b));
  if (data.length <= 0x1000) return data.toString("hex");
  return `len=${data.length} sha1=${crypto.createHash("sha1").update(data).digest("hex")}`;
};
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
function pattern(w: number, h: number, seed: number) {
  const buf = new ArrayBuffer(w * h * 4);
  const u8 = new Uint8Array(buf);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4;
    u8[i] = (x * 3 + y + seed) & 0xff; u8[i + 1] = (x * y + seed * 5) & 0xff; u8[i + 2] = (x + y * 7) & 0xff; u8[i + 3] = 255;
  }
  return buf;
}

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const gameIds: any = { 1: "CLBE", 2: "NMWE", 3: "NMVE" };
const results: any = {};

function setup(game: number) {
  const log: any[] = [];
  const files = new Map<string, ArrayBuffer>();
  const sceneBufs: { [i: number]: ArrayBuffer } = {};
  const seqTable = { midis: [] as any[] };
  const rom = {
    getGame: () => gameIds[game],
    getMainFS: () => ({
      get(d: number, f: number) { const k = `${d}/${f}`; if (!files.has(k)) files.set(k, new ArrayBuffer(0x2000)); return files.get(k)!; },
      has(d: number, f: number) { return files.has(`${d}/${f}`); },
      write(d: number, f: number, c: ArrayBuffer) { files.set(`${d}/${f}`, c); log.push(["mainfs.write", d, f, blob(c)]); },
    }),
    getScenes: () => ({
      getInfo(i: number) { return { rom_start: 0x200000 + i * 0x40000, ram_start: 0x80100000 }; },
      getDataView(i: number) { if (!sceneBufs[i]) sceneBufs[i] = new ArrayBuffer(0x30000); return new DataView(sceneBufs[i]); },
    }),
    getAudio: () => ({ getSequenceTable: () => seqTable }),
    getAnimationFS: () => ({
      writeAnimationBackground(set: number, i: number, main: ImageData, anim: ImageData, w: number, h: number) {
        log.push(["animationfs.writeAnimationBackground", set, i, blob(main.data.buffer), blob(anim.data.buffer), w, h]);
      },
    }),
  };
  (romhandler as any).getRom = () => rom;
  (romhandler as any).getROMGame = () => gameIds[game];
  (romhandler as any).getGameVersion = () => game;
  return { log, files, sceneBufs, seqTable, adapter: getAdapter(game, {}) as any };
}

function sp(x: number, y: number, extra: any = {}) { return { x, y, z: 0, type: 1, ...extra }; }

(async () => {
  for (const game of [1, 2, 3]) {
    const { log, files, sceneBufs, seqTable, adapter } = setup(game);
    const res: any = {};
    const infos = getBoardInfos(gameIds[game])!;
    const board: any = {
      game, type: "NORMAL", bg: { width: 960, height: 720 }, events: {}, links: {},
      spaces: [sp(10, 10, { star: true }), sp(50, 50, { subtype: 0 }), sp(400, 400, { star: true }),
        sp(300, 310, { subtype: 0 }), sp(5, 600, { subtype: 3 }), sp(700, 20, { subtype: 5 }),
        sp(800, 30, { subtype: 6 }), sp(100, 650, { subtype: 7 }), sp(900, 700, { subtype: 8 }),
        sp(450, 450, { subtype: 2 }), sp(460, 460, { subtype: 1 })],
    };
    const attempt = (name: string, fn: () => void) => {
      try { fn(); } catch (e: any) { log.push(["error", name]); }
    };
    infos.forEach((info: any, j: number) => {
      attempt("_writeStarInfo" + j, () => adapter._writeStarInfo(board, info));
      attempt("_writeBoos" + j, () => adapter._writeBoos(board, info));
      attempt("_writeBanks" + j, () => adapter._writeBanks(board, info));
      attempt("_writeItemShops" + j, () => adapter._writeItemShops(board, info));
      attempt("_writeGates" + j, () => adapter._writeGates(board, info));
      if (game === 1) {
        attempt("_writeKoopa" + j, () => adapter._writeKoopa(board, info));
        attempt("_writeBowser" + j, () => adapter._writeBowser(board, info));
      }
    });
    // No stars/toads: writing undefined fails.
    const empty: any = { game, bg: { width: 960, height: 720 }, spaces: [sp(1, 1)], links: {} };
    attempt("emptyStarInfo", () => adapter._writeStarInfo(empty, infos[0]));
    attempt("emptyBoos", () => adapter._writeBoos(empty, infos[0]));
    res.board = board;
    res.empty = empty;
    res.scenes = {};
    for (const i in sceneBufs) res.scenes[i] = runs(sceneBufs[i]);

    // Custom audio.
    res.audio = adapter.onWriteAudio({ audioType: 1, audioData: [
      { name: "a", data: input.midi, soundbankIndex: 3 }, { name: "b", data: input.midi, soundbankIndex: 1 }] }, infos[0], 0);
    res.midis = seqTable.midis.map((m: any) => [blob(m.buffer), m.soundbankIndex]);
    res.audioInGame = [adapter.onWriteAudio({ audioIndex: 9 }, infos[0], 0), adapter.onWriteAudio({}, infos[0], 0)];

    // hydrateSpace through addSpaceInternal.
    const hb: any = { game, spaces: [], links: {}, events: {} };
    for (const type of [5, 6, 12, 1]) addSpaceInternal(10, 20, type, undefined, hb, getEventsInLibrary());
    res.hydrated = hb;

    res.offsetToAddr = [0x1234, 0x300000, 0x210000].map((o) => adapter._offsetToAddr(o, { sceneIndex: 4 }));
    res.offsetBase = [adapter._offsetToAddrBase(0x10, 0x807b0000), adapter._addrToOffsetBase(0x807b0040, 0x807b0000),
      adapter._addrToOffsetBase(0x00100010, 0x80100020)];
    res.maps = { audio: adapter.getAudioMap(0), sfx: adapter.getSoundEffectMap(0), chars: adapter.getCharacterMap() };

    // Parse board select images and logos from image packs.
    const packs: any = { 1: [[10, 276]], 2: [[9, 30], [10, 406]], 3: [[20, 72], [19, 22], [19, 28]] }[game];
    packs.forEach(([d, f]: number[], n: number) => {
      files.set(`${d}/${f}`, toPack([{ src: pattern(24 + n * 8, 16, n), width: 24 + n * 8, height: 16, bpp: 32 }], 16, 0));
    });
    const pb: any = { otherbg: {} };
    const pinfo = infos[game === 1 ? 0 : 0];
    if (game !== 1) adapter.onParseBoardSelectImg(pb, pinfo);
    adapter.onParseBoardLogoImg(pb, pinfo);
    res.parsedImages = pb.otherbg;

    if (game === 2) {
      await adapter._writeAnimationBackgrounds(1, 96, 72, input.bg, [input.bg, input.bg]);
      await adapter._writeAnimationBackgrounds(undefined, 96, 72, input.bg, [input.bg]);
      await adapter._writeAnimationBackgrounds(2, 96, 72, input.bg, []);
    }
    res.log = log;
    results[game] = res;
  }
  results.arrowRotationLimit = getArrowRotationLimit();
  results.noAdapter = [getAdapter(4 as any, {}), getBoardInfos("NMVJ" as any)];
  (romhandler as any).getGameVersion = () => null;
  results.noRomAdapter = getROMAdapter({});
  console.log(JSON.stringify(results));
})();
