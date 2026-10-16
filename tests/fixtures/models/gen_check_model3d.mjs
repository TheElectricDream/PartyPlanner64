// Checks static/js/lib/model3d.js: builds the Python scene descriptions (py_scenes.json, made by
// form_to_scene for the forms in models_ref.json) with three.js in node and compares the objects
// with the ones FormToThreeJs made (models_ref.json). Run from the TypeScript checkout with
// model3d.js copied next to it as model3d.mjs: node check.mjs py_scenes.json models_ref.json
import * as THREE from "three";
import fs from "fs";
import { loadScene, buildCamera, buildAnimation } from "./model3d.mjs";
THREE.TextureLoader.prototype.load = function (url, onLoad) { const t = new THREE.Texture(); t.__url = url; setTimeout(() => onLoad && onLoad(t), 0); return t; };
const S = process.argv[2];
const ref = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const py = JSON.parse(fs.readFileSync(S, "utf8"));
function dumpObj(o, materials) {
  const d = { type: o.type, name: o.name, position: o.position.toArray(), rotation: [o.rotation.x, o.rotation.y, o.rotation.z, o.rotation.order], scale: o.scale.toArray(), children: o.children.map((c) => dumpObj(c, materials)) };
  if (o.geometry) {
    const g = o.geometry;
    d.geometry = { attributes: {}, groups: g.groups.map((x) => ({ start: x.start, count: x.count, materialIndex: x.materialIndex === undefined ? null : x.materialIndex })) };
    for (const k of Object.keys(g.attributes)) d.geometry.attributes[k] = Array.from(g.attributes[k].array);
  }
  if (o.material) {
    if (Array.isArray(o.material)) d.materials = o.material.map((m) => materials.indexOf(m) >= 0 ? materials.indexOf(m) : (materials.push(m), materials.length - 1));
    else d.material = { type: o.material.type, color: o.material.color.getHex(), linewidth: o.material.linewidth };
  }
  return d;
}
let bad = 0;
function cmp(a, b, path) {
  if (typeof a === "number" && typeof b === "number") { if (Math.abs(a - b) > 1e-4 * Math.max(1, Math.abs(a))) { bad++; if (bad < 10) console.log("DIFF", path, a, b); } return; }
  if (Array.isArray(a)) { if (!Array.isArray(b) || a.length !== b.length) { bad++; console.log("LEN", path, a && a.length, b && b.length); return; } a.forEach((x, i) => cmp(x, b[i], path + "[" + i + "]")); return; }
  if (a && typeof a === "object") { for (const k of Object.keys(a)) cmp(a[k], b ? b[k] : undefined, path + "." + k); return; }
  if (a !== b) { bad++; console.log("NE", path, a, b); }
}
for (const name of Object.keys(py.scenes)) for (const v of Object.keys(py.scenes[name])) {
  const sceneJson = py.scenes[name][v];
  const root = await loadScene(sceneJson);
  const mats = [];
  const tree = dumpObj(root, mats);
  cmp(ref.forms[name].variants[v].tree, tree, name + "/" + v);
  const cam = buildCamera(sceneJson, 400, 300);
  cmp(ref.forms[name].variants[v].camera.position, cam.position.toArray(), name + "/" + v + "/cam");
  cmp(ref.forms[name].variants[v].camera.quaternion, cam.quaternion.toArray(), name + "/" + v + "/camq");
  const tsm = ref.forms[name].variants[v].materials;
  mats.forEach((m, i) => { cmp({ type: tsm[i].type, vertexColors: tsm[i].vertexColors, alphaTest: tsm[i].alphaTest }, { type: m.type, vertexColors: m.vertexColors, alphaTest: m.alphaTest }, name + "/mat" + i);
    if (tsm[i].map) cmp([tsm[i].map.flipY, tsm[i].map.wrapS, tsm[i].map.wrapT, tsm[i].map.colorSpace, tsm[i].map.magFilter, tsm[i].map.minFilter], [m.map.flipY, m.map.wrapS, m.map.wrapT, m.map.colorSpace, m.map.magFilter, m.map.minFilter], name + "/tex" + i); });
}
const clip = buildAnimation(py.anim, null);
cmp(ref.mtnx.clip, { name: clip.name, duration: clip.duration, tracks: clip.tracks.map((t) => ({ name: t.name, times: Array.from(t.times), values: Array.from(t.values), type: t.ValueTypeName })) }, "clip");
console.log("mismatches:", bad);
