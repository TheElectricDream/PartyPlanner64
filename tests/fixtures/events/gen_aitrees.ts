// parseDecisionTree on a synthetic tree. Output: fixtures/events/aitrees.json
import { parseDecisionTree } from "../packages/lib/ai/aitrees";
const buf = new ArrayBuffer(0x100);
const v = new DataView(buf);
const base = 0x00100000; // RAM address (no 0x80000000 prefix) of offset 0
function node(off: number, type: number, data: number, decision: number) {
  v.setUint8(off, type); v.setUint32(off + 4, data); v.setUint32(off + 8, decision);
}
// Root at 0x10: hasCoins -> subtree at 0x40; star -> result; leaf -> result.
node(0x10, 1, 20, 0x80000000 | (base + 0x40));
node(0x1C, 2, 0x0F, 0x1A2B3C4D);
node(0x28, 0, 0, 0x10010102);
// Subtree at 0x40: turnsElapsed -> result; leaf.
node(0x40, 7, 10, 0x00013264);
node(0x4C, 0, 0xDEADBEEF, 0x064C9932);
const out: any = { bytes: Array.from(new Uint8Array(buf)), base };
for (const game of [1, 2, 3]) out[game] = parseDecisionTree(v, 0x10, base, game as any);
console.log(JSON.stringify(out));
