// Builds three.js objects from the scene and animation descriptions made in Python
// (partyplanner64/lib/models/form_to_scene.py and mtnx_to_animation.py). Together they
// replace FormToThreeJs.ts and MtnxToThreeJs.ts: the objects built here are the ones
// FormToThreeJs made (Object3D hierarchy named by global index, ZYX rotations,
// multi-material meshes of MeshBasicMaterials with vertex colors, textures with
// flipY off, wireframes from EdgesGeometry, vertex normal helpers).
import * as THREE from "three";

function floats(value) {
  if (typeof value === "string") {
    const bin = atob(value);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Float32Array(bytes.buffer);
  }
  return new Float32Array(value || []);
}

function buildGeometry(desc) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(floats(desc.position), 3));
  for (const [name, size] of [["normal", 3], ["color", 3], ["uv", 2]]) {
    const array = floats(desc[name]);
    if (array.length > 0) geometry.setAttribute(name, new THREE.BufferAttribute(array, size));
  }
  for (const group of desc.groups || []) {
    geometry.addGroup(group.start, group.count, group.material_index ?? undefined);
  }
  return geometry;
}

function buildTexture(desc, promises) {
  const loader = new THREE.TextureLoader();
  let texture;
  promises.push(new Promise((resolve) => {
    texture = loader.load(desc.image, resolve, undefined, resolve);
  }));
  texture.flipY = desc.flip_y;
  texture.wrapS = THREE[desc.wrap_s];
  texture.wrapT = THREE[desc.wrap_t];
  texture.magFilter = THREE[desc.mag_filter];
  texture.minFilter = THREE[desc.min_filter];
  texture.colorSpace = desc.color_space === "srgb" ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  return texture;
}

function buildMaterial(desc, textures) {
  const params = { vertexColors: !!desc.vertex_colors };
  if (desc.alpha_test !== undefined) params.alphaTest = desc.alpha_test;
  if (desc.map !== undefined && desc.map !== null) params.map = textures[desc.map];
  return new THREE.MeshBasicMaterial(params);
}

/** The lines VertexNormalsHelper(mesh, size, color) drew for a detached mesh. */
function buildNormalsHelper(geometry, size, color) {
  const position = geometry.getAttribute("position");
  const normal = geometry.getAttribute("normal");
  const count = normal ? normal.count : 0;
  const lines = new Float32Array(count * 6);
  const v = new THREE.Vector3();
  const n = new THREE.Vector3();
  for (let i = 0; i < count; i++) {
    v.fromBufferAttribute(position, i);
    n.fromBufferAttribute(normal, i).normalize().multiplyScalar(size).add(v);
    lines.set([v.x, v.y, v.z, n.x, n.y, n.z], i * 6);
  }
  const lineGeometry = new THREE.BufferGeometry();
  lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
  const helper = new THREE.LineSegments(
    lineGeometry,
    new THREE.LineBasicMaterial({ color, toneMapped: false }),
  );
  helper.type = "VertexNormalsHelper";
  helper.matrixAutoUpdate = false;
  return helper;
}

function buildNode(desc, ctx) {
  switch (desc.type) {
    case "mesh":
      return new THREE.Mesh(ctx.geometries[desc.geometry], ctx.materials);
    case "wireframe":
      return new THREE.LineSegments(
        new THREE.EdgesGeometry(ctx.geometries[desc.geometry]),
        new THREE.LineBasicMaterial({ color: desc.color, linewidth: desc.linewidth }),
      );
    case "normals":
      return buildNormalsHelper(ctx.geometries[desc.geometry], desc.size, desc.color);
    default: {
      const obj = new THREE.Object3D();
      obj.name = desc.name || "";
      obj.position.fromArray(desc.position);
      obj.rotation.set(desc.rotation[0], desc.rotation[1], desc.rotation[2], desc.rotation_order || "XYZ");
      obj.scale.fromArray(desc.scale);
      for (const child of desc.children || []) obj.add(buildNode(child, ctx));
      return obj;
    }
  }
}

function build(sceneJson) {
  const promises = [];
  const textures = (sceneJson.textures || []).map((t) => buildTexture(t, promises));
  const ctx = {
    geometries: (sceneJson.geometries || []).map(buildGeometry),
    materials: (sceneJson.materials || []).map((m) => buildMaterial(m, textures)),
  };
  const root = sceneJson.root ? buildNode(sceneJson.root, ctx) : new THREE.Object3D();
  return { root, promises };
}

/**
 * Builds the model's THREE.Object3D (textures appear once their images load;
 * use loadScene to wait for them).
 */
export function buildScene(sceneJson) {
  return build(sceneJson).root;
}

/** Like buildScene, resolving once the textures have loaded (as FormToThreeJs.createModel). */
export function loadScene(sceneJson) {
  const { root, promises } = build(sceneJson);
  return Promise.all(promises).then(() => root);
}

/** The camera FormToThreeJs.createCamera made, for a viewer of width x height. */
export function buildCamera(sceneJson, width, height) {
  const desc = sceneJson.camera || { fov: 75, near: 1, far: 999999, position: [0, 0, 500] };
  const camera = new THREE.PerspectiveCamera(desc.fov, width / height, desc.near, desc.far);
  camera.position.fromArray(desc.position);
  if (desc.look_at) camera.lookAt(new THREE.Vector3().fromArray(desc.look_at));
  return camera;
}

/** The scene background color. */
export function buildBackground(sceneJson) {
  return new THREE.Color(sceneJson.background || 0);
}

/**
 * Builds the THREE.AnimationClip MtnxToThreeJs made. Its tracks address the nodes
 * of `root` (the object buildScene returned) by name, so play it with an
 * AnimationMixer on root (or on a scene containing it).
 */
export function buildAnimation(animJson, root) {
  const tracks = (animJson.tracks || []).map(
    (t) => new THREE.VectorKeyframeTrack(t.name, t.times, t.values),
  );
  return new THREE.AnimationClip(animJson.name || "MTNX", animJson.duration, tracks);
}

/** Disposes the geometries, materials and textures of a built object (models.tsx disposeTHREEObj). */
export function disposeObject(obj) {
  if (!obj) return;
  for (const child of obj.children) disposeObject(child);
  if (obj.geometry) obj.geometry.dispose();
  const materials = Array.isArray(obj.material) ? obj.material : obj.material ? [obj.material] : [];
  for (const material of materials) {
    if (material.map) material.map.dispose();
    material.dispose();
  }
}
