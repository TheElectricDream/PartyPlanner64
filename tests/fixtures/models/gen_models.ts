// Generates reference outputs for the Python models port (tests/fixtures/models).
import * as THREE from "three";
import { HTMLCanvasElement } from "canvas-api-lite";
import { setCreateCanvas } from "../packages/lib/utils/canvas";
import { FORM } from "../packages/lib/models/FORM";
import { MTNX } from "../packages/lib/models/MTNX";
import { FormToThreeJs } from "../packages/lib/models/FormToThreeJs";
import { MtnxToThreeJs } from "../packages/lib/models/MtnxToThreeJs";

setCreateCanvas((w: number, h: number) => new HTMLCanvasElement(w, h) as any);

const textureUrls: string[] = [];
(THREE.TextureLoader.prototype as any).load = function (url: string, onLoad: any) {
  const t = new THREE.Texture();
  textureUrls.push(url);
  (t as any).__url = url;
  setTimeout(() => onLoad && onLoad(t), 0);
  return t;
};

function hex(buf: ArrayBufferLike | Uint8Array): string {
  const u8 = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  return Array.from(u8).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function dump(v: any): any {
  if (v instanceof ArrayBuffer) return { hex: hex(v) };
  if (ArrayBuffer.isView(v)) return { hex: hex(new Uint8Array(v.buffer, v.byteOffset, v.byteLength)) };
  if (Array.isArray(v)) return v.map(dump);
  if (v && typeof v === "object") {
    const o: any = {};
    for (const k of Object.keys(v)) o[k] = dump(v[k]);
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
  str(s: string) { for (const c of s) this.u8(c.charCodeAt(0)); }
  buffer() { return new Uint8Array(this.bytes).buffer; }
}

function transforms(w: W, t: number[]) { for (const v of t) w.f32(v); }

function obj1(objs: ((w: W) => void)[]) {
  const w = new W();
  w.u16(objs.length); w.u16(0x1234);
  for (const o of objs) {
    const sub = new W(); o(sub);
    // sub = [type u8, globalIndex u16, ...payload]; objSize counts from type.
    w.u16(sub.bytes.length); for (const b of sub.bytes) w.u8(b);
  }
  return w.buffer();
}
const T0 = [0, 0, 0, 0, 0, 0, 1, 1, 1];
function o3d(gi: number, children: number[], t: number[]) { return (w: W) => { w.u8(0x3d); w.u16(gi); w.u16(children.length); for (const c of children) w.u16(c); transforms(w, t); }; }
function o3a(gi: number, fi: number, fc: number, t: number[]) { return (w: W) => { w.u8(0x3a); w.u16(gi); w.u8(0); w.u16(fi); w.u16(fc); transforms(w, t); }; }
function o10(gi: number, skl: number, t: number[]) { return (w: W) => { w.u8(0x10); w.u16(gi); w.u16(skl); transforms(w, t); }; }
function o61(gi: number, t: number[]) { return (w: W) => { w.u8(0x61); w.u16(gi); transforms(w, t); }; }
function oOther(type: number, gi: number) { return (w: W) => { w.u8(type); w.u16(gi); w.u8(0); w.u8(0); }; }

function vtx1(verts: number[][], scale: number) {
  const w = new W(); w.u16(verts.length); w.u16(0); w.f32(scale);
  for (const v of verts) { w.u16(v[0] & 0xffff); w.u16(v[1] & 0xffff); w.u16(v[2] & 0xffff); w.u8(v[3]); w.u8(v[4]); w.u8(v[5]); }
  return w.buffer();
}
type Face = { type: number; entries: number[][]; mat: number; atr: number; m3: number };
function fac1(faces: Face[]) {
  const w = new W(); w.u16(faces.length); w.u16(0); w.u32(0);
  for (const f of faces) {
    w.u8(f.type);
    if (f.type === 0x30) { for (let i = 0; i < 6; i++) w.u8(i); }
    else for (const e of f.entries) { w.u16(e[0]); w.u16(e[1] & 0xffff); w.f32(e[2]); w.f32(e[3]); }
    w.u16(f.mat & 0xffff); w.u16(f.atr & 0xffff); w.u8(f.m3);
  }
  return w.buffer();
}
function mat1(colorIndices: number[]) { const w = new W(); w.u16(colorIndices.length); for (const c of colorIndices) { w.u16(1); w.u16(c); w.u16(3); w.f32(0.5); w.u16(5); } return w.buffer(); }
function col1(colors: number[]) { const w = new W(); w.u16(colors.length); for (const c of colors) w.u32(c); return w.buffer(); }
function atr1(atrs: number[][]) { const w = new W(); w.u16(atrs.length); for (const a of atrs) { w.u16(0x10); w.u8(0x2a); w.u16(0xffff); w.u8(a[0]); w.u8(a[1]); w.u8(0x2f); w.u8(0x2f); w.u8(1); w.u16(a[2]); for (let i = 0; i < 6; i++) w.u8(0); } return w.buffer(); }
function bmpRaw(gi: number, width: number, height: number, bpp: number, data: number[]) { const w = new W(); w.u16(gi); w.u16(0x127); w.u8(bpp); w.u16(width); w.u16(height); w.u16(0); w.u16(data.length); for (const b of data) w.u8(b); return w.buffer(); }
function bmpPal(gi: number, width: number, height: number, palGi: number, data: number[]) { const w = new W(); w.u16(gi); w.u16(0x128); w.u8(8); w.u16(width); w.u16(height); w.u16(palGi); w.u32(0); w.u16(data.length); for (const b of data) w.u8(b); return w.buffer(); }
function bmpGray(gi: number, fmt: number, width: number, height: number, data: number[]) { const w = new W(); w.u16(gi); w.u16(fmt); w.u8(8); w.u16(width); w.u16(height); w.u16(0); w.u16(data.length); for (const b of data) w.u8(b); return w.buffer(); }
function pal1(gi: number, colors: number[]) { const w = new W(); w.u16(gi); w.u16(colors.length); for (const c of colors) w.u32(c); return w.buffer(); }
function skl1(gi: number, entries: number[][]) {
  const w = new W(); w.u16(gi); w.u8(entries.length);
  for (const e of entries) { // [objGi, nextSibling, isParent, ...transforms]
    const start = w.pos;
    w.u8(7); w.u16(e[0]); transforms(w, e.slice(3));
    while (w.pos < start + 0x33) w.u8(0);
    w.u16(e[1]); w.u16(e[2]);
    while (w.pos < start + 56) w.u8(0);
  }
  return w.buffer();
}
function strg(strs: string[]) { const w = new W(); w.u16(strs.length); for (const s of strs) w.u8(s.length); for (const s of strs) w.str(s); return w.buffer(); }
function hbin() { const w = new W(); for (let i = 0; i < 0x14; i++) w.u8(i); w.u8(0x45); w.u8(0x46); w.u8(0x47); w.u8(0); return w.buffer(); }

function makeForm(entries: [string, ArrayBuffer][]) {
  const formObj: any = Object.create(null);
  formObj.entries = [];
  for (const [type, raw] of entries) {
    formObj.entries.push(type);
    formObj[type] = formObj[type] || [];
    formObj[type].push({ raw });
  }
  return FORM.pack(formObj);
}

const verts = [
  [0, 0, 0, 0, 127, 0], [100, 0, 0, 0, 127, 0], [100, 100, 0, 0, 0, 127], [0, 100, 0, -128, 0, 0],
  [-50, 20, 30, 50, 60, -70], [10, -20, 300, 1, 2, 3], [7, 8, 9, -3, -2, -1],
];
const faces: Face[] = [
  { type: 0x16, entries: [[0, 0, 0, 0], [1, 0, 1, 0], [2, 0, 1, 1]], mat: 0, atr: -1, m3: 0x36 },
  { type: 0x35, entries: [[0, 1, 0, 0], [1, 1, 1, 0], [2, 1, 1, 1], [3, 1, 0, 1]], mat: 1, atr: 0, m3: 0x36 },
  { type: 0x30, entries: [], mat: 0, atr: -1, m3: 0x36 },
  { type: 0x16, entries: [[4, 0, 0.25, 0.5], [5, 1, 0.5, 0.75], [6, 2, -1.5, 2.5]], mat: 0, atr: -1, m3: 0x37 },
  { type: 0x16, entries: [[4, 0, 0, 0], [5, 0, 0, 0], [6, 0, 0, 0]], mat: 2, atr: 1, m3: 0x36 },
  { type: 0x16, entries: [[0, 0, 0, 0], [5, 0, 0, 0], [6, 0, 0, 0]], mat: 0, atr: -1, m3: 0x38 },
  { type: 0x35, entries: [[3, 0, 0, 0], [4, 0, 1, 0], [5, 0, 1, 1], [6, 0, 0, 1]], mat: 1, atr: 2, m3: 0x36 },
];
const rgba = [255, 0, 0, 255, 0, 255, 0, 128, 0, 0, 255, 255, 10, 20, 30, 0];

const forms: any = {};
forms.simple = makeForm([
  ["HBINMODE", hbin()],
  ["OBJ1", obj1([o3d(0, [1, 2], [1, 2, 3, 10, 20, 30, 1, 2, 0.5]), o3a(1, 0, 5, [0, 5, 0, 0, 90, 0, 1, 1, 1]), o3a(2, 5, 2, T0), oOther(0x3e, 3), o61(4, [1, 2, 3, 0, 0, 0, 1, 1, 1])])],
  ["VTX1", vtx1(verts, 0.5)],
  ["FAC1", fac1(faces)],
  ["MAT1", mat1([0, 1, 2])],
  ["COL1", col1([0xff000000, 0x00ff8000, 0x123456ff])],
  ["ATR1", atr1([[0x2c, 0x2d, 5], [0x2e, 0x99, 6], [0x2d, 0x2c, 99]])],
  ["BMP1", bmpRaw(5, 2, 2, 32, rgba)],
  ["BMP1", bmpGray(6, 0x125, 2, 2, [0x1f, 0xa5, 0xff, 0x00])],
  ["STRG", strg(["model", "x"])],
]);
forms.skeleton = makeForm([
  ["OBJ1", obj1([o10(0, 7, [5, 6, 7, 45, 0, 0, 2, 2, 2]), o3a(2, 0, 2, T0), o3a(3, 3, 1, [0, 0, 1, 0, 0, 0, 1, 1, 1]), o3d(4, [3], T0)])],
  ["VTX1", vtx1(verts, 2)],
  ["FAC1", fac1(faces)],
  ["MAT1", mat1([0, 1, 2])],
  ["COL1", col1([0xff000000, 0x00ff8000, 0x123456ff])],
  ["ATR1", atr1([[0x2d, 0x2d, 8]])],
  ["PAL1", pal1(9, [0xff0000ff, 0x00ff00ff, 0x0000ffff, 0xffffff00])],
  ["BMP1", bmpPal(8, 4, 2, 9, [0x01, 0x23, 0x30, 0x12])],
  ["SKL1", skl1(7, [[2, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1], [3, 1, 0, 1, 1, 1, 0, 90, 0, 1, 1, 1], [4, 0, 0, 2, 2, 2, 0, 0, 30, 1, 1, 1]])],
]);
forms.camera = makeForm([
  ["OBJ1", obj1([o3d(0, [1], T0), o3a(1, 0, 1, T0), o61(2, [10, 20, 30, 0, 0, 0, 1, 1, 1]), o61(3, [0, 5, 0, 0, 0, 0, 1, 1, 1]), o61(4, T0)])],
  ["VTX1", vtx1(verts, 1)],
  ["FAC1", fac1(faces)],
  ["MAT1", mat1([0, 1, 2])],
  ["COL1", col1([0xff000000, 0x00ff8000, 0x123456ff])],
  ["BMP1", bmpGray(1, 0x124, 2, 2, [0x1f, 0xa5])],
]);

function dumpObj(o: any, materials: any[]): any {
  const d: any = { type: o.type, name: o.name,
    position: o.position.toArray(), rotation: [o.rotation.x, o.rotation.y, o.rotation.z, o.rotation.order],
    scale: o.scale.toArray(), children: o.children.map((c: any) => dumpObj(c, materials)) };
  if (o.geometry) {
    const g = o.geometry;
    d.geometry = { attributes: {} as any, groups: g.groups.map((x: any) => ({ start: x.start, count: x.count, materialIndex: x.materialIndex === undefined ? null : x.materialIndex })) };
    for (const k of Object.keys(g.attributes)) d.geometry.attributes[k] = Array.from(g.attributes[k].array);
  }
  if (o.material) {
    if (Array.isArray(o.material)) d.materials = o.material.map((m: any) => materials.indexOf(m) >= 0 ? materials.indexOf(m) : (materials.push(m), materials.length - 1));
    else d.material = { type: o.material.type, color: o.material.color.getHex(), linewidth: o.material.linewidth };
  }
  return d;
}
function dumpMaterial(m: any) {
  return { type: m.type, vertexColors: m.vertexColors, alphaTest: m.alphaTest,
    map: m.map ? { url: m.map.__url, flipY: m.map.flipY, wrapS: m.map.wrapS, wrapT: m.map.wrapT, colorSpace: m.map.colorSpace,
      magFilter: m.map.magFilter, minFilter: m.map.minFilter } : null };
}

async function main() {
  const out: any = { forms: {}, consts: { MirroredRepeatWrapping: THREE.MirroredRepeatWrapping, RepeatWrapping: THREE.RepeatWrapping, ClampToEdgeWrapping: THREE.ClampToEdgeWrapping, LinearFilter: THREE.LinearFilter, LinearMipmapLinearFilter: THREE.LinearMipmapLinearFilter } };
  for (const name of Object.keys(forms)) {
    const buf = forms[name];
    const form = FORM.unpack(buf)!;
    const entry: any = { input: hex(buf), unpacked: dump(form), repacked: hex(FORM.pack(form)), variants: {} };
    for (const variant of ["default", "wire", "normals", "camera"]) {
      const conv = new FormToThreeJs();
      if (variant === "wire") { conv.showWireframe = true; conv.showTextures = false; conv.bgColor = 0x336699; }
      if (variant === "normals") { conv.showVertexNormals = true; conv.showWireframe = true; }
      if (variant === "camera") conv.useFormCamera = true;
      const model = await conv.createModel(form);
      const materials: any[] = [];
      const tree = dumpObj(model, materials);
      const cam = conv.createCamera(form, 400, 300);
      entry.variants[variant] = { tree, materials: materials.map(dumpMaterial),
        camera: { position: cam.position.toArray(), quaternion: cam.quaternion.toArray(), fov: cam.fov, near: cam.near, far: cam.far } };
    }
    out.forms[name] = entry;
  }

  // MTNX
  const w = new W();
  const tracks = [
    { type: 0x17, dim: 0x45, obj: 0, frames: [[0, 1.5], [30, -2], [10, 4]] },
    { type: 0x4c, dim: 0x47, obj: 1, frames: [[0, 90], [60, 180]] },
    { type: 0x1b, dim: 0x46, obj: 7, frames: [[5, 2]] },
    { type: 0x99, dim: 0x45, obj: 0, frames: [[0, 1]] },
  ];
  w.str("MTNX"); w.u32(0); w.u16(tracks.length); w.u16(120);
  const offsAt = w.pos; w.u32(0); w.u32(0); w.u32(0);
  const trackPtrs = w.pos; for (const _ of tracks) w.u32(0);
  const trackOffs: number[] = [];
  let kfIndex = 0, dataIndex = 0;
  const kfs: number[] = [], data: number[] = [];
  for (const t of tracks) {
    trackOffs.push(w.pos);
    w.u8(t.type); w.u8(t.dim); w.u8(1); w.u8(2); w.u16(3); w.u16(120); w.u8(4); w.u8(t.obj);
    w.u16(kfIndex); w.u16(dataIndex); w.u16(t.frames.length);
    for (const [f, v] of t.frames) { kfs.push(f); data.push(v, v * 2, v * 3); }
    kfIndex += t.frames.length; dataIndex += t.frames.length * 3;
  }
  const ds = w.pos; for (let i = 0; i < tracks.length; i++) w.u8(0x10 + i);
  while (w.pos % 4) w.u8(0);
  const kfOff = w.pos; for (const k of kfs) w.u16(k);
  while (w.pos % 4) w.u8(0);
  const dataOff = w.pos; for (const d of data) w.f32(d);
  const mbytes = w.bytes;
  const set32 = (at: number, v: number) => { for (let i = 0; i < 4; i++) mbytes[at + i] = (v >>> (24 - 8 * i)) & 0xff; };
  set32(offsAt, ds); set32(offsAt + 4, kfOff); set32(offsAt + 8, dataOff);
  trackOffs.forEach((o, i) => set32(trackPtrs + i * 4, o));
  const mbuf = new Uint8Array(mbytes).buffer;
  const mtnx = MTNX.unpack(mbuf)!;
  const animConv = new MtnxToThreeJs();
  animConv.form = FORM.unpack(forms.skeleton)!;
  const clip = animConv.createClip(mtnx);
  out.mtnx = { input: hex(mbuf), unpacked: dump(mtnx),
    clip: { name: clip.name, duration: clip.duration, tracks: clip.tracks.map((t) => ({ name: t.name, times: Array.from(t.times), values: Array.from(t.values), type: t.ValueTypeName })) } };

  // replaceBMP
  const form = FORM.unpack(forms.skeleton)!;
  FORM.replaceBMP(form, 0, new Uint8Array([0x32, 0x10, 0x03, 0x21]).buffer, { colors: [0x11223344, 0x55667788, 0x99aabbcc, 0xddeeff00] });
  out.replaceBMP = hex(FORM.pack(form));
  console.log(JSON.stringify(out));
}
main();
