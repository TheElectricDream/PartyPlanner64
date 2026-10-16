// Generates reference outputs for the Python audio port (tests/fixtures/audio).
import { decodeVADPCM } from "../packages/lib/audio/vadpcm";
import { extractWavFromSound, extractWavSound } from "../packages/lib/audio/wav";
import { parseGameMidi, createGameMidi } from "../packages/lib/audio/midi";
import { S2 } from "../packages/lib/audio/S2";
import { MBF0 } from "../packages/lib/audio/MBF0";
import { SBF0 } from "../packages/lib/audio/SBF0";
import { T3 } from "../packages/lib/audio/T3";
import { FXD0 } from "../packages/lib/audio/FXD0";

let seed = 12345;
function rnd(): number {
  seed = (Math.imul(seed, 1103515245) + 12345) >>> 0;
  return (seed >>> 8) / 0x1000000;
}
function rint(n: number) { return Math.floor(rnd() * n); }
function hex(buf: ArrayBufferLike | Uint8Array): string {
  const u8 = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  return Array.from(u8).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function dump(v: any): any {
  if (v instanceof ArrayBuffer) return { hex: hex(v) };
  if (Array.isArray(v)) return v.map(dump);
  if (v && typeof v === "object") {
    const o: any = {};
    for (const k of Object.keys(v)) {
      if (k.startsWith("_")) continue;
      o[k] = dump(v[k]);
    }
    return o;
  }
  return v;
}

class W {
  bytes: number[] = [];
  get pos() { return this.bytes.length; }
  u8(v: number) { this.bytes.push(v & 0xff); }
  u16(v: number) { this.u8(v >> 8); this.u8(v); }
  u32(v: number) { this.u16(v >>> 16); this.u16(v & 0xffff); }
  f32(v: number) { const b = new DataView(new ArrayBuffer(4)); b.setFloat32(0, v); for (let i = 0; i < 4; i++) this.u8(b.getUint8(i)); }
  set32(at: number, v: number) { for (let i = 0; i < 4; i++) this.bytes[at + i] = (v >>> (24 - 8 * i)) & 0xff; }
  set16(at: number, v: number) { this.bytes[at] = (v >> 8) & 0xff; this.bytes[at + 1] = v & 0xff; }
  align(n: number) { while (this.bytes.length % n) this.u8(0); }
  buffer() { return new Uint8Array(this.bytes).buffer; }
}

const out: any = {};

// --- VADPCM ---
out.vadpcm = [];
for (let t = 0; t < 6; t++) {
  const order = 2;
  const npredictors = 1 + rint(4);
  const predictors: number[] = [];
  for (let i = 0; i < order * npredictors * 8; i++) predictors.push(rint(4096) - 2048 + (t === 5 ? rint(60000) - 30000 : 0));
  const half = t % 3 === 2;
  const len = (half ? 5 : 9) * (3 + rint(20)) + rint(4);
  const tbl = new Uint8Array(len + 8);
  for (let i = 0; i < tbl.length; i++) tbl[i] = rint(256);
  const book: any = { order, npredictors, predictors };
  const outRaw = new ArrayBuffer(len * 8);
  const n = decodeVADPCM(new DataView(tbl.buffer), outRaw, len, book, half);
  out.vadpcm.push({ tbl: hex(tbl), len, book, half, samples: n, out: hex(outRaw.slice(0, n * 2)) });
}

// --- Synthetic B1 + S2 / MBF0 ---
function buildB1(w: W, tblLen: number) {
  const start = w.pos;
  const at = (o: number) => o - start;
  w.u16(0x4231); w.u16(1); // B1, one bank
  const bankPtr = w.pos; w.u32(0);
  w.align(4);
  const bankOff = w.pos; w.set32(bankPtr, at(bankOff));
  const instCount = 2;
  w.u16(instCount); w.u8(0); w.u8(0); w.u32(22050); w.u32(0);
  const instPtrs: number[] = [];
  for (let i = 0; i < instCount; i++) { instPtrs.push(w.pos); w.u32(0); }
  for (let i = 0; i < instCount; i++) {
    const instOff = w.pos; w.set32(instPtrs[i], at(instOff));
    w.u8(100 + i); w.u8(64); w.u8(5); w.u8(0);
    for (let k = 0; k < 8; k++) w.u8(k);
    w.u16(200); w.u16(2);
    const soundPtrs = [w.pos, w.pos + 4]; w.u32(0); w.u32(0);
    for (let s = 0; s < 2; s++) {
      const sndOff = w.pos; w.set32(soundPtrs[s], at(sndOff));
      const envPtr = w.pos; w.u32(0);
      const kmPtr = w.pos; w.u32(0);
      const wavePtr = w.pos; w.u32(0);
      w.u8(60 + s); w.u8(110 + i); w.u8(0); w.u8(0);
      const envOff = w.pos; w.set32(envPtr, at(envOff));
      w.u32(1000); w.u32(2000); w.u32(3000); w.u16(127); w.u16(100);
      const kmOff = w.pos; w.set32(kmPtr, at(kmOff));
      w.u8(0); w.u8(127); w.u8(s * 60); w.u8(s * 60 + 59); w.u8(48 + s * 12 + i); w.u8(s ? 0xf6 : 5);
      w.align(4);
      const waveOff = w.pos; w.set32(wavePtr, at(waveOff));
      const raw = i === 1 && s === 1;
      const waveBase = (i * 2 + s) * 64;
      w.u32(waveBase); w.u32(raw ? 40 : 45); w.u8(raw ? 1 : 0); w.u8(0); w.u16(0);
      if (raw) {
        w.u32(8); w.u32(0); // loop offset relative to info
        w.u32(2); w.u32(18); w.u32(0xffffffff);
      } else {
        const loopPtr = w.pos; w.u32(0);
        const bookPtr = w.pos; w.u32(0);
        if (s === 0) {
          const loopOff = w.pos; w.set32(loopPtr, at(loopOff));
          w.u32(16); w.u32(64); w.u32(3); for (let k = 0; k < 16; k++) w.u16(k * 3);
        }
        const bookOff = w.pos; w.set32(bookPtr, at(bookOff));
        w.u32(2); w.u32(2); for (let k = 0; k < 32; k++) w.u16((rint(4096) - 2048) & 0xffff);
      }
    }
  }
  w.align(8);
  return w.pos - start;
}

const tblLen = 256;
const tblBytes: number[] = []; for (let i = 0; i < tblLen; i++) tblBytes.push(rint(256));

function buildGameMidi(): number[] {
  // A tiny hand-made game midi: header of 16 track offsets + division.
  const w = new W();
  for (let i = 0; i < 16; i++) w.u32(0);
  w.u32(0x30); // division
  const t0 = w.pos; w.set32(0, t0);
  w.u8(0); w.u8(0xff); w.u8(0x51); w.u8(0x07); w.u8(0xa1); w.u8(0x20); // tempo
  w.u8(0); w.u8(0xc0); w.u8(3); // program
  w.u8(0); w.u8(0xb0); w.u8(7); w.u8(100); // volume
  w.u8(0); w.u8(0xff); w.u8(0x2e); w.u8(0); w.u8(0xff); // loop start
  w.u8(0); w.u8(0x90); w.u8(60); w.u8(100); w.u8(0x18); // note with duration
  w.u8(0x0c); w.u8(62); w.u8(90); w.u8(0x81); w.u8(0x00); // running status note, 2 byte duration
  w.u8(0x30); w.u8(0xe0); w.u8(0); w.u8(0x40); // pitch bend
  w.u8(0x10); w.u8(0x90); w.u8(64); w.u8(80); w.u8(0x0c);
  w.u8(0x40); w.u8(0xff); w.u8(0x2f); w.u8(0x00);
  const t1 = w.pos; w.set32(4, t1);
  w.u8(0); w.u8(0x91); w.u8(48); w.u8(70); w.u8(0x60);
  w.u8(0x08); w.u8(50); w.u8(70); w.u8(0x08);
  w.u8(0x08); w.u8(0xd1); w.u8(30);
  w.u8(0x60); w.u8(0xff); w.u8(0x2f); w.u8(0x00);
  w.align(8);
  return w.bytes;
}

{
  // S2
  const w = new W();
  const midiCount = 2;
  w.u16(0x5332); w.u16(midiCount);
  const t1 = w.pos; for (let i = 0; i < midiCount; i++) { w.u32(0); w.u32(0); }
  const t2 = w.pos; for (let i = 0; i < midiCount; i++) { w.u8(i); w.u8(0x7f); w.u8(0xff); w.u8(0xff); w.u32(0); w.u32(0); w.u32(0); }
  w.u32(0xffffffff);
  w.align(16);
  const b1Off = w.pos;
  const b1Len = buildB1(w, tblLen);
  const tblOff = w.pos;
  for (const b of tblBytes) w.u8(b);
  w.align(8);
  for (let i = 0; i < midiCount; i++) {
    w.set32(t2 + i * 16 + 4, b1Off); w.set32(t2 + i * 16 + 8, b1Len); w.set32(t2 + i * 16 + 12, tblOff);
  }
  const gm = buildGameMidi();
  for (let i = 0; i < midiCount; i++) {
    w.set32(t1 + i * 8, w.pos); w.set32(t1 + i * 8 + 4, gm.length);
    for (const b of gm) w.u8(b);
  }
  w.align(16);
  const buf = w.buffer();
  const s2 = new S2(new DataView(buf));
  const packed = new ArrayBuffer(s2.getByteLength());
  const packedLen = s2.pack(packed);
  const wavs: string[] = [];
  const bank = s2.soundbanks.banks[0];
  for (let i = 0; i < bank.instruments.length; i++)
    for (let s = 0; s < bank.instruments[i].sounds.length; s++)
      wavs.push(hex(extractWavSound(s2.tbl, bank, i, s)));
  out.s2 = { input: hex(buf), parsed: dump(s2), packed: hex(packed), packedLen, byteLength: s2.getByteLength(), wavs,
    midi: hex(parseGameMidi(new DataView(s2.midis[0].buffer), s2.midis[0].buffer.byteLength)) };
}

{
  // MBF0
  const w = new W();
  const midiCount = 3;
  w.u32(0x4d424630); w.u32(midiCount);
  for (let i = 0; i < 0x38; i++) w.u8(i === 0x10 ? 0x56 : 0);
  const table = w.pos;
  for (let i = 0; i < midiCount; i++) { w.u8(i === 1 ? 1 : 0); w.u8(0x6f); w.u8(i % 2); w.u8(0); w.u32(0x07000000); w.u32(0); w.u32(0); }
  const extra = w.pos; w.u32(0); w.u32(0); w.u32(0); w.u32(0);
  const gm = buildGameMidi();
  const m0 = w.pos; for (const b of gm) w.u8(b); w.align(8);
  const m1 = w.pos; for (const b of gm.slice(0, gm.length - 8)) w.u8(b ^ 0); w.align(8);
  const offs = [m0, m1, m0];
  const lens = [gm.length, gm.length - 8, gm.length];
  for (let i = 0; i < midiCount; i++) { w.set32(table + i * 16 + 8, offs[i]); w.set32(table + i * 16 + 12, lens[i]); }
  w.align(16);
  const b1Off = w.pos; const b1Len = buildB1(w, tblLen);
  const tblOff = w.pos; for (const b of tblBytes) w.u8(b); w.align(16);
  w.set32(extra, b1Off); w.set32(extra + 4, b1Len); w.set32(extra + 8, tblOff); w.set32(extra + 12, tblLen);
  const buf = w.buffer();
  const mbf0 = new MBF0(new DataView(buf));
  const packed = new ArrayBuffer(mbf0.getByteLength());
  const packedLen = mbf0.pack(packed);
  out.mbf0 = { input: hex(buf), parsed: dump(mbf0), packed: hex(packed), packedLen, byteLength: mbf0.getByteLength() };
}

function buildSoundSimpleTable(w: W, count: number, base: number, sampleRates: boolean) {
  // Entries are 16 bytes; offsets inside are relative to the table start (base).
  const entries = w.pos;
  for (let i = 0; i < count; i++) { w.u32(0); w.u32(sampleRates ? 16000 + i : 0); w.u32(0); w.u8(64); w.u8(100 + i); w.u8(0); w.u8(0); }
  for (let i = 0; i < count; i++) {
    const env = w.pos - base; w.u32(10); w.u32(20); w.u32(30); w.u16(127); w.u16(0);
    w.align(4);
    const wave = w.pos - base;
    const raw = i === 1;
    w.u32(i * 64); w.u32(raw ? 30 : 36); w.u8(raw ? 1 : 0); w.u8(i === 2 ? 0x30 : 0); w.u16(0);
    if (raw) { w.u32(0); w.u32(0); }
    else {
      w.u32(0); const bp = w.pos; w.u32(0);
      w.set32(bp, w.pos - base); w.u32(2); w.u32(1); for (let k = 0; k < 16; k++) w.u16((rint(4096) - 2048) & 0xffff);
    }
    w.set32(entries + i * 16, env); w.set32(entries + i * 16 + 8, wave);
  }
}

{
  // SBF0
  const w = new W();
  w.u32(0x53424630); w.u32(2);
  while (w.pos < 0x74) w.u8(0);
  const count = 3;
  w.set32(0x44, count);
  buildSoundSimpleTable(w, count, 0x74, true);
  w.align(16);
  const tblOff = w.pos; for (const b of tblBytes) w.u8(b);
  w.set32(0x54, tblOff); w.set32(0x58, tblLen);
  const buf = w.buffer();
  const sbf0 = new SBF0(new DataView(buf));
  out.sbf0 = { input: hex(buf), parsed: dump(sbf0),
    wavs: sbf0.sounds.map((s) => hex(extractWavFromSound(sbf0.tbl, s, s.sampleRate))) };
}

{
  // T3
  const w = new W();
  const fx = 2;
  w.u16(0x5433); w.u16(fx);
  w.u32(0); w.u16(0x1002); w.u16(11025);
  w.u32(0); w.u16(0x2000); w.u16(16000);
  const h = w.pos;
  for (let i = 0; i < 11; i++) w.u32(0);
  const count = 3;
  w.set32(h + 4, count);
  const tableStart = w.pos;
  buildSoundSimpleTable(w, count, tableStart, false);
  w.align(16);
  const tblOff = w.pos; for (const b of tblBytes) w.u8(b);
  w.set32(h + 0xc, tblOff); w.set32(h + 0x14, tblLen);
  const buf = w.buffer();
  const t3 = new T3(new DataView(buf));
  out.t3 = { input: hex(buf), parsed: dump(t3) };
}

{
  const w = new W();
  w.u32(0x46584430); w.u32(2); w.u32(0); w.u32(0);
  for (let i = 0; i < 0x208 * 2; i++) w.u8(rint(256));
  const buf = w.buffer();
  out.fxd0 = { input: hex(buf), parsed: dump(new FXD0(new DataView(buf))) };
}

// --- MIDI round trips ---
function vl(w: W, v: number) {
  const bytes = [v & 0x7f];
  while ((v >>= 7)) bytes.unshift((v & 0x7f) | 0x80);
  for (const b of bytes) w.u8(b);
}
function buildStdMidi(variant: number): ArrayBuffer {
  const w = new W();
  const ntracks = 1 + (variant % 3);
  w.u32(0x4d546864); w.u32(6); w.u16(ntracks > 1 ? 1 : 0); w.u16(ntracks); w.u16(96 + variant * 24);
  for (let t = 0; t < ntracks; t++) {
    w.u32(0x4d54726b); const lenAt = w.pos; w.u32(0);
    const start = w.pos;
    const ch = t === 2 ? 9 : t;
    if (t === 0) {
      vl(w, 0); w.u8(0xff); w.u8(0x03); w.u8(4); for (const c of "Song") w.u8(c.charCodeAt(0));
      vl(w, 0); w.u8(0xff); w.u8(0x51); w.u8(3); w.u8(0x07); w.u8(0xa1); w.u8(0x20);
      vl(w, 0); w.u8(0xf0); vl(w, 3); w.u8(1); w.u8(2); w.u8(0xf7);
    }
    vl(w, 0); w.u8(0xc0 | ch); w.u8(rint(16));
    vl(w, 0); w.u8(0xb0 | ch); w.u8(7); w.u8(90 + rint(30));
    w.u8(0); w.u8(10); w.u8(64); // running status controller
    const notes = 6 + rint(10 + variant * 4);
    let running = false;
    for (let n = 0; n < notes; n++) {
      const note = 40 + rint(40);
      const style = rint(4);
      vl(w, rint(3) * 24 + (variant === 4 ? 300 : 0));
      if (running) { w.u8(note); w.u8(60 + rint(60)); } else { w.u8(0x90 | ch); w.u8(note); w.u8(60 + rint(60)); }
      running = rint(2) === 0;
      if (n === 3 && variant > 0) { vl(w, 5); w.u8(0xe0 | ch); w.u8(0); w.u8(0x50); running = false; }
      if (n === 4 && variant === 2) { vl(w, 0); w.u8(0xd0 | ch); w.u8(40); running = false; }
      const dur = 12 + rint(4) * 12 + (variant === 3 ? 20000 : 0);
      if (style === 0) { vl(w, dur); w.u8(0x80 | ch); w.u8(note); w.u8(0); running = false; }
      else if (style === 1 && running) { vl(w, dur); w.u8(note); w.u8(0); }
      else { vl(w, dur); w.u8(0x90 | ch); w.u8(note); w.u8(0); running = true; }

    }
    vl(w, 10); w.u8(0xff); w.u8(0x2f); w.u8(0);
    w.set32(lenAt, w.pos - start);
  }
  return w.buffer();
}
out.midi = [];
for (let v = 0; v < 6; v++) {
  const std = buildStdMidi(v);
  const entry: any = { std: hex(std) };
  for (const loop of [false, true]) {
    const game = createGameMidi(std, { loop });
    const key = loop ? "loop" : "noloop";
    entry[key] = game ? hex(game) : null;
    if (game) {
      try {
        entry[key + "_parsed"] = hex(parseGameMidi(new DataView(game), game.byteLength));
      } catch (e: any) {
        entry[key + "_parsed_error"] = String(e);
      }
    }
  }
  out.midi.push(entry);
}

// Game midis with FE repeats and loop counts.
{
  const w = new W();
  for (let i = 0; i < 16; i++) w.u32(0);
  w.u32(0x60);
  w.set32(0, w.pos);
  const pat = w.pos;
  w.u8(0); w.u8(0x90); w.u8(60); w.u8(100); w.u8(0x10);
  w.u8(0x10); w.u8(62); w.u8(100); w.u8(0x10);
  // repeat the 8 bytes from pat (FE, distance hi, lo, count)
  const fePos = w.pos;
  w.u8(0xfe); const dist = fePos + 4 - pat; w.u8(dist >> 8); w.u8(dist & 0xff); w.u8(9);
  w.u8(0x10); w.u8(0xff); w.u8(0x2e); w.u8(1); w.u8(0xff);
  const loopBody = w.pos;
  w.u8(0x08); w.u8(0x90); w.u8(64); w.u8(0xfe); w.u8(0xfe); w.u8(0x08); // velocity 0xFE escaped
  w.u8(0x08); w.u8(0xff); w.u8(0x2d); w.u8(0xff); w.u8(0);
  const back = w.pos + 4 - loopBody;
  w.u32(back);
  w.u8(0x20); w.u8(0xff); w.u8(0x2f); w.u8(0);
  w.align(8);
  const buf = w.buffer();
  out.gameMidiRepeat = { input: hex(buf), parsed: hex(parseGameMidi(new DataView(buf), buf.byteLength)) };
}

console.log(JSON.stringify(out));
