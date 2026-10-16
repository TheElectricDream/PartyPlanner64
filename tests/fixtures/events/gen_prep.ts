// Reference outputs of the event code text transforms (prepAsm.ts, prepC.ts,
// additionalbg.ts, getaudiochoice.ts) and of createCustomEvent.
// Usage: node ref/run.mjs ref/events_prep.ts <fixtures/events dir> > prep.json
import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import "../packages/lib/events/builtin/events.include";
import {
  prepAsm, prepGenericAsm, prepSingleEventAsm, makeGameSymbolLabels,
  makeGenericSymbolsForAddresses, makeParameterSymbolLabels,
  scopeLabelsStaticByDefault, createEventInstanceLabel,
} from "../packages/lib/events/prepAsm";
import { prepC, makeParameterSymbolDefines } from "../packages/lib/events/prepC";
import {
  prepAdditionalBgAsm, prepAdditionalBgC, makeBgSymbolLabels, makeAdditionalBgDefines,
  defaultAdditionalBgAsm, defaultAdditionalBgC,
} from "../packages/lib/events/additionalbg";
import {
  prepGetAudioAsm, prepGetAudioC, makeAudioSymbolLabels, makeAudioDefines,
  defaultGetAudioAsm, defaultGetAudioC, makeFakeGetAudioIndices,
} from "../packages/lib/events/getaudiochoice";
import { createCustomEvent, CustomAsmHelper } from "../packages/lib/events/customevents";
import { dummyBoardInfo } from "../packages/lib/adapter/boardinfobase";
import { Game } from "../packages/lib/types";

const dir = process.argv[2];
const corpusDir = path.join(dir, "corpus");
const files = fs.readdirSync(corpusDir).sort();
const corpus: { [name: string]: string } = {};
for (const f of files) corpus[f] = fs.readFileSync(path.join(corpusDir, f), "utf8");
const writes = JSON.parse(fs.readFileSync(path.join(dir, "write.json"), "utf8"));
const asms: { [name: string]: string } = { ...corpus };
writes.results.forEach((r: any, i: number) => { if (typeof r === "string") asms["write_" + i] = r; });
asms.defaultAdditionalBgAsm = defaultAdditionalBgAsm;
asms.defaultGetAudioAsm = defaultGetAudioAsm;
asms.defaultAdditionalBgC = defaultAdditionalBgC;
asms.defaultGetAudioC = defaultGetAudioC;

function attempt(fn: () => any) {
  try { return fn(); } catch (e: any) { return { error: String(e) }; }
}
function digest(s: string) {
  const lines = s.split("\n");
  return { md5: crypto.createHash("md5").update(s, "utf8").digest("hex"), lines: lines.length,
    head: lines.slice(0, 3), tail: lines.slice(-3) };
}

const out: any = { scope: {}, generic: {}, custom: {}, single: {}, params: [], misc: {}, games: {}, prepAsm: {} };
for (const name in asms) {
  const asm = asms[name];
  out.scope[name] = [attempt(() => scopeLabelsStaticByDefault(asm, true)), attempt(() => scopeLabelsStaticByDefault(asm, false))];
  out.generic[name] = makeGenericSymbolsForAddresses(asm);
  out.custom[name] = attempt(() => createCustomEvent(name.endsWith(".c") ? 1 : 0, asm));
  out.custom[name + ":games"] = CustomAsmHelper.readSupportedGames(asm);
  out.custom[name + ":params"] = CustomAsmHelper.readDiscretePropertySet(asm, "PARAM");
  out.custom[name + ":cleared"] = CustomAsmHelper.clearDiscreteProperties(asm, ["NAME", "GAMES", "EXECUTION", "PARAM"]);
}
out.custom.written = CustomAsmHelper.writeDiscretePropertyArray(
  CustomAsmHelper.writeDiscreteProperty("nop", "NAME", "x", ";"), "PARAM", ["Number|a", "Boolean|b"], "//");

const paramEvent: any = createCustomEvent(0, corpus["edge1.s"]);
const valueSets: any[] = [
  undefined,
  {},
  { coins: 5, flag: true, target: 3, amount: 7, targets: [1, 3, 9], numbers: [1, 2] },
  { coins: "x", flag: 0, target: 9, amount: -2, targets: [] },
  { coins: 2.5, flag: false, target: 1, targets: [4] },
];
const infos: any[] = [
  { chains: [[0, 1, 2], [3, 4], [5, 9]], curSpaceIndex: 3 },
  { curSpaceIndex: -2, testCompile: true },
  { chains: [], curSpaceIndex: 0 },
];
for (let v = 0; v < valueSets.length; v++) {
  for (let i = 0; i < infos.length; i++) {
    const spaceEvent: any = { id: paramEvent.id, activationType: 3, executionType: 1 };
    if (valueSets[v] !== undefined) spaceEvent.parameterValues = valueSets[v];
    out.params.push({
      v, i,
      labels: attempt(() => makeParameterSymbolLabels(paramEvent, spaceEvent, infos[i])),
      defines: attempt(() => makeParameterSymbolDefines(paramEvent, spaceEvent, infos[i])),
      single: [0, 1].map((n) => ["edge1.s", "main_entry.s", "crlf.s"].map((f) =>
        attempt(() => prepSingleEventAsm(corpus[f], paramEvent, spaceEvent, infos[i], !!n, n + 1)))),
    });
  }
}

out.misc = {
  labels: [createEventInstanceLabel(0, 0), createEventInstanceLabel(12, 3), createEventInstanceLabel(-4, 1)],
  bgAsm: prepAdditionalBgAsm(defaultAdditionalBgAsm, 7, [8, 9]),
  bgAsmNull: prepAdditionalBgAsm(corpus["edge1.s"], 0, null),
  bgC: prepAdditionalBgC(defaultAdditionalBgC, 7, [8, 9]),
  bgSyms: makeBgSymbolLabels(3, [4, 5, 6]),
  bgDefines: makeAdditionalBgDefines(3, []),
  audioAsm: prepGetAudioAsm(defaultGetAudioAsm, [12, 40]),
  audioC: prepGetAudioC(defaultGetAudioC, [12]),
  audioSyms: makeAudioSymbolLabels([1, 2, 3]),
  audioDefines: [makeAudioDefines(null), makeAudioDefines([5, 6])],
  fakeAudio: [makeFakeGetAudioIndices({} as any), makeFakeGetAudioIndices({ audioData: [{}, {}, {}] } as any)],
};

for (const game of [Game.MP1_USA, Game.MP1_JPN, Game.MP1_PAL, Game.MP2_USA, Game.MP2_JPN, Game.MP2_PAL, Game.MP3_USA, Game.MP3_JPN, Game.MP3_PAL]) {
  out.games[game] = [true, false].map((stubs) => attempt(() => digest(makeGameSymbolLabels(game, stubs).join("\n"))));
  out.prepAsm[game] = attempt(() => {
    const spaceEvent: any = { id: paramEvent.id, activationType: 3, executionType: 1, parameterValues: valueSets[2] };
    const info: any = {
      addr: 0x80123450, game, audioIndices: [3, 4], boardInfo: dummyBoardInfo,
      board: { additionalbg: ["a", "b"] }, chains: infos[0].chains,
    };
    return [digest(prepAsm(corpus["edge1.s"], paramEvent, spaceEvent, info)),
      digest(prepGenericAsm(corpus["crlf.s"], 0x80000000, game)),
      prepC(corpus["event.c"], createCustomEvent(1, corpus["event.c"]), spaceEvent, info)];
  });
}

console.log(JSON.stringify(out));
