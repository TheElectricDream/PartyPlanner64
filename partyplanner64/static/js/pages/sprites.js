// Sprites: browse the ROM's image packs (MainFS files), view their frames, save PNGs
// (views/sprites.tsx).
import { $, $$, api, act, esc, loadCss, toast, download } from '../api.js';

let root = null;
let app = null;
let sprites = null;       // [{dir, file, frames, width, height}]
let current = null;       // {dir, file}
let frames = [];
let zoom = 2;
let bg = 'checker';
let filter = '';
let loading = false;

const key = s => `${s.dir}/${s.file}`;
const hex = n => '0x' + n.toString(16).toUpperCase().padStart(4, '0');

export function init(container, theApp) {
  loadCss('sprites');
  root = container;
  app = theApp;
  root.innerHTML = `<div class="layout sprites-page">
      <aside class="sidebar">
        <section class="card spr-list-card">
          <div class="card-head"><h2>Sprites</h2><span class="pill" id="sprCount">…</span></div>
          <input id="sprFilter" class="input" placeholder="Filter, e.g. 9/ or 64x64" spellcheck="false"
            title="Show only the sprites whose directory/file or size contains this text">
          <ul class="list-box spr-list" id="sprList"><li class="empty">Loading…</li></ul>
          <p class="hint">Every MainFS file that holds an image pack. Use ↑ and ↓ to step through them.</p>
        </section>
        <section class="card">
          <div class="card-head"><h2>Selected</h2></div>
          <div id="sprInfo"><p class="hint">No sprite selected.</p></div>
          <div class="spr-actions">
            <button type="button" class="btn btn-sm" id="sprSheet" title="Save every frame side by side, as one PNG">Save Sheet</button>
            <button type="button" class="btn btn-sm" id="sprZip" title="Save every frame as its own PNG, in a .zip">Save All (.zip)</button>
          </div>
        </section>
      </aside>
      <main class="main">
        <div class="viewer spr-viewer bg-checker" id="sprViewer">
          <div class="viewer-toolbar">
            <div class="segmented" role="group" aria-label="Zoom" title="How large the frames are drawn">
              ${[1, 2, 4, 8].map(z => `<button type="button" data-zoom="${z}" class="${z === zoom ? 'active' : ''}" title="Draw frames at ${z}× size">${z}×</button>`).join('')}
            </div>
            <div class="segmented" role="group" aria-label="Background" title="The background behind the frames">
              <button type="button" data-bg="checker" class="active" title="A checkerboard, to see transparency">Checker</button>
              <button type="button" data-bg="black" title="Black background">Black</button>
              <button type="button" data-bg="white" title="White background">White</button>
            </div>
          </div>
          <div class="spr-frames" id="sprFrames"></div>
          <div class="viewer-empty" id="sprEmpty" hidden><b>No Sprite</b><span>Pick a sprite on the left.</span></div>
        </div>
      </main>
    </div>`;
  $('#sprFilter', root).addEventListener('input', e => {
    filter = e.target.value.trim().toLowerCase();
    renderList();
  });
  for (const b of $$('[data-zoom]', root)) {
    b.addEventListener('click', () => {
      zoom = +b.dataset.zoom;
      for (const o of $$('[data-zoom]', root)) o.classList.toggle('active', o === b);
      renderFrames();
    });
  }
  for (const b of $$('[data-bg]', root)) {
    b.addEventListener('click', () => {
      bg = b.dataset.bg;
      for (const o of $$('[data-bg]', root)) o.classList.toggle('active', o === b);
      $('#sprViewer', root).className = `viewer spr-viewer bg-${bg}`;
    });
  }
  $('#sprSheet', root).addEventListener('click', () => current && act(async () => {
    const name = await download(`/api/sprites/${current.dir}/${current.file}/sheet.png?download=1`, undefined, 'sprite.png');
    toast(`Saved ${name}.`, 'success', 3000);
  }));
  $('#sprZip', root).addEventListener('click', () => current && act(async () => {
    const name = await download(`/api/sprites/${current.dir}/${current.file}/zip`, undefined, 'sprite.zip');
    toast(`Saved ${name}.`, 'success', 3000);
  }));
  $('#sprFrames', root).addEventListener('click', e => {
    const btn = e.target.closest('[data-save]');
    if (btn) {
      act(async () => {
        const name = await download(`/api/sprites/${current.dir}/${current.file}/${btn.dataset.save}.png?download=1`, undefined, 'frame.png');
        toast(`Saved ${name}.`, 'success', 3000);
      });
    }
  });
  $('#sprList', root).addEventListener('keydown', e => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const items = $$('li[data-key]', $('#sprList', root));
    const i = items.findIndex(li => li.classList.contains('active'));
    const next = items[Math.max(0, Math.min(items.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))];
    if (next) {
      next.click();
      next.scrollIntoView({ block: 'nearest' });
    }
  });
  app.on('rom', () => {
    sprites = null;
    current = null;
    frames = [];
    if (app.page === 'sprites') load();
  });
}

export function show() {
  if (!sprites && !loading) load();
}

async function load() {
  renderSelected();
  renderFrames();
  if (!app.state?.rom) {
    $('#sprList', root).innerHTML = '<li class="empty">Open a ROM to see its sprites.</li>';
    $('#sprCount', root).textContent = 'No ROM';
    return;
  }
  loading = true;
  $('#sprList', root).innerHTML = '<li class="empty">Reading the ROM\'s files…</li>';
  $('#sprCount', root).textContent = '…';
  try {
    const res = await act(() => api('/api/sprites'));
    sprites = res?.sprites || null;
  } finally {
    loading = false;
  }
  if (!sprites) {
    $('#sprList', root).innerHTML = '<li class="empty">The sprites couldn\'t be read.</li>';
    $('#sprCount', root).textContent = 'Error';
    return;
  }
  renderList();
  if (sprites.length && !current) select(sprites[0]);
}

function renderList() {
  const list = $('#sprList', root);
  if (!sprites) return;
  $('#sprCount', root).textContent = `${sprites.length}`;
  const shown = sprites.filter(s => !filter || `${key(s)} ${s.width}x${s.height}`.includes(filter));
  if (!sprites.length) {
    list.innerHTML = '<li class="empty">This ROM has no image packs.</li>';
    return;
  }
  if (!shown.length) {
    list.innerHTML = `<li class="empty">No sprite matches “${esc(filter)}”.</li>`;
    return;
  }
  list.tabIndex = 0;
  list.innerHTML = shown.map(s => `<li data-key="${key(s)}" class="${current && key(current) === key(s) ? 'active' : ''}"
      title="MainFS ${key(s)} (${hex(s.dir)}/${hex(s.file)}): ${s.frames} frame${s.frames === 1 ? '' : 's'} of ${s.width}×${s.height}">
      <span class="mono spr-key">${key(s)}</span>
      <span class="muted small spr-meta">${s.frames > 1 ? `${s.frames} × ` : ''}${s.width}×${s.height}</span></li>`).join('');
  for (const li of $$('li[data-key]', list)) {
    li.addEventListener('click', () => select(sprites.find(s => key(s) === li.dataset.key)));
  }
}

async function select(sprite) {
  current = sprite;
  for (const li of $$('li[data-key]', $('#sprList', root))) li.classList.toggle('active', li.dataset.key === key(sprite));
  frames = [];
  renderSelected();
  await act(async () => {
    const res = await api(`/api/sprites/${sprite.dir}/${sprite.file}`);
    if (current !== sprite) return;
    frames = res.frames;
    renderFrames();
  });
}

function renderSelected() {
  const info = $('#sprInfo', root);
  $('#sprSheet', root).disabled = !current;
  $('#sprZip', root).disabled = !current;
  if (!current) {
    info.innerHTML = '<p class="hint">No sprite selected.</p>';
    return;
  }
  info.innerHTML = `<table class="table spr-table"><tbody>
      <tr><td class="muted">MainFS File</td><td class="num">${key(current)}</td></tr>
      <tr><td class="muted">Hexadecimal</td><td class="num">${hex(current.dir)}/${hex(current.file)}</td></tr>
      <tr><td class="muted">Frames</td><td class="num">${current.frames}</td></tr>
      <tr><td class="muted">Size</td><td class="num">${current.width} × ${current.height}</td></tr>
    </tbody></table>`;
}

function renderFrames() {
  const box = $('#sprFrames', root);
  $('#sprEmpty', root).hidden = !!current;
  if (!current) {
    box.innerHTML = '';
    return;
  }
  box.innerHTML = frames.map(f => `<figure class="spr-frame">
      <div class="spr-img"><img src="${f.url}" width="${f.width * zoom}" height="${f.height * zoom}" alt="Frame ${f.index}"></div>
      <figcaption><span>Frame ${f.index}</span><span class="muted">${f.width}×${f.height}</span>
        <button type="button" class="btn btn-ghost btn-sm" data-save="${f.index}" title="Save this frame as a PNG">Save PNG</button></figcaption>
    </figure>`).join('');
}
