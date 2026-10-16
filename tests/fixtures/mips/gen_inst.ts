// Generates reference outputs of mips-inst parse/print for the Python port's tests.
import { parse, print } from "mips-inst";
import * as fs from "fs";

function mulberry32(a: number) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(12345);
const rnd32 = () => Math.floor(rand() * 4294967296) >>> 0;

const src = fs.readFileSync("node_modules/mips-inst/dist/js/opcodes.js", "utf8");
const i0 = src.indexOf("const opcodeDetails = {");
const body = src.substring(i0 + "const opcodeDetails = ".length).replace(/;\s*$/, "");
const consts = `const rs="rs",rt="rt",rd="rd",fs="fs",ft="ft",fd="fd",fr="fr",sa="uint5",uint5="uint5",uint10="uint10",int16="int16",uint16="uint16",uint20="uint20",uint26="uint26",uint26shift2="uint26shift2",cc="cc",cond="cond",fmt="fmt",fmt3="fmt3";`;
const ops: any = eval(consts + "(" + body + ")");
const fmtBits: any = { S: 16, D: 17, W: 20, L: 21 };
const fmt3Bits: any = { S: 0, D: 1, W: 4, L: 5 };
function len(p: string): number {
  if (p[0] === "0" || p[0] === "1") return p.length;
  p = p.replace("?", "");
  if (p === "cc" || p === "fmt3") return 3;
  if (p === "cond") return 4;
  if (["rs","rt","rd","fs","ft","fd","fr","sa","fmt"].includes(p)) return 5;
  return parseInt(p.match(/\d+/g) as any);
}
function makeWord(op: any): number {
  let w = 0;
  for (let piece of op.format) {
    if (Array.isArray(piece)) piece = rand() < 0.5 ? piece[0] : piece[piece.length - 1];
    const l = len(piece);
    let v;
    if (piece[0] === "0" || piece[0] === "1") v = parseInt(piece, 2);
    else if (piece === "fmt") v = fmtBits[op.fmts[Math.floor(rand() * op.fmts.length)]];
    else if (piece === "fmt3") v = fmt3Bits[op.fmts[Math.floor(rand() * op.fmts.length)]];
    else v = rand() < 0.15 ? 0 : (rand() < 0.15 ? (2 ** l - 1) : Math.floor(rand() * 2 ** l));
    w = ((w * 2 ** l) + v) >>> 0;
  }
  return w >>> 0;
}
function tryit(f: () => any) {
  try { return f(); } catch (e: any) { return { error: String(e.message) }; }
}
const optSets = [
  {},
  { casing: "toLowerCase", commas: true, include$: true },
  { numBase: 10 },
  { numBase: 2, casing: "toLowerCase" },
  { numBase: 8, commas: true },
];
const printCases: any[] = [];
const words: number[] = [];
for (const name in ops) for (let k = 0; k < 12; k++) words.push(makeWord(ops[name]));
for (let k = 0; k < 1500; k++) words.push(rnd32());
words.push(0, 0xFFFFFFFF, 0x03E00008, 0x0C000000, 0x08FFFFFF);
for (const w of words) {
  const o = Math.floor(rand() * optSets.length);
  printCases.push({ w, o, out: tryit(() => print(w, optSets[o])) });
}
// parse: feed printed forms back in (various options), plus hand-written cases.
const parseInputs: string[] = [];
for (const c of printCases) {
  if (typeof c.out === "string") {
    parseInputs.push(c.out);
    if (rand() < 0.3) parseInputs.push(tryit(() => print(c.w, { casing: "toLowerCase", commas: true, include$: true })));
  }
}
const extra = [
  "ADDIU SP SP 0xFFE0", "addiu $sp, $sp, -32", "lw ra, 0x18(sp)", "LW RA 0x18 (SP)", "sw $a0, -4($sp)",
  "JAL 0x80104321", "j 0x80000000", "JR RA", "jalr a0", "jalr ra, t9", "nop", "NOP", "syscall", "break", "break 5",
  "bc1f 0x10", "bc1t 1, -3", "c.eq.s f0, f2", "c.lt.d 3, F4, F6", "C.OLT.S F0 F1", "add.s f0, f1, f2", "cvt.s.w f0, f2",
  "cvt.d.s $f0, $f2", "cvt.w.d f4 f6", "mov.d f0 f2", "mfc1 a0 f12", "mtc1 t0, F0", "mfc0 k0 12", "lwc1 f0, 8(a0)",
  "swc1 F2 -8(SP)", "ldc1 f0, 0(t0)", "madd.s f0 f1 f2 f3", "lui a0 0x8034", "ori a0 a0 0b101", "ori a0 a0 0o17",
  "addiu a0 r0 010", "addiu a0 r0 1F", "addiu a0 r0 -0x8000", "addiu a0 r0 0x18000", "sll t0 t1 31", "sra t0 t1 0x1F",
  "bogus a0", "addiu", "addiu a0", "addiu a0 a0 zz", "add a0 a0 q9", "add.x f0 f1 f2", "cvt.s.s f0 f1", "beq a0 a1 -4",
  "bne v0 r0 0x10", "lb a0 0x7FFF(a1)", "cache 1 0x10(a0)", "pref 3 0x10(a0)", "trunc.w.s f0 f2", "round.l.d f0 f2",
  "sync", "eret", "tlbwi", "teq a0 a1", "  addu   v0,v1,a0  ", "add.s.d f0 f1 f2", "c.f.s f0 f1", "c.ngt.d 7 f0 f1",
  "dsll32 a0 a1 4", "ld a0 0(sp)", "sd ra 8(sp)", "daddiu a0 a0 -1", "mult a0 a1", "mflo v0", "div r0 a0 a1",
  "ADDIU A0 A0 0X10", "jal -4", "lw $zero, ($a0)", "lw a0 (a1)", "lw a0, 4(a1", "beql a0 a1 0", "bgezal a0 -1",
];
parseInputs.push(...extra);
const parseCases = parseInputs.map(s => ({ s, out: tryit(() => parse(s)) }));
// multi-line and list forms
const multi = [
  { s: "nop\nJR RA\r\n\n  ADDU V0 V0 A0", out: tryit(() => parse("nop\nJR RA\r\n\n  ADDU V0 V0 A0")) },
  { s: "", out: tryit(() => parse("")) },
];
const objs = [
  { op: "addiu", rs: 29, rt: 29, uint16: -32 },
  { op: "add.fmt", fmt: 17, fs: 2, ft: 4, fd: 0 },
  { op: "c.cond.fmt", cond: 2, fmt: 16, fs: 1, ft: 2, cc: 3 },
];
const objCases = objs.map(o => ({ o, parse: tryit(() => parse(o)), print: tryit(() => print(o)),
  inter: tryit(() => print(parse(o), { intermediate: true })) }));
const interCases = ["addiu sp sp -32", "c.eq.s 1 f0 f2", "lw a0 4(a1)"].map(s => ({ s, out: tryit(() => parse(s, { intermediate: true })) }));
const bufCase = { words: [0x27BDFFE0, 0xAFBF0018, 0x03E00008, 0], out: print(new Uint8Array([0x27,0xBD,0xFF,0xE0,0xAF,0xBF,0x00,0x18,0x03,0xE0,0x00,0x08,0,0,0,0]).buffer) };
console.log(JSON.stringify({ optSets, printCases, parseCases, multi, objCases, interCases, bufCase }));
