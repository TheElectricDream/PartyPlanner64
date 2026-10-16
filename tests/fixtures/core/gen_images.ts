// Generates tests/fixtures/core/images.json: image codec reference outputs.
import * as fs from "fs";
import { RGBA5551toRGBA32, RGBA5551fromRGBA32 } from "../packages/lib/utils/img/RGBA5551";
import { GrayscaleToRGBA32 } from "../packages/lib/utils/img/Grayscale";
import { BMPtoRGBA, BMPfromRGBA } from "../packages/lib/utils/img/BMP";
import { fromTiles, toTiles } from "../packages/lib/utils/img/tiler";
import { fromPack, toPack } from "../packages/lib/utils/img/ImgPack";
import { isFontPack, fontPackToRGBA32 } from "../packages/lib/utils/img/FontPack";
import { decode } from "../packages/lib/utils/img/HVQ";
import { make8Bit } from "../packages/lib/utils/img/RGBA32";
import { cutFromWhole, invertColor } from "../packages/lib/utils/image";
import { toHexString, readBitAtOffset, readByteAtBitOffset, hash } from "../packages/lib/utils/arrays";
import { mpFormatToPlainText, toU32, fromU32 } from "../packages/lib/utils/string";
import { compress } from "../packages/lib/utils/compression";
import resizeImageData from "resize-image-data";

let seed = 777;
function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
function randBytes(n: number, alphabet = 256) { const a = new Uint8Array(n); for (let i = 0; i < n; i++) a[i] = Math.floor(rnd() * alphabet); return a; }
const b64 = (u: ArrayBufferLike | Uint8Array) => Buffer.from(u instanceof Uint8Array ? u : new Uint8Array(u)).toString("base64");
function attempt(fn: () => any) { try { return fn(); } catch (e) { return { error: String((e as any).message || e) }; } }

const out: any = {};

out.rgba5551to = [[1, 1], [13, 7], [64, 48]].map(([w, h]) => { const i = randBytes(w * h * 2); return { w, h, input: b64(i), output: b64(RGBA5551toRGBA32(i.buffer, w, h)) }; });
out.rgba5551from = [[1, 1], [13, 7], [64, 48]].map(([w, h]) => { const i = randBytes(w * h * 4); return { w, h, input: b64(i), output: b64(RGBA5551fromRGBA32(i.buffer, w, h)) }; });
out.grayscale = [[8, 5, 3], [8, 4, 4], [4, 7, 3], [4, 4, 4], [4, 1, 1]].map(([bpp, w, h]) => { const i = randBytes(Math.ceil(w * h * bpp / 8)); return { bpp, w, h, input: b64(i), output: b64(GrayscaleToRGBA32(i.buffer, w, h, bpp)) }; });

out.bmpTo = [];
for (const [inBpp, outBpp, palLen] of [[8, 16, 256], [8, 32, 256], [4, 16, 16], [4, 32, 16], [2, 16, 4], [2, 32, 4], [8, 16, 10], [4, 8, 16]]) {
  const i = randBytes(23, inBpp === 8 && palLen < 256 ? palLen + 2 : 256);
  const pal = Array.from(randBytes(palLen * 4)).map((v, k) => k).slice(0, palLen).map(() => Math.floor(rnd() * 0x100000000));
  const r = attempt(() => b64(BMPtoRGBA(i.buffer, pal, inBpp, outBpp)));
  out.bmpTo.push({ inBpp, outBpp, palette: pal, input: b64(i), output: r });
}
out.bmpFrom = [];
for (const [inBpp, outBpp, n, alpha] of [[16, 8, 40, 4], [32, 8, 40, 300], [8, 8, 17, 9], [32, 4, 8, 3], [32, 4, 0, 3]]) {
  const i = randBytes(n * inBpp / 8, alpha);
  const r = attempt(() => { const [bmp, pal] = BMPfromRGBA(i.buffer, inBpp, outBpp); return { bmp: b64(bmp), palette: pal }; });
  out.bmpFrom.push({ inBpp, outBpp, input: b64(i), output: r });
}

out.tiles = [];
for (const [xc, yc, xw, yw] of [[3, 2, 8, 4], [2, 3, 128, 48], [1, 1, 4, 1], [5, 1, 40, 12]]) {
  const img = randBytes(xc * xw * yc * yw);
  const tiles = toTiles(Array.from(img), xc, yc, xw, yw);
  const back = fromTiles(tiles.map(t => new DataView(t)), xc, yc, xw, yw);
  out.tiles.push({ xc, yc, xw, yw, input: b64(img), tiles: tiles.map(b64), back: b64(back) });
}
// fromTiles with widths not divisible by 4 (4-byte copies run across rows).
out.tilesOdd = [];
for (const [xc, yc, xw, yw] of [[2, 2, 6, 3]]) {
  const tiles = []; for (let i = 0; i < xc * yc; i++) tiles.push(randBytes(xw * yw + 8));
  out.tilesOdd.push({ xc, yc, xw, yw, tiles: tiles.map(b64), output: attempt(() => b64(fromTiles(tiles.map(t => new DataView(t.buffer)), xc, yc, xw, yw))) });
}

// ImgPack round trips.
out.packs = [];
function packCase(name: string, infos: any[], outBpp: number, bmpBpp: number, old?: Uint8Array) {
  const inputs = infos.map(i => ({ width: i.width, height: i.height, bpp: i.bpp, src: b64(i.src) }));
  const infosAB = infos.map(i => ({ ...i, src: i.src.buffer }));
  const r = attempt(() => {
    const pack = toPack(infosAB, outBpp, bmpBpp, old ? old.buffer : undefined);
    const back = attempt(() => fromPack(pack).map((i: any) => ({ width: i.width, height: i.height, src: i.src ? b64(i.src) : null })));
    return { pack: b64(pack), back };
  });
  out.packs.push({ name, inputs, outBpp, bmpBpp, old: old ? b64(old) : null, output: r });
}
packCase("32to16", [{ width: 6, height: 4, bpp: 32, src: randBytes(96) }, { width: 3, height: 5, bpp: 32, src: randBytes(60) }], 16, 0);
packCase("16to16", [{ width: 5, height: 3, bpp: 16, src: randBytes(30) }], 16, 0);
packCase("32to32", [{ width: 2, height: 2, bpp: 32, src: randBytes(16) }], 32, 0);
packCase("bmp16", [{ width: 8, height: 6, bpp: 16, src: randBytes(96, 3) }], 16, 8);
packCase("bmp32", [{ width: 4, height: 4, bpp: 32, src: randBytes(64, 2) }], 16, 8);
packCase("old", [{ width: 4, height: 2, bpp: 32, src: randBytes(32) }], 16, 0, randBytes(64));
packCase("bad", [{ width: 4, height: 2, bpp: 8, src: randBytes(8) }], 16, 0);
// Hand-made packs: grayscale 4/8 bit and 32 bit, and palettes.
out.rawPacks = [];
function rawPack(bitCount: number, w: number, h: number, palette: number[]) {
  const imgBytes = bitCount >= 8 ? bitCount * w * h / 8 : w * h / (8 / bitCount);
  const len = 0x20 + 12 + imgBytes + palette.length * 2;
  const buf = new Uint8Array(len); const v = new DataView(buf.buffer);
  v.setUint32(0, 0x20); v.setUint32(12, 0x20 + 12 + imgBytes); v.setUint16(16, 1); v.setUint8(25, bitCount);
  v.setUint32(0x20, 0x2c); v.setUint16(0x24, w); v.setUint16(0x26, h);
  const img = randBytes(imgBytes, palette.length ? Math.min(palette.length, 1 << bitCount) : 256); buf.set(img, 0x2c);
  palette.forEach((c, i) => v.setUint16(0x2c + imgBytes + i * 2, c));
  out.rawPacks.push({ pack: b64(buf), output: attempt(() => fromPack(buf.buffer).map((i: any) => ({ width: i.width, height: i.height, src: i.src ? b64(i.src) : null }))) });
}
rawPack(8, 5, 3, []); rawPack(4, 6, 3, []); rawPack(32, 2, 3, []); rawPack(16, 3, 3, []);
rawPack(8, 4, 3, [0x1234, 0xffff, 0x0001]); rawPack(4, 4, 4, [0xf801, 0x07c1, 0x003f, 0x0000]);
rawPack(2, 8, 2, [1, 2, 3, 4]);

// Font packs.
out.fonts = [];
function fontPack(w: number, h: number, palLen: number, imgCount: number, charCount: number, base = 12) {
  const cp = w * h;
  const palOff = palLen ? base : 0;
  const imgOff = imgCount ? base + palLen * 2 : 0;
  const charsOff = base + palLen * 2 + imgCount * cp;
  const len = charsOff + charCount * cp / 2;
  const buf = new Uint8Array(len); const v = new DataView(buf.buffer);
  v.setUint32(0, palOff); v.setUint32(4, imgOff); v.setUint32(8, charsOff);
  for (let i = 0; i < palLen; i++) v.setUint16(base + i * 2, Math.floor(rnd() * 0x10000));
  buf.set(randBytes(imgCount * cp, Math.max(palLen, 1)), base + palLen * 2);
  buf.set(randBytes(charCount * cp / 2), charsOff);
  out.fonts.push({ pack: b64(buf), isFontPack: isFontPack(buf.buffer), output: attempt(() => { const p = fontPackToRGBA32(buf.buffer); return { images: p.images.map(b64), chars: p.chars.map(b64), charWidth: p.charWidth, charHeight: p.charHeight, bpp: p.bpp }; }) });
}
fontPack(10, 12, 4, 2, 5); fontPack(8, 8, 0, 0, 7); fontPack(8, 8, 3, 1, 3); fontPack(10, 12, 0, 0, 3);
fontPack(7, 7, 0, 0, 3);
out.fontsSmall = [new Uint8Array(20), new Uint8Array(40)].map(b => ({ pack: b64(b), isFontPack: isFontPack(b.buffer) }));

// HVQ decode.
out.hvq = [];
{
  const raw = randBytes(64);
  const c = new Uint8Array(compress(3, new DataView(raw.buffer)) as ArrayBuffer);
  const f = new Uint8Array(8 + c.length); const v = new DataView(f.buffer); v.setUint32(0, 3); v.setUint32(4, 64); f.set(c, 8);
  out.hvq.push({ input: b64(f), output: b64(decode(new DataView(f.buffer)) as ArrayBuffer) });
  const plain = randBytes(40); plain[0] = 1;
  out.hvq.push({ input: b64(plain), output: b64(decode(new DataView(plain.buffer)) as ArrayBuffer) });
  const h = randBytes(40); h.set([0x48, 0x56, 0x51, 0x32], 0);
  out.hvq.push({ input: b64(h), output: b64(decode(new DataView(h.buffer)) as ArrayBuffer) });
}

// resize-image-data.
out.resize = [];
for (const [sw, sh, dw, dh, alg] of [[5, 4, 9, 7, "bilinear-interpolation"], [9, 7, 4, 3, "bilinear-interpolation"], [6, 6, 6, 3, "bilinear-interpolation"], [3, 1, 7, 2, "bilinear-interpolation"], [7, 5, 3, 9, "nearest-neighbor"], [1, 1, 3, 3, "bilinear-interpolation"]] as any[]) {
  const data = randBytes(sw * sh * 4);
  const img = { width: sw, height: sh, data: new Uint8ClampedArray(data.buffer) };
  const r = resizeImageData(img as any, dw, dh, alg);
  out.resize.push({ sw, sh, dw, dh, alg, input: b64(data), output: b64(new Uint8Array(r.data.buffer)) });
}

// make8Bit, image helpers.
{
  const d = randBytes(4 * 12); const u32 = new Uint32Array(d.slice().buffer); make8Bit(u32, 4, 3);
  out.make8Bit = { input: b64(d), output: b64(new Uint8Array(u32.buffer)) };
  const src = randBytes(10 * 6 * 4);
  out.cut = [[32, 2, 1, 5, 3], [16, 0, 0, 10, 6], [8, 3, 2, 4, 4]].map(([bpp, x, y, w, h]) => ({ bpp, x, y, w, h, output: b64(cutFromWhole(src.buffer, bpp === 32 ? 10 : bpp === 16 ? 20 : 40, 6, bpp, x, y, w, h)) }));
  out.cutSrc = b64(src);
  out.invert = [0, 0xffffff, 0x123456, 0xabcdef].map(c => [c, invertColor(c)]);
  const a = randBytes(37);
  out.arrays = { input: b64(a), hex: toHexString(a.buffer), hex8: toHexString(a.buffer, 20, 8), bits: Array.from({ length: 30 }, (_, i) => readBitAtOffset(a.buffer, i * 7)), bytes: Array.from({ length: 30 }, (_, i) => readByteAtBitOffset(a.buffer, i * 9)), hash: hash(a.buffer, 3, 20), hashOob: hash(a.buffer, 30, 20) };
  out.strings = { plain: ["<RED>Hi　 and 　<BLUE>〇〉", "", "【】〈"].map(mpFormatToPlainText), u32: ["FORM", "ÿþýü", "HVQ2"].map(toU32), from: [0x464f524d, 0xfffefdfc].map(fromU32) };
}
fs.writeFileSync(process.argv[2], JSON.stringify(out));
