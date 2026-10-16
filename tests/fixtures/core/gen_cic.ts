// Generates tests/fixtures/core/cic.json: CIC checksums of the synthetic ROMs of
// tests/lib/utils/cic_data.py (written to files named <seed>_<bootcode>.bin).
import * as fs from "fs";
import * as path from "path";
import { fixChecksum } from "../packages/lib/utils/CIC";
const dir = process.argv[2];
const out: any[] = [];
for (const name of fs.readdirSync(dir).sort()) {
  const [seed, boot] = name.replace(".bin", "").split("_").map(Number);
  const buf = new Uint8Array(fs.readFileSync(path.join(dir, name)));
  fixChecksum(buf.buffer);
  const v = new DataView(buf.buffer);
  out.push({ seed, bootcode: boot, crc1: v.getUint32(0x10), crc2: v.getUint32(0x14) });
}
fs.writeFileSync(process.argv[3], JSON.stringify(out, null, 1));
