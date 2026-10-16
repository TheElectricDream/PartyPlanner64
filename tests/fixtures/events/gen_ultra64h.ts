import { ultra64h } from "../packages/lib/events/includes/ultra64h";
import * as fs from "fs";
fs.writeFileSync(process.argv[2], ultra64h);
