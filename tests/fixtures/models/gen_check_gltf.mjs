// Loads the glTF/GLB files scene_to_gltf wrote (py_gltf.json) with three.js GLTFLoader and checks
// that their world-space vertices and colors equal those of model3d.js buildScene of the same scene.
globalThis.ProgressEvent = class ProgressEvent { constructor(t, o) { Object.assign(this, o); this.type = t; } };
globalThis.self = globalThis;
import * as THREE from "three";
import fs from "fs";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { buildScene } from "./model3d.mjs";
THREE.TextureLoader.prototype.load = function (url, onLoad) { const t = new THREE.Texture(); setTimeout(() => onLoad && onLoad(t), 0); return t; };
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
function tris(root) {
  root.updateMatrixWorld(true);
  const out = [];
  root.traverse((o) => {
    if (!o.isMesh) return;
    const pos = o.geometry.getAttribute("position");
    const col = o.geometry.getAttribute("color");
    const idx = o.geometry.index;
    const groups = Array.isArray(o.material) ? o.geometry.groups.filter((g) => o.material[g.materialIndex]) : [{ start: 0, count: idx ? idx.count : pos.count }];
    for (const g of groups) for (let i = g.start; i < g.start + g.count; i++) {
      const k = idx ? idx.getX(i) : i;
      const v = new THREE.Vector3().fromBufferAttribute(pos, k).applyMatrix4(o.matrixWorld);
      out.push([v.x, v.y, v.z, col ? col.getX(k) : -1].map((x) => x.toFixed(3)).join(","));
    }
  });
  return out.sort();
}
const loader = new GLTFLoader();
for (const name of Object.keys(data)) {
  for (const kind of ["glb", "gltf"]) {
    const buf = kind === "glb" ? Uint8Array.from(Buffer.from(data[name].glb, "base64")).buffer : data[name].gltf;
    const gltf = await loader.parseAsync(buf, "");
    const a = tris(gltf.scene), b = tris(buildScene(data[name].scene));
    const same = a.length === b.length && a.every((x, i) => x === b[i]);
    console.log(name, kind, "vertices", a.length, b.length, same ? "SAME" : "DIFFERENT", "materials", gltf.parser.json.materials?.length, "textures", gltf.parser.json.textures?.length ?? 0);
  }
}
