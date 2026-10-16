// Generates assembler reference outputs (board overlays, built-in event asm)
// for the Python mips-assembler port's tests.
import { assemble } from "mips-assembler";
import { createHash } from "crypto";
import { gzipSync } from "zlib";
import { Game, Space, SpaceSubtype, EditorEventActivationType, EventExecutionType } from "../packages/lib/types";
import { getBoardInfos } from "../packages/lib/adapter/boardinfo";
import { createBoardOverlay as mp1 } from "../packages/lib/adapter/MP1.U.boardoverlay";
import { createBoardOverlay as mp2 } from "../packages/lib/adapter/MP2.U.boardoverlay";
import { createBoardOverlay as mp3 } from "../packages/lib/adapter/MP3.U.boardoverlay";
import { prepGenericAsm, prepSingleEventAsm, makeGameSymbolLabels, makeGenericSymbolsForAddresses } from "../packages/lib/events/prepAsm";
import "../packages/lib/events/builtin/events.include";
import { getEventsInLibrary } from "../packages/lib/events/EventLibrary";

function makeBoard(game: number, variant: number): any {
  const spaces: any[] = [];
  const types = [Space.START, Space.BLUE, Space.RED, Space.BLUE, Space.HAPPENING, Space.CHANCE,
    Space.OTHER, Space.OTHER, Space.OTHER, Space.OTHER, Space.OTHER, Space.OTHER, Space.BLUE, Space.ITEM,
    Space.BANK, Space.BLUE, Space.RED, Space.BLUE];
  const subtypes: any = { 6: SpaceSubtype.TOAD, 7: SpaceSubtype.BOO, 8: SpaceSubtype.KOOPA, 9: SpaceSubtype.BOWSER,
    10: SpaceSubtype.BANK, 11: SpaceSubtype.ITEMSHOP, 17: SpaceSubtype.TOAD };
  if (variant === 1) { subtypes[7] = SpaceSubtype.BOO; subtypes[12] = SpaceSubtype.BOO; delete subtypes[8]; }
  for (let i = 0; i < types.length; i++) {
    const s: any = { x: 30 + i * 47, y: 50 + ((i * 97) % 300), z: 0, type: types[i] };
    if (subtypes[i] !== undefined) s.subtype = subtypes[i];
    if (variant === 0 ? (i === 3 || i === 12 || i === 15) : (i % 4 === 1)) s.star = true;
    spaces.push(s);
  }
  const links: any = {};
  for (let i = 0; i < 5; i++) links[i] = i + 1;
  links[5] = [12, 13];
  for (let i = 12; i < 17; i++) links[i] = i + 1;
  return { name: "Test", description: "", game, type: "NORMAL", difficulty: 3, spaces, links, events: {},
    bg: { width: 960, height: 720, src: "", fov: 0, scaleFactor: 1, cameraEyePosX: 0, cameraEyePosY: 0,
      cameraEyePosZ: 0, lookatPointX: 0, lookatPointY: 0, lookatPointZ: 0 },
    otherbg: {}, audioType: 0, audioIndex: 0 };
}

function hash(buf: ArrayBuffer) { return createHash("sha256").update(new Uint8Array(buf)).digest("hex"); }

function run(asm: string): any {
  try {
    const syms: any = Object.create(null);
    const buf = assemble(asm, { symbolOutputMap: syms }) as ArrayBuffer;
    const text = assemble(asm, { text: true }) as string[];
    return { len: buf.byteLength, sha256: hash(buf), syms: { ...syms },
      textSha256: createHash("sha256").update(text.join("\n")).digest("hex") };
  } catch (e: any) {
    return { error: String(e.message) };
  }
}

(async () => {
  const cases: any[] = [];
  const games: [number, number, any][] = [[Game.MP1_USA, 1, mp1], [Game.MP2_USA, 2, mp2], [Game.MP3_USA, 3, mp3]];
  for (const [game, version, fn] of games) {
    const infos = getBoardInfos(game as any)!.filter((i: any) => i.mainfsEventFile);
    for (const variant of (version === 1 ? [0, 1] : [0])) {
      const board = makeBoard(version, variant);
      const boardIndex = variant;
      const overlayAsm = await fn(board, infos[Math.min(boardIndex, infos.length - 1)], boardIndex, [3, 7]);
      // As AdapterBase._writeNewBoardOverlay does.
      const asm = `
        ${makeGameSymbolLabels(game as any, true).join("\n")}
        ${makeGenericSymbolsForAddresses(overlayAsm).join("\n")}

        ${overlayAsm}
      `;
      cases.push({ name: `overlay_${version}_${variant}`, asmGz: gzipSync(asm).toString("base64"), out: run(asm) });
    }
    // Built-in events, combined roughly as AdapterBase._writeEvents does.
    const lib = getEventsInLibrary();
    const eventAsms: string[] = [];
    let num = 0;
    for (const id in lib) {
      const ev: any = lib[id];
      if (!ev.write || ev.supportedGames.indexOf(game) === -1) continue;
      const board = makeBoard(version, 0);
      const info: any = { boardIndex: 0, board, boardInfo: infos[0], audioIndices: [3, 7],
        curSpaceIndex: 3 + num, curSpace: board.spaces[3], chains: [[0, 1, 2, 3, 4, 5], [12, 13, 14, 15, 16, 17]],
        game, gameVersion: version, addr: 0x80123400 };
      const parameterValues: any = {};
      for (const p of ev.parameters || []) {
        parameterValues[p.name] = { Boolean: true, Number: 3, Space: 13, SpaceArray: [12, 14], NumberArray: [1, 2] }[p.type as string] ?? 1;
      }
      Object.assign(parameterValues, { chains: [0, 1], spaceIndexArgs: [13, 14, -1], chainArgs: [1, 0, 1, 0], prevSpace: 2 });
      const inst = { id, activationType: EditorEventActivationType.LANDON, executionType: EventExecutionType.DIRECT,
        parameterValues };
      let asm: any;
      try {
        asm = await ev.write(new DataView(new ArrayBuffer(0)), inst, info, {});
      } catch (e: any) { console.error("skip", id, String(e)); continue; }
      if (typeof asm !== "string") { console.error("skip", id, typeof asm); continue; }
      const one = prepGenericAsm(asm, 0x80123400, game as any);
      cases.push({ name: `event_${id}_${version}`, asmGz: gzipSync(one).toString("base64"), out: run(one) });
      eventAsms.push(prepSingleEventAsm(asm, ev, inst as any, info, true, num++));
    }
    const combined = eventAsms.join("\n");
    const internals = Array.from(new Set(combined.match(/__PP64_INTERNAL_\w+/g) || []));
    const full = `
.org 0x80400000
.ascii "PP64"
.word 0x80400000
.word 0 // Populated with buffer size later
.align 16
${makeGameSymbolLabels(game as any, true).join("\n")}
${internals.map((n, i) => `.definelabel ${n},${0x80100000 + i * 0x40}`).join("\n")}
${makeGenericSymbolsForAddresses(combined).join("\n")}
${combined}
`;
    cases.push({ name: `events_${version}`, asmGz: gzipSync(full).toString("base64"), out: run(full) });
  }
  console.log(JSON.stringify(cases));
})();
