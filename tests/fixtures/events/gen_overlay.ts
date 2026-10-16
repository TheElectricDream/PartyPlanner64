// getAdditionalBgAsmForOverlay / getAudioIndexAsmForOverlay / writeCustomEvent outputs.
// Usage: node ref/run.mjs ref/events_overlay.ts <fixtures/events dir> > overlay.json
import * as fs from "fs";
import * as path from "path";
import "../packages/lib/events/builtin/events.include";
import { romhandler } from "../packages/lib/romhandler";
import { getAdditionalBgAsmForOverlay, defaultAdditionalBgC } from "../packages/lib/events/additionalbg";
import { getAudioIndexAsmForOverlay, defaultGetAudioC } from "../packages/lib/events/getaudiochoice";
import { writeCustomEvent } from "../packages/lib/events/customevents";
import { dummyBoardInfo } from "../packages/lib/adapter/boardinfobase";
import { Game } from "../packages/lib/types";

(romhandler as any).getROMGame = () => Game.MP3_USA;
(romhandler as any).romIsLoaded = () => false;
(async () => {
  const corpus = path.join(process.argv[2], "corpus");
  const good = fs.readFileSync(path.join(corpus, "good.c"), "utf8");
  const crlf = fs.readFileSync(path.join(corpus, "crlf.s"), "utf8");
  const out: any = {};
  out.bg = [
    await getAdditionalBgAsmForOverlay({} as any, 5, [6, 7]),
    await getAdditionalBgAsmForOverlay({ additionalbgcode: "LI V0 ADDITIONAL_BG_2\nJR RA\nNOP" } as any, 5, null),
    await getAdditionalBgAsmForOverlay({ additionalbgcode: { language: 1, code: defaultAdditionalBgC } } as any, 5, [6]),
  ];
  out.audio = [
    await getAudioIndexAsmForOverlay({} as any, [3]),
    await getAudioIndexAsmForOverlay({ audioSelectCode: { language: 0, code: "LI V0 MUSIC_TRACK_INDEX_2\nJR RA\nNOP" } } as any, [3, 9]),
    await getAudioIndexAsmForOverlay({ audioSelectCode: { language: 1, code: defaultGetAudioC } } as any, [3, 9]),
  ];
  const info: any = {
    game: Game.MP3_USA, audioIndices: [2], boardInfo: dummyBoardInfo, board: { additionalbg: ["a"] },
    chains: [[0, 1], [2, 3, 4]], curSpaceIndex: 1,
  };
  out.write = [
    await writeCustomEvent(null as any, { id: "Good C", parameterValues: { coins: 3, target: 4, flag: true } } as any, info, 1, good, {}),
    await writeCustomEvent(null as any, { id: "CRLF Event" } as any, info, 0, crlf, {}),
  ];
  process.stdout.write(JSON.stringify(out));
})();
