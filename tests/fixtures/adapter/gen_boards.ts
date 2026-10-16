// Reference outputs for boarddef (determineChains, padChains, create, parse) and the
// adapters' chain/star/gate event creation, on sample boards for each game.
import { romhandler } from "../packages/lib/romhandler";
import { getAdapter } from "../packages/lib/adapter/adapters";
import {
  determineChains,
  padChains,
  create as createBoardDef,
  parse as parseBoardDef,
} from "../packages/lib/adapter/boarddef";
import "../packages/lib/events/builtin/events.include";

const games: any = { 1: "CLBE", 2: "NMWE", 3: "NMVE" };
let curGame = 1;
(romhandler as any).getGameVersion = () => curGame;
(romhandler as any).getROMGame = () => games[curGame];

function sp(x: number, y: number, type = 1, extra: any = {}) {
  return { x, y, z: 0, type, ...extra };
}

const samples: any = {
  loop: {
    spaces: [sp(100, 100, 7), sp(200, 100), sp(300, 100, 2), sp(400, 100), sp(400, 200),
      sp(300, 200, 1, { star: true }), sp(200, 200), sp(100, 200)],
    links: { 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 0 },
  },
  branch: {
    spaces: [sp(100, 100, 7), sp(200, 100), sp(300, 100), sp(400, 50), sp(500, 50),
      sp(400, 150, 2), sp(600, 100), sp(700, 100, 1, { star: true }), sp(650, 300, 0), sp(50, 400, 0)],
    links: { 0: 1, 1: 2, 2: [3, 5], 3: 4, 4: 6, 5: 6, 6: 7, 7: 0 },
  },
  padding: {
    // 2 and 3 are one-space chains (a merge and a split need padding).
    spaces: [sp(100, 100, 7), sp(200, 100), sp(300, 50), sp(300, 150), sp(400, 100),
      sp(500, 50), sp(500, 150), sp(600, 100), sp(700, 100, 1, { star: true }), sp(800, 100)],
    links: { 0: 1, 1: [2, 3], 2: 4, 3: [5, 6], 5: 7, 6: 7, 4: 7, 7: 8, 8: 9, 9: 0 },
  },
  deadend: {
    // 5 -> 6 -> 2 can only be reached in reverse; 8 is decorative; 9 -> 10 -> 9 is an isolated cycle.
    spaces: [sp(100, 100, 7), sp(200, 100), sp(300, 100), sp(400, 100), sp(500, 100),
      sp(300, 300), sp(300, 200), sp(200, 300), sp(900, 900, 0), sp(10, 10), sp(20, 20)],
    links: { 0: 1, 1: 2, 2: 3, 3: 4, 4: 0, 5: 6, 6: 2, 7: 1, 9: 10, 10: 9 },
  },
  gate: {
    spaces: [sp(100, 100, 7), sp(200, 100), sp(300, 100), sp(400, 100), sp(500, 100, 1, { subtype: 8 }),
      sp(600, 100), sp(700, 100), sp(800, 100), sp(300, 300), sp(500, 300, 1, { star: true }),
      sp(700, 300)],
    links: { 0: 1, 1: 2, 2: [3, 8], 3: 4, 4: 5, 5: 6, 6: 7, 8: 9, 9: 10, 10: 7, 7: 0 },
  },
};

const out: any = { samples, results: {} };
for (const game of [1, 2, 3]) {
  curGame = game;
  const adapter: any = getAdapter(game, {})!;
  for (const name in samples) {
    const board: any = JSON.parse(JSON.stringify(samples[name]));
    board.game = game;
    board.type = "NORMAL";
    board.events = {};
    board.bg = { width: 960, height: 720 };
    const res: any = {};
    const chains = determineChains(board);
    res.chains = JSON.parse(JSON.stringify(chains));
    padChains(board, chains);
    res.paddedChains = JSON.parse(JSON.stringify(chains));
    res.paddedBoard = JSON.parse(JSON.stringify(board));
    const def = new Uint8Array(createBoardDef(board, chains));
    res.boarddef = Buffer.from(def).toString("hex");
    const parsed: any = parseBoardDef(def.buffer, {});
    res.parsed = JSON.parse(JSON.stringify(parsed));
    // Chain, star and gate events.
    const evBoard = JSON.parse(JSON.stringify(board));
    try {
      if (game === 3) adapter._createGateEvents(evBoard, {}, chains);
      adapter.onCreateChainEvents(evBoard, chains);
      adapter._createStarEvents(evBoard);
      if (adapter.onWriteEvents) adapter.onWriteEvents(evBoard);
      res.eventBoard = JSON.parse(JSON.stringify(evBoard));
    } catch (e: any) {
      res.eventError = String(e.message || e);
    }
    out.results[game + ":" + name] = res;
  }
}
console.log(JSON.stringify(out));
