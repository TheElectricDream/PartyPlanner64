// Generates reference board overlay asm for the Python port (tests/fixtures/overlays).
// Usage: node ref/run.mjs ref/overlays_gen.ts <outdir>
import "../packages/lib/events/builtin/events.include";
import { createBoardOverlay as mp1Overlay } from "../packages/lib/adapter/MP1.U.boardoverlay";
import { createBoardOverlay as mp2Overlay } from "../packages/lib/adapter/MP2.U.boardoverlay";
import { createBoardOverlay as mp3Overlay } from "../packages/lib/adapter/MP3.U.boardoverlay";
import { getBoardInfos } from "../packages/lib/adapter/boardinfo";
import { Game, Space, SpaceSubtype } from "../packages/lib/types";
import { getAdditionalBgAsmForOverlay, getBoardAdditionalBgHvqIndices } from "../packages/lib/events/additionalbg";
import { getAudioIndexAsmForOverlay } from "../packages/lib/events/getaudiochoice";
import { getSymbol } from "../packages/lib/symbols/symbols";
import * as fs from "fs";
import * as zlib from "zlib";

const outDir = process.argv[2];

// Deterministic pseudo random numbers.
let seed = 12345;
function rand() {
  seed = (seed * 1103515245 + 12345) & 0x7fffffff;
  return seed / 0x7fffffff;
}

interface Opts {
  stars?: number;
  toads?: number;
  boos?: number;
  bowser?: boolean;
  koopa?: boolean;
  banks?: number;
  bankCoins?: number;
  bankEvents?: number;
  shops?: number;
  shopEvents?: number;
  booEvents?: number;
  arrows?: number;
  gates?: number; // number of gate event spaces (pairs of entry/exit)
  dupGate?: boolean;
  additionalbg?: number;
  additionalbgcode?: any;
  audioSelectCode?: any;
  duel?: boolean;
  boardevents?: boolean;
  floatCoords?: boolean;
}

function mkBoard(game: number, opts: Opts): any {
  const spaces: any[] = [];
  const width = 1152, height = 864;
  const add = (type: number, subtype?: number, extra?: any) => {
    const x = opts.floatCoords ? Math.round(rand() * width * 100) / 100 : Math.floor(rand() * width);
    const y = opts.floatCoords ? Math.round(rand() * height * 100) / 100 : Math.floor(rand() * height);
    const s: any = { x, y, z: 0, type };
    if (subtype !== undefined) s.subtype = subtype;
    if (extra) Object.assign(s, extra);
    spaces.push(s);
    return spaces.length - 1;
  };
  add(opts.duel ? Space.DUEL_START_BLUE : Space.START);
  if (opts.duel) add(Space.DUEL_START_RED);
  for (let i = 0; i < 6; i++) add(opts.duel ? Space.DUEL_BASIC : Space.BLUE);
  for (let i = 0; i < (opts.stars || 0); i++) add(Space.BLUE, undefined, { star: true });
  for (let i = 0; i < (opts.toads || 0); i++) add(Space.OTHER, SpaceSubtype.TOAD);
  for (let i = 0; i < (opts.boos || 0); i++) add(Space.OTHER, SpaceSubtype.BOO);
  if (opts.bowser) add(Space.OTHER, SpaceSubtype.BOWSER);
  if (opts.koopa) add(Space.OTHER, SpaceSubtype.KOOPA);
  for (let i = 0; i < (opts.banks || 0); i++) add(Space.OTHER, SpaceSubtype.BANK);
  for (let i = 0; i < (opts.bankCoins || 0); i++) add(Space.OTHER, SpaceSubtype.BANKCOIN);
  for (let i = 0; i < (opts.shops || 0); i++) add(Space.OTHER, SpaceSubtype.ITEMSHOP);
  const ev = (id: string, extra?: any) => Object.assign({ id, activationType: 1, executionType: 1 }, extra || {});
  for (let i = 0; i < (opts.bankEvents || 0); i++) add(Space.BLUE, undefined, { events: [ev("BANK")] });
  for (let i = 0; i < (opts.shopEvents || 0); i++) add(Space.BLUE, undefined, { events: [ev("ITEMSHOP")] });
  for (let i = 0; i < (opts.booEvents || 0); i++) add(Space.BLUE, undefined, { events: [ev("BOO")] });
  const rots = [undefined, 0, 45.5, 3.14159, -90, 180, 270.25, 1e-3, 359.99, 12];
  for (let i = 0; i < (opts.arrows || 0); i++) {
    const extra: any = {};
    if (rots[i % rots.length] !== undefined) extra.rotation = rots[i % rots.length];
    add(Space.ARROW, undefined, extra);
  }
  for (let g = 0; g < (opts.gates || 0); g++) {
    const gateIdx = add(Space.OTHER, SpaceSubtype.GATE);
    const params = {
      gateEntryIndex: gateIdx - 1 >= 0 ? gateIdx - 1 : 0,
      gateSpaceIndex: gateIdx,
      gateExitIndex: gateIdx + 1,
      gatePrevChain: [g * 2 + 1, g + 3],
      gateNextChain: [g * 2 + 2, g + 7],
    };
    add(Space.BLUE, undefined, { events: [ev("GATE", { parameterValues: params })] });
    add(Space.BLUE, undefined, { events: [ev("GATE", { parameterValues: Object.assign({}, params, { gateExitIndex: params.gateEntryIndex, gateEntryIndex: params.gateExitIndex }) })] });
    if (opts.dupGate && g === 0) {
      // Another space referencing an already used gate space.
      add(Space.BLUE, undefined, { events: [ev("CHANCETIME"), ev("GATE", { parameterValues: params })] });
    }
  }
  const board: any = {
    name: "Test board",
    description: "Generated",
    game,
    type: opts.duel ? "DUEL" : "NORMAL",
    difficulty: 3,
    spaces,
    links: {},
    events: {},
    bg: { width, height, src: "", fov: 17, scaleFactor: 1, cameraEyePosX: 0, cameraEyePosY: 1355, cameraEyePosZ: 1495, lookatPointX: 0, lookatPointY: 0, lookatPointZ: 0 },
    otherbg: {},
    audioType: 0,
    audioIndex: 3,
  };
  if (opts.additionalbg) {
    board.additionalbg = [];
    for (let i = 0; i < opts.additionalbg; i++) board.additionalbg.push("data:image/png;base64,AAAA");
  }
  if (opts.additionalbgcode !== undefined) board.additionalbgcode = opts.additionalbgcode;
  if (opts.audioSelectCode !== undefined) {
    board.audioSelectCode = opts.audioSelectCode;
    board.audioType = 1;
  }
  if (opts.boardevents) {
    board.boardevents = [ev("GATE", { parameterValues: { gateEntryIndex: 1, gateSpaceIndex: 2, gateExitIndex: 3, gatePrevChain: [0, 0], gateNextChain: [0, 0] } }), ev("BOO")];
  }
  return board;
}

const customBgAsm = `; custom
ADDIU SP SP -4
SW RA 0(SP)
myLabel:
LI V0 ADDITIONAL_BG_1
BEQ V0 R0 myLabel
NOP
.global exported
exported:
LW RA 0(SP)
JR RA
ADDIU SP SP 4`;

const customAudioAsm = `ADDIU SP SP -4
SW RA 0(SP)
pick:
LI V0 MUSIC_TRACK_INDEX_2
LW RA 0(SP)
JR RA
ADDIU SP SP 4`;

const caseOpts: [string, Opts][] = [
  ["empty", {}],
  ["one_star_no_toad", { stars: 1 }],
  ["basic", { stars: 3, toads: 2, boos: 1, bowser: true, koopa: true }],
  ["full", { stars: 7, toads: 4, boos: 2, bowser: true, koopa: true, banks: 2, bankCoins: 3, bankEvents: 2, shops: 2, shopEvents: 3, booEvents: 2, arrows: 10, gates: 2, additionalbg: 2, additionalbgcode: customBgAsm, audioSelectCode: { language: 0, code: customAudioAsm }, boardevents: true, floatCoords: true }],
  ["stars8", { stars: 8, toads: 1, boos: 3, banks: 1, bankEvents: 1, shops: 1, shopEvents: 1, booEvents: 1, arrows: 3, gates: 1 }],
  ["stars2_events_no_targets", { stars: 2, bankEvents: 3, shopEvents: 1, booEvents: 3, arrows: 8 }],
  ["stars4_bgcode_object", { stars: 4, toads: 4, additionalbg: 1, additionalbgcode: { language: 0, code: customBgAsm }, gates: 3, dupGate: true }],
  ["stars5_6", { stars: 5, toads: 6, boos: 1, bankCoins: 1, banks: 3, bankEvents: 1, floatCoords: true }],
  ["stars6", { stars: 6, toads: 2, shops: 3, shopEvents: 2, gates: 1, dupGate: true, additionalbg: 3 }],
  ["stars9", { stars: 9, toads: 3, arrows: 1, audioSelectCode: { language: 0, code: customAudioAsm } }],
  ["duel", { duel: true, arrows: 2, gates: 1, boos: 1, booEvents: 1 }],
];

const audioIndicesFor = [[3], [1], [7], [0x30, 0x31, 0x32], [5], [2], [9], [4, 6], [11], [1, 2], [8]];

const games: [string, number, Game, any][] = [
  ["mp1", 1, Game.MP1_USA, mp1Overlay],
  ["mp2", 2, Game.MP2_USA, mp2Overlay],
  ["mp3", 3, Game.MP3_USA, mp3Overlay],
];

async function main() {
  for (const [name, gameVersion, gameId, overlayFn] of games) {
    const infos = getBoardInfos(gameId)!;
    const cases: any[] = [];
    for (let c = 0; c < caseOpts.length; c++) {
      const [caseName, opts] = caseOpts[c];
      if (opts.duel && gameVersion !== 3) continue;
      const board = mkBoard(gameVersion, opts);
      const boardIn = JSON.parse(JSON.stringify(board));
      // Use the overwritable (normal) boards in turn.
      const normalInfos = infos.filter((i: any) => i.mainfsEventFile);
      const boardIndex = infos.indexOf(normalInfos[c % normalInfos.length]);
      const boardInfo: any = infos[boardIndex];
      const audioIndices = audioIndicesFor[c];
      // Intermediate values, so the overlay can be tested on its own.
      const prepped = {
        additionalBgCode: await getAdditionalBgAsmForOverlay(boardIn, boardInfo.bgDir, getBoardAdditionalBgHvqIndices(boardIn)),
        audioIndexCode: await getAudioIndexAsmForOverlay(boardIn, audioIndices),
      };
      const asm = await overlayFn(board, boardInfo, boardIndex, audioIndices);
      cases.push({
        name: caseName, boardIndex, audioIndices, board: boardIn,
        boardInfo: { bg_dir: boardInfo.bgDir, pause_bg_dir: boardInfo.pauseBgDir ?? null, board_def_file: boardInfo.boardDefFile, mainfs_event_file: boardInfo.mainfsEventFile },
        prepped, deadSpaceIndex: board._deadSpace ?? null,
        asm,
      });
    }
    // A board info without mainfsEventFile (duel boards) fails.
    const noEvt = infos.findIndex((i: any) => !i.mainfsEventFile);
    let error: any = null;
    if (noEvt >= 0) {
      try { await overlayFn(mkBoard(gameVersion, { stars: 1 }), infos[noEvt], noEvt, [1]); } catch (e) { error = String(e); }
    }
    const symbols: any = {};
    for (const sym of ["ReadMainFS", "FreeMainFS", "EventTableHydrate", "AddArrowAngle"]) {
      try { symbols[sym] = getSymbol(gameId, sym); } catch (e) { }
    }
    const json = JSON.stringify({ game: name, symbols, cases, missingEventFileError: error, missingEventFileBoardIndex: noEvt });
    fs.writeFileSync(`${outDir}/${name}_overlays.json.gz`, zlib.gzipSync(json, { level: 9 }));
    console.log(name, cases.length, json.length, error);
  }
}
main();
