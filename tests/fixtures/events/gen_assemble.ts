// Test assembly/compilation of custom events and board code, with errors.
// Usage: node ref/run.mjs ref/events_assemble.ts <fixtures/events dir> > assemble.json
import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import "../packages/lib/events/builtin/events.include";
import { createCustomEvent, CustomAsmHelper, validateCustomEvent } from "../packages/lib/events/customevents";
import { testAdditionalBgCodeAllGames, defaultAdditionalBgAsm, defaultAdditionalBgC } from "../packages/lib/events/additionalbg";
import { testGetAudioCodeAllGames, defaultGetAudioAsm, defaultGetAudioC } from "../packages/lib/events/getaudiochoice";
import { Game } from "../packages/lib/types";

(process as any).exit = (code: number) => { throw new Error("process.exit(" + code + ")"); };
(async () => {
  const dir = path.join(process.argv[2], "corpus");
  const out: any = { events: {}, bg: {}, audio: {} };
  const origError = console.error;
  console.error = () => {}; const origLog = (globalThis as any).__log;
  for (const f of fs.readdirSync(dir).sort()) {
    if (!f.endsWith(".s") && !f.endsWith(".c")) continue;
    // (SmallerC calls process.exit on errors under node; the patched exit throws instead, as in a browser.)
    const code = fs.readFileSync(path.join(dir, f), "utf8");
    const lang = f.endsWith(".c") ? 1 : 0;
    const res: any = {};
    let ev: any;
    try { ev = createCustomEvent(lang, code); } catch (e) { res.create = String(e); out.events[f] = res; continue; }
    res.validate = await validateCustomEvent(ev).then((x) => x, (e) => String(e));
    res.games = {};
    for (const game of [Game.MP1_USA, Game.MP2_USA, Game.MP3_USA, Game.MP1_JPN]) {
      try {
        const r: any = await CustomAsmHelper.testCustomEvent(lang, code, ev.parameters, { game });
        res.games[game] = typeof r === "string" ? r :
          crypto.createHash("md5").update(new Uint8Array(r)).digest("hex") + ":" + r.byteLength;
      } catch (e) { res.games[game] = { error: String(e) }; }
    }
    out.events[f] = res;
  }
  const bad = "  j missing_label\n  nop";
  for (const game of [1, 2, 3]) {
    const board: any = { game, additionalbg: ["x", "y"], audioData: [{}, {}] };
    out.bg[game] = [
      await testAdditionalBgCodeAllGames(defaultAdditionalBgAsm, 0, board),
      await testAdditionalBgCodeAllGames(bad, 0, board),
      await testAdditionalBgCodeAllGames(defaultAdditionalBgC, 1, board),
    ];
    out.audio[game] = [
      await testGetAudioCodeAllGames(defaultGetAudioAsm, 0, board),
      await testGetAudioCodeAllGames(bad, 0, board),
      await testGetAudioCodeAllGames(defaultGetAudioC, 1, board),
    ];
  }
  console.error = origError;
  process.stdout.write(JSON.stringify(out, null, 1));
})().catch((e) => { process.stderr.write("FAIL " + (e && e.stack) + "\n"); process.exit(2); });
