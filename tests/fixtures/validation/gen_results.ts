// Validation of the synthetic boards in boards.json, rule by rule and as a whole.
// Usage: node ref/run.mjs ref/validation_rules.ts <fixtures/validation dir> > results.json
import * as fs from "fs";
import * as path from "path";
import "../packages/lib/events/builtin/events.include";
import { romhandler } from "../packages/lib/romhandler";
import { Game } from "../packages/lib/types";
import { getRule } from "../packages/lib/validation/validationrules";
import { validateCurrentBoardForOverwrite } from "../packages/lib/validation/validation";
import { dummyBoardInfo } from "../packages/lib/adapter/boardinfobase";
import { BankEvent, ItemShopEvent } from "../packages/lib/events/builtin/events.common";

const RULES: [string, any][] = [
  ["HASSTART", undefined], ["GAMEVERSION", undefined], ["DEADEND", undefined],
  ["TOOMANYSPACES", undefined], ["OVERRECOMMENDEDSPACES", { max: 128 }],
  ["TOOMANYBOOS", { limit: 2 }], ["TOOMANYBOOS", undefined], ["TOOMANYBOWSERS", { limit: 1 }],
  ["TOOMANYKOOPAS", { limit: 0 }], ["TOOMANYBANKS", { limit: 2 }], ["TOOMANYITEMSHOPS", { limit: 1 }],
  ["TOOMANYGATES", { limit: 2 }], ["TOOMANYGATES", { limit: 0 }],
  ["BADSTARCOUNT", { low: 0, high: 7, disallowed: { 1: true } }], ["BADSTARCOUNT", { low: 7, high: 7 }],
  ["BADSTARCOUNT", { low: 0, high: 8, disallowed: { 1: true } }], ["WARNNOSTARSPACES", undefined],
  ["TOOFEWBLUESPACES", { low: 3 }], ["TOOFEWREDSPACES", { low: 1 }], ["TOOFEWREDSPACES", undefined],
  ["TOOMANYOFEVENT", { event: BankEvent, high: 2 }], ["TOOMANYOFEVENT", { event: ItemShopEvent, low: 2 }],
  ["TOOMANYOFEVENT", { event: BankEvent, low: 1, high: 1 }],
  ["UNRECOGNIZEDEVENTS", undefined], ["UNSUPPORTEDEVENTS", undefined], ["CUSTOMEVENTFAIL", undefined],
  ["CUSTOMEVENTBADPARAMS", undefined], ["TOOMANYPATHOPTIONS", undefined], ["TOOMANYPATHOPTIONS", { limit: 1 }],
  ["CHARACTERSONPATH", undefined], ["SPLITATNONINVISIBLESPACE", undefined],
  ["TOOMANYARROWROTATIONS", { limit: 8 }], ["GATESETUP", undefined],
  ["ADDITIONALBGCODEISSUE", undefined], ["GETAUDIOINDEXCODEISSUE", undefined], ["AUDIODETAILSISSUE", undefined],
];

const GAMES: any = { 1: Game.MP1_USA, 2: Game.MP2_USA, 3: Game.MP3_USA };

(async () => {
  const dir = process.argv[2];
  const boards = JSON.parse(fs.readFileSync(path.join(dir, "boards.json"), "utf8"));
  console.error = () => {};
  let currentGame: Game = Game.MP1_USA;
  (romhandler as any).getROMGame = () => currentGame;
  (romhandler as any).getGameVersion = () => ({ CLBE: 1, NMWE: 2, NMVE: 3 } as any)[currentGame];
  (romhandler as any).romIsLoaded = () => false;
  const out: any = { rules: {}, overwrite: {} };
  for (const name of Object.keys(boards).sort()) {
    const boardGame = name === "mp2_on_other" ? 3 : boards[name].game;
    currentGame = GAMES[boardGame];
    const res: any[] = [];
    for (const [id, args] of RULES) {
      const board = JSON.parse(JSON.stringify(boards[name]));
      try {
        res.push(await getRule(id, args).fails({ board, boardInfo: dummyBoardInfo }));
      } catch (e) {
        res.push({ error: String(e) });
      }
    }
    out.rules[name] = res;
    out.overwrite[name] = {};
    for (const g of [1, 2, 3]) {
      currentGame = GAMES[g];
      const board = JSON.parse(JSON.stringify(boards[name]));
      const romBoards = [
        { ...JSON.parse(JSON.stringify(boards["mp" + g + "_valid"])), name: "ROM A" },
        { ...JSON.parse(JSON.stringify(boards["mp" + g + "_many_subtypes"])), name: "ROM B", type: "DUEL" },
        { ...JSON.parse(JSON.stringify(boards["mp" + g + "_nine_stars"])), name: "ROM C" },
      ];
      try {
        out.overwrite[name][g] = await validateCurrentBoardForOverwrite(romBoards, board, false);
      } catch (e) {
        out.overwrite[name][g] = { error: String(e) };
      }
    }
  }
  out.ruleList = RULES.map(([id, args]) => [id, args && args.event ? { ...args, event: args.event.id } : args]);
  process.stdout.write(JSON.stringify(out));
})();
