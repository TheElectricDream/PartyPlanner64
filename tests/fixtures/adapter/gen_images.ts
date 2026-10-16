// Reference outputs for the adapters' image writing, with images that need no
// resampling (so the canvas and Pillow agree): boot splash branding, board select
// icon compositing and hover mask, overview background shift, logos and backgrounds.
import { romhandler } from "../packages/lib/romhandler";
import { getAdapter } from "../packages/lib/adapter/adapters";
import { setCreateCanvas, setCreateImage } from "../packages/lib/utils/canvas";
import { createCanvasNode, createImageNode } from "../apps/cli/CanvasImpl";
import { toPack } from "../packages/lib/utils/img/ImgPack";
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

// A deterministic RGBA32 image.
export function pattern(w: number, h: number, seed: number) {
  const buf = new ArrayBuffer(w * h * 4);
  const u8 = new Uint8Array(buf);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      u8[i] = (x * 3 + y + seed) & 0xff;
      u8[i + 1] = (x * y + seed * 5) & 0xff;
      u8[i + 2] = (x + y * 7) & 0xff;
      u8[i + 3] = 255;
    }
  }
  return buf;
}

// A logo pack like the game's (NINTENDO / Hudson): 320x240, byte 0x1A = 0x20.
function logoPack(seed: number) {
  const pack = toPack([{ src: pattern(320, 240, seed), width: 320, height: 240, bpp: 32 }], 16, 0);
  new Uint8Array(pack)[0x1a] = 0x20;
  return pack;
}

const imgs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const gameIds: any = { 1: "CLBE", 2: "NMWE", 3: "NMVE" };
const results: any = {};

function setup(game: number) {
  const log: any[] = [];
  const files = new Map<string, ArrayBuffer>();
  const mainfs = {
    get(d: number, f: number) { const k = `${d}/${f}`; if (!files.has(k)) files.set(k, new ArrayBuffer(0x2000)); return files.get(k)!; },
    has(d: number, f: number) { return files.has(`${d}/${f}`); },
    write(d: number, f: number, c: ArrayBuffer) { files.set(`${d}/${f}`, c); log.push(["mainfs.write", d, f, blob(c)]); },
  };
  const hvqfs = {
    writeBackground(dir: number, imgData: ImageData, w: number, h: number) { log.push(["hvqfs.writeBackground", dir, w, h, blob(imgData.data.buffer)]); },
    getDirectoryCount() { return 100; },
  };
  const rom = { getGame: () => gameIds[game], getMainFS: () => mainfs, getHVQFS: () => hvqfs };
  (romhandler as any).getRom = () => rom;
  (romhandler as any).getROMGame = () => gameIds[game];
  (romhandler as any).getGameVersion = () => game;
  return { log, files, adapter: getAdapter(game, {}) as any };
}

(async () => {
  // Boot splash branding.
  for (const game of [1, 2, 3]) {
    const { log, files, adapter } = setup(game);
    const n = adapter.nintendoLogoFSEntry, h = adapter.hudsonLogoFSEntry;
    const nPack = logoPack(1), hPack = logoPack(2);
    files.set(`${n[0]}/${n[1]}`, nPack);
    files.set(`${h[0]}/${h[1]}`, hPack);
    await adapter._brandBootSplashscreen();
    results["brand" + game] = { packs: [blob(nPack), blob(hPack)], log };
    // Branding off.
    const off: any = getAdapter(game, { writeBranding: false });
    log.length = 0;
    await off._brandBootSplashscreen();
    results["brandOff" + game] = log.slice();
  }

  // MP2 board select icon (and its hover mask).
  for (const icon of ["icon", "icon_opaque"]) {
    const { log, files, adapter } = setup(2);
    const selectPack = toPack([{ src: pattern(200, 120, 3), width: 200, height: 120, bpp: 32 }], 16, 0);
    files.set("9/15", selectPack);
    const info = { name: "x", img: { boardSelectIconCoords: [39, 20], boardSelectIconMask: 20 } };
    await adapter._writeBoardSelectIcon({ otherbg: { boardselecticon: imgs[icon] } }, info);
    const board: any = { otherbg: {} };
    files.set("9/15", selectPack);
    adapter._parseBoardSelectIcon(board, info);
    results["icon_" + icon] = { pack: blob(selectPack), log, parsedIcon: board.otherbg.boardselecticon };
  }

  {
    const { log, adapter } = setup(2);
    await adapter._writeOverviewBackground(8, imgs.bg320);
    await adapter.onWriteBoardLogoImg({ otherbg: { boardlogo: imgs.mp2_logo } }, { name: "x", img: { introLogoImg: 406, pauseLogoImg: 380 } });
    await adapter.onWriteBoardSelectImg({ otherbg: { boardselect: imgs.mp2_select } }, { name: "x", img: { boardSelectImg: 30 } });
    await adapter._writeBackground(5, imgs.bg320, 320, 240);
    await adapter._writeAdditionalBackgrounds({ additionalbg: [imgs.bg_small, imgs.bg_small], bg: { width: 96, height: 72 } });
    results.mp2 = log;
  }

  {
    const { log, adapter } = setup(3);
    const info = { name: "x", img: { splashLogoImg: 22, splashLogoTextImg: 28, pauseLogoImg: 125, statsLogoImg: [19, 105], boardSelectImg: 72 } };
    await adapter.onWriteBoardLogoImg({ otherbg: { boardlogo: imgs.logo_large, boardlogotext: imgs.logo_text,
      boardlogomedium: imgs.logo_medium, boardlogosmall: imgs.logo_small } }, info);
    await adapter.onWriteBoardLogoImg({ otherbg: {} }, info);
    await adapter.onWriteBoardSelectImg({ otherbg: { boardselect: imgs.mp3_select } }, info);
    results.mp3 = log;
  }

  {
    const { log, adapter } = setup(1);
    await adapter.onWriteBoardLogoImg({ otherbg: { boardlogo: imgs.mp1_intro } },
      { name: "x", img: { introLogoImg: [356, 357], introLogoImgDimens: [272, 112] } });
    results.mp1 = log;
  }

  console.log(JSON.stringify(results));
})();
