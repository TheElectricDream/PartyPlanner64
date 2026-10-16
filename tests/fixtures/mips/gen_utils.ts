// Reference outputs of utils/MIPS.ts for the Python port's tests.
import { makeInst, REG, getJALAddr, getRegSetUpperAndLower, getRegSetAddress, getFunctionLength, findCalls, findCallsInFunction } from "../packages/lib/utils/MIPS";
const out: any = { makeInst: [], upperLower: [], regSet: [], jal: [] };
const regs = [0, 4, 29, 31];
const imms = [0, 1, -1, 0x7FFF, 0x8000, -0x18, 0xFFFF, 0x12345, 0x80123456];
for (const op of ["addiu", "addu", "beq", "bne", "bgtz", "blez", "j", "jr", "jal", "lb", "sb", "lh", "sh", "lui", "lw", "sw", "ori", "ADDIU"]) {
  for (const r of regs) for (const imm of imms) {
    const n = (makeInst as any).length;
    out.makeInst.push({ op, args: [r, (r + 5) % 32, imm], out: (makeInst as any)(op, r, (r + 5) % 32, imm) });
    out.makeInst.push({ op, args: [r, imm], out: (makeInst as any)(op, r, imm) });
    out.makeInst.push({ op, args: [imm], out: (makeInst as any)(op, imm) });
  }
}
for (const a of [0, 0x80000000, 0x8000FFFF, 0x80018000, 0x12347FFF, 0xFFFF8000, 0x80123456]) out.upperLower.push({ a, out: getRegSetUpperAndLower(a) });
for (const [u, l] of [[0x8012, 0x3456], [0x8013, 0x8000], [0, 0x8000], [0xFFFF, 0xFFFF], [0x18012, 0x13456]]) out.regSet.push({ u, l, out: getRegSetAddress(u, l) });
for (const w of [0x0C000000, 0x0C0410C8, 0x0FFFFFFF]) out.jal.push({ w, out: getJALAddr(w) });
try { getJALAddr(0x27BDFFE0); } catch (e: any) { out.jalErr = e.message; }
const buf = new ArrayBuffer(64);
const dv = new DataView(buf);
const jal = 0x0C0410C8; // JAL 0x80104320
dv.setUint32(4, jal); dv.setUint32(12, jal); dv.setUint32(20, 0x03E00008); dv.setUint32(28, jal); dv.setUint32(40, 0x03E00008);
out.bufHex = Buffer.from(new Uint8Array(buf)).toString("hex");
out.findCalls = findCalls(dv, 0x80104320);
out.findCallsInFunction = [findCallsInFunction(dv, 0, 0x80104320), findCallsInFunction(dv, 24, 0x80104320)];
out.getFunctionLength = [getFunctionLength(dv, 0), getFunctionLength(dv, 20), getFunctionLength(dv, 24)];
console.log(JSON.stringify(out));
