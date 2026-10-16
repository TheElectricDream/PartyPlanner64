// Models: browse the ROM's 3D models (MainFS FORM files) and animations (MTNX), view them in
// three.js, export glTF/GLB/OBJ (views/models.tsx). The server converts the FORMs
// (GET /api/models/...); js/lib/model3d.js builds the three.js objects.
import { $, $$, api, act, esc, loadCss, toast, download } from '../api.js';

let THREE = null;
let OrbitControls = null;
let model3d = null;

let root = null;
let app = null;
let list = null;              // {models, first}
let anims = [];               // [{dir, file}] for the model shown
let current = null;           // {dir, file}
let anim = null;              // {dir, file} or null
let sceneJson = null;
let animJson = null;
let filter = '';
const view = { textures: true, wireframe: false, normals: false, camera: false, bg: 0x000000 };

// three.js
let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let mixer = null;
let action = null;
let clock = null;
let modelObj = null;
let running = false;
let timer = 0;
let frameReq = 0;
let resizeObs = null;
let paused = false;
let loadSeq = 0;

const key = m => `${m.dir}/${m.file}`;
const hex4 = n => n.toString(16).toUpperCase().padStart(4, '0');

export async function init(container, theApp) {
  loadCss('models');
  root = container;
  app = theApp;
  root.innerHTML = `<div class="layout models-page">
      <aside class="sidebar">
        <section class="card mdl-list-card">
          <div class="card-head"><h2>Model</h2><span class="pill" id="mdlCount">…</span></div>
          <input id="mdlFilter" class="input" placeholder="Filter, e.g. 2/" spellcheck="false" title="Show only the models whose directory/file contains this text (press M to come here)">
          <ul class="list-box mdl-list" id="mdlList" tabindex="0" title="The MainFS files that hold a model (FORM). ↑ and ↓ step through them."><li class="empty">Loading…</li></ul>
        </section>
        <section class="card">
          <div class="card-head"><h2>Animation</h2><span class="muted small" id="mdlAnimCount"></span></div>
          <select id="mdlAnim" class="input" title="Play an animation (MTNX) on the model (press A to come here)"><option value="">None</option></select>
          <p class="hint" id="mdlAnimHint"></p>
          <label class="toggle mdl-opt" title="Offer only the animations in the model's directory (a setting)"><input type="checkbox" id="mdlLimitAnims"><span></span>Limit Animations</label>
        </section>
        <section class="card">
          <div class="card-head"><h2>View</h2></div>
          <div class="mdl-toggles">
            <label class="toggle" title="Draw the model's textures"><input type="checkbox" data-view="textures" checked><span></span>Textures</label>
            <label class="toggle" title="Draw the edges of the model's triangles"><input type="checkbox" data-view="wireframe"><span></span>Wireframe</label>
            <label class="toggle" title="Use the camera defined by the model"><input type="checkbox" data-view="camera"><span></span>Camera</label>
            <label class="toggle" id="mdlNormalsOpt" title="Draw the vertex normals (advanced)"><input type="checkbox" data-view="normals"><span></span>Vertex Normals</label>
          </div>
          <div class="field">
            <span class="field-label">Background</span>
            <div class="segmented mdl-bg" role="group" aria-label="Background">
              <button type="button" data-bg="000000" class="active" title="Change the background to black"><i style="background:#000"></i>Black</button>
              <button type="button" data-bg="FFFFFF" title="Change the background to white"><i style="background:#fff"></i>White</button>
              <button type="button" data-bg="C6E7FF" id="mdlBgMotion" title="Change the background to the MP3 motion test's (0xC6E7FF)"><i style="background:#C6E7FF"></i>Motion Test</button>
            </div>
          </div>
          <label class="toggle mdl-opt" title="Draw 30 frames per second instead of every frame, for better performance (a setting)"><input type="checkbox" id="mdlLimitFps"><span></span>Limit FPS</label>
        </section>
        <section class="card">
          <div class="card-head"><h2>Export</h2></div>
          <div class="mdl-export">
            <button type="button" class="btn btn-primary" id="mdlGltf" title="Export the model to a glTF file">glTF</button>
            <button type="button" class="btn" id="mdlObj" title="Export the model to a Wavefront OBJ file">OBJ</button>
          </div>
          <label class="toggle mdl-opt" title="Create a binary GLB container when exporting to glTF (a setting)"><input type="checkbox" id="mdlGlb"><span></span>Use GLB Container</label>
        </section>
      </aside>
      <main class="main">
        <div class="viewer mdl-viewer" id="mdlViewer">
          <div class="viewer-toolbar">
            <button type="button" class="btn btn-sm" id="mdlReset" title="Put the camera back where it started">Reset View</button>
            <button type="button" class="btn btn-sm" id="mdlPause" title="Pause or resume the animation" disabled>Pause</button>
            <span class="mdl-name mono" id="mdlName"></span>
          </div>
          <div class="legend" id="mdlLegend" hidden></div>
          <div class="viewer-empty" id="mdlEmpty"><b>No Model</b><span>Pick a model on the left.</span></div>
        </div>
      </main>
    </div>`;
  wire();
  try {
    THREE = await import('three');
    ({ OrbitControls } = await import('/static/vendor/three/OrbitControls.js'));
  } catch (e) {
    showEmpty('3D Unavailable', `three.js couldn't be loaded: ${e.message}`);
    return;
  }
  try {
    model3d = await import('../lib/model3d.js');
  } catch (e) {
    console.error(e);
    model3d = null;
  }
  app.on('rom', () => {
    list = null;
    current = null;
    clearModel();
    if (app.page === 'models') load();
  });
  app.on('state', syncSettings);
  syncSettings();
}

export function show() {
  syncSettings();
  if (!list) load();
  start();
}

export function hide() {
  stop();
}

function wire() {
  $('#mdlFilter', root).addEventListener('input', e => {
    filter = e.target.value.trim();
    renderList();
  });
  const listEl = $('#mdlList', root);
  listEl.addEventListener('click', e => {
    const li = e.target.closest('li[data-key]');
    if (li) selectModel(list.models.find(m => key(m) === li.dataset.key));
  });
  listEl.addEventListener('keydown', e => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const items = $$('li[data-key]', listEl);
    const i = items.findIndex(li => li.classList.contains('active'));
    const next = items[Math.max(0, Math.min(items.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))];
    if (next) {
      next.click();
      next.scrollIntoView({ block: 'nearest' });
    }
  });
  $('#mdlAnim', root).addEventListener('change', e => {
    const v = e.target.value;
    anim = v ? { dir: +v.split('/')[0], file: +v.split('/')[1] } : null;
    loadAnimation();
  });
  for (const input of $$('[data-view]', root)) {
    input.addEventListener('change', () => {
      view[input.dataset.view] = input.checked;
      // As the original: textures or wireframe, at least one.
      if (!view.textures && !view.wireframe) {
        const other = input.dataset.view === 'textures' ? 'wireframe' : 'textures';
        view[other] = true;
        $(`[data-view="${other}"]`, root).checked = true;
      }
      // As the original: the model is made again with the new options.
      loadModel(input.dataset.view === 'camera');
    });
  }
  for (const b of $$('[data-bg]', root)) {
    b.addEventListener('click', () => {
      view.bg = parseInt(b.dataset.bg, 16);
      for (const o of $$('[data-bg]', root)) o.classList.toggle('active', o === b);
      if (scene) scene.background = new THREE.Color(view.bg);
      $('#mdlViewer', root).style.background = `#${b.dataset.bg}`;
      // The wireframe is drawn in the background's inverse colour.
      if (view.wireframe) loadModel();
    });
  }
  const settingToggle = (id, setting, after) => $(id, root).addEventListener('change', e => act(async () => {
    await api('/api/settings', { [setting]: e.target.checked });
    await app.refresh();
    after?.();
  }));
  settingToggle('#mdlLimitFps', 'models.limitfps');
  settingToggle('#mdlLimitAnims', 'models.limitAnimations', () => loadAnimList());
  settingToggle('#mdlGlb', 'models.useGLB', () => syncSettings());
  $('#mdlGltf', root).addEventListener('click', () => exportModel(app.setting('models.useGLB') ? 'glb' : 'gltf'));
  $('#mdlObj', root).addEventListener('click', () => exportModel('obj'));
  $('#mdlReset', root).addEventListener('click', () => placeCamera());
  $('#mdlPause', root).addEventListener('click', () => {
    paused = !paused;
    $('#mdlPause', root).textContent = paused ? 'Play' : 'Pause';
  });
  // The original's shortcuts: M for the model list, A for the animations.
  root.addEventListener('keydown', e => {
    if (e.target.matches('input, select, textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === 'm') { e.preventDefault(); $('#mdlList', root).focus(); }
    if (k === 'a') { e.preventDefault(); $('#mdlAnim', root).focus(); }
  });
  root.tabIndex = -1;
}

function syncSettings() {
  if (!root) return;
  $('#mdlLimitFps', root).checked = !!app.setting('models.limitfps');
  $('#mdlLimitAnims', root).checked = !!app.setting('models.limitAnimations');
  $('#mdlGlb', root).checked = !!app.setting('models.useGLB');
  $('#mdlGltf', root).textContent = app.setting('models.useGLB') ? 'glTF (GLB)' : 'glTF';
  $('#mdlNormalsOpt', root).hidden = !app.setting('ui.advanced');
  $('#mdlBgMotion', root).hidden = !app.setting('ui.debug');
}

function showEmpty(title, text) {
  const el = $('#mdlEmpty', root);
  el.hidden = false;
  el.innerHTML = `<b>${esc(title)}</b><span>${esc(text)}</span>`;
}

async function load() {
  if (!app.state?.rom) {
    $('#mdlList', root).innerHTML = '<li class="empty">Open a ROM to see its models.</li>';
    $('#mdlCount', root).textContent = 'No ROM';
    showEmpty('No ROM Open', 'Open a ROM to see its 3D models.');
    return;
  }
  $('#mdlList', root).innerHTML = '<li class="empty">Reading the ROM\'s files…</li>';
  showEmpty('Reading the ROM…', 'Finding the models and animations.');
  list = await act(() => api('/api/models')) || null;
  if (!list) {
    $('#mdlList', root).innerHTML = '<li class="empty">The models couldn\'t be read.</li>';
    showEmpty('Models Unavailable', 'The ROM\'s models couldn\'t be read.');
    return;
  }
  renderList();
  if (!list.models.length) {
    showEmpty('No Models', 'This ROM has no FORM files.');
    return;
  }
  if (!model3d) {
    showEmpty('Viewer Unavailable', 'js/lib/model3d.js couldn\'t be loaded, so models can be exported but not shown.');
  }
  selectModel(list.first || list.models[0]);
}

function renderList() {
  const el = $('#mdlList', root);
  if (!list) return;
  $('#mdlCount', root).textContent = `${list.models.length}`;
  const shown = list.models.filter(m => !filter || key(m).includes(filter));
  if (!shown.length) {
    el.innerHTML = `<li class="empty">${list.models.length ? `No model matches “${esc(filter)}”.` : 'No models.'}</li>`;
    return;
  }
  el.innerHTML = shown.map(m => `<li data-key="${key(m)}" class="${current && key(current) === key(m) ? 'active' : ''}"
      title="MainFS ${key(m)} (0x${hex4(m.dir)}/0x${hex4(m.file)})"><span class="mono">${key(m)}</span>
      <span class="muted small mono">${hex4(m.dir)}/${hex4(m.file)}</span></li>`).join('');
}

async function selectModel(m) {
  if (!m) return;
  current = m;
  anim = null;
  for (const li of $$('li[data-key]', $('#mdlList', root))) li.classList.toggle('active', li.dataset.key === key(m));
  $('#mdlName', root).textContent = `Model ${key(m)}`;
  await loadAnimList();
  await loadModel(true);
}

async function loadAnimList() {
  if (!current) return;
  const limited = !!app.setting('models.limitAnimations');
  const res = await act(() => api(`/api/models/animations${limited ? `?dir=${current.dir}` : ''}`));
  anims = res?.animations || [];
  const sel = $('#mdlAnim', root);
  sel.innerHTML = '<option value="">None</option>' + anims.map(a => `<option value="${key(a)}">${key(a)}</option>`).join('');
  sel.value = anim ? key(anim) : '';
  if (anim && sel.value !== key(anim)) anim = null;
  $('#mdlAnimCount', root).textContent = `${anims.length}`;
  $('#mdlAnimHint', root).textContent = anims.length
    ? (limited ? `The animations in directory ${current.dir}.` : 'Every animation in the ROM.')
    : (limited ? `No animations in directory ${current.dir}; turn Limit Animations off to try others.` : 'No animations in this ROM.');
}

/** Gets the model from the server, made with the view's options. replaceCamera: place the camera again. */
async function loadModel(replaceCamera) {
  if (!current) return;
  const seq = ++loadSeq;
  const q = `textures=${view.textures ? 1 : 0}&wireframe=${view.wireframe ? 1 : 0}&normals=${view.normals ? 1 : 0}`
    + `&camera=${view.camera ? 1 : 0}&bg=${view.bg.toString(16).padStart(6, '0')}`;
  const json = await act(() => api(`/api/models/${current.dir}/${current.file}?${q}`));
  if (seq !== loadSeq) return;
  sceneJson = json || null;
  animJson = null;
  if (!sceneJson) {
    clearModel();
    showEmpty('Model Unavailable', `Model ${key(current)} couldn't be converted.`);
    return;
  }
  if (anim) await loadAnimation(true);
  rebuild(replaceCamera || !modelObj);
}

async function loadAnimation(noRebuild) {
  animJson = null;
  if (anim && current) {
    animJson = await act(() => api(`/api/models/${current.dir}/${current.file}/animation/${anim.dir}/${anim.file}`)) || null;
  }
  if (!noRebuild) applyAnimation();
}

function ensureRenderer() {
  if (renderer) return;
  const viewer = $('#mdlViewer', root);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  viewer.prepend(renderer.domElement);
  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000);
  controls = new OrbitControls(camera, renderer.domElement);
  resizeObs = new ResizeObserver(() => resize());
  resizeObs.observe(viewer);
  resize();
}

function resize() {
  if (!renderer) return;
  const viewer = $('#mdlViewer', root);
  const w = viewer.clientWidth || 1;
  const h = viewer.clientHeight || 1;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function disposeObj(obj) {
  obj?.traverse?.(o => {
    o.geometry?.dispose?.();
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) {
      for (const k of ['map', 'lightMap', 'bumpMap', 'normalMap', 'specularMap', 'envMap']) m[k]?.dispose?.();
      m.dispose?.();
    }
  });
}

function clearModel() {
  if (mixer) mixer.stopAllAction();
  mixer = null;
  action = null;
  if (modelObj && scene) scene.remove(modelObj);
  (model3d?.disposeObject || disposeObj)(modelObj);
  modelObj = null;
  $('#mdlLegend', root).hidden = true;
  $('#mdlPause', root).disabled = true;
}

/** Builds the three.js scene from sceneJson (and the animation). */
function rebuild(replaceCamera) {
  if (!sceneJson || !model3d || !THREE) return;
  ensureRenderer();
  clearModel();
  if (!scene) scene = new THREE.Scene();
  scene.background = new THREE.Color(view.bg);
  try {
    modelObj = model3d.buildScene(sceneJson);
  } catch (e) {
    console.error(e);
    showEmpty('Model Unavailable', `Model ${key(current)} couldn't be drawn: ${e.message}`);
    return;
  }
  scene.add(modelObj);
  $('#mdlEmpty', root).hidden = true;
  if (replaceCamera) placeCamera();
  applyAnimation();
  renderLegend();
  start();
}

/** The camera the original made (the FORM's own with Camera on), looking at the model. */
function placeCamera() {
  if (!camera || !sceneJson) return;
  const viewer = $('#mdlViewer', root);
  const made = model3d.buildCamera(sceneJson, viewer.clientWidth || 1, viewer.clientHeight || 1);
  camera.fov = made.fov;
  camera.near = made.near;
  camera.far = made.far;
  camera.position.copy(made.position);
  camera.quaternion.copy(made.quaternion);
  camera.updateProjectionMatrix();
  const look = sceneJson.camera?.look_at;
  controls.target.set(look?.[0] || 0, look?.[1] || 0, look?.[2] || 0);
  controls.update();
}

function applyAnimation() {
  if (mixer) mixer.stopAllAction();
  mixer = null;
  action = null;
  paused = false;
  $('#mdlPause', root).textContent = 'Pause';
  $('#mdlPause', root).disabled = true;
  if (!animJson || !modelObj || !model3d?.buildAnimation) {
    renderLegend();
    return;
  }
  try {
    const clip = model3d.buildAnimation(animJson, modelObj);
    if (clip) {
      mixer = new THREE.AnimationMixer(modelObj);
      action = mixer.clipAction(clip);
      action.play();
      clock = new THREE.Clock();
      $('#mdlPause', root).disabled = false;
    }
  } catch (e) {
    console.error(e);
    toast(`The animation couldn't be played: ${e.message}`, 'error');
  }
  renderLegend();
}

function renderLegend() {
  const el = $('#mdlLegend', root);
  if (!modelObj) {
    el.hidden = true;
    return;
  }
  let meshes = 0;
  let verts = 0;
  let tris = 0;
  let textures = new Set();
  modelObj.traverse(o => {
    if (!o.isMesh || !o.geometry) return;
    meshes++;
    const pos = o.geometry.attributes?.position;
    if (pos) verts += pos.count;
    tris += o.geometry.index ? o.geometry.index.count / 3 : (pos ? pos.count / 3 : 0);
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) if (m?.map) textures.add(m.map);
  });
  const clip = action?.getClip?.();
  el.hidden = false;
  el.innerHTML = `<span title="Objects with geometry"><b>${meshes}</b>&nbsp;meshes</span>
    <span title="Vertices"><b>${verts.toLocaleString()}</b>&nbsp;vertices</span>
    <span title="Triangles"><b>${Math.round(tris).toLocaleString()}</b>&nbsp;triangles</span>
    <span title="Textures"><b>${textures.size}</b>&nbsp;textures</span>
    ${clip ? `<span title="The animation playing">Anim ${key(anim)} · ${clip.duration.toFixed(2)} s</span>` : ''}`;
}

function start() {
  if (running || !renderer || app.page !== 'models') return;
  running = true;
  clock = clock || new THREE.Clock();
  tick();
}

function stop() {
  running = false;
  clearTimeout(timer);
  cancelAnimationFrame(frameReq);
}

function tick() {
  if (!running) return;
  controls?.update();
  const delta = clock ? clock.getDelta() : 0;
  if (mixer && !paused) mixer.update(delta);
  if (scene && camera) renderer.render(scene, camera);
  if (app.setting('models.limitfps')) {
    timer = setTimeout(() => { frameReq = requestAnimationFrame(tick); }, 1000 / 30);
  } else {
    frameReq = requestAnimationFrame(tick);
  }
}

async function exportModel(format) {
  if (!current) {
    toast('Pick a model first.', 'warn');
    return;
  }
  await act(async () => {
    const name = await download(`/api/models/${current.dir}/${current.file}/export?format=${format}`, undefined, `model-${current.dir}-${current.file}.${format}`);
    toast(`Exported ${name}.`, 'success', 3000);
  });
}
