// Debug: tools for looking inside the ROM (views/debug.tsx, utils/dump.ts). What the original
// printed to the browser's console goes to this page's output.
import { $, $$, api, act, busy, esc, loadCss, toast, download, pickFile } from '../api.js';

const FIELDS = [
  ['ram_start', 'RAM Start', 'Where the overlay is loaded in RAM'],
  ['code_start', 'Code Start', 'The start of its code (RAM address)'],
  ['code_end', 'Code End', 'The end of its code'],
  ['rodata_start', 'Rodata Start', 'The start of its read-only data'],
  ['rodata_end', 'Rodata End', 'The end of its read-only data'],
  ['bss_start', 'BSS Start', 'The start of its zeroed data'],
  ['bss_end', 'BSS End', 'The end of its zeroed data'],
];

let root = null;
let app = null;
let blocks = 0;

export function init(container, theApp) {
  loadCss('debug');
  root = container;
  app = theApp;
  const field = (id, label, title, placeholder = '', cls = '') => `<label class="field dbg-field ${cls}">
      <span class="field-label tip" title="${esc(title)}">${label}</span>
      <input id="${id}" class="input mono" placeholder="${esc(placeholder)}" spellcheck="false" title="${esc(title)}"></label>`;
  root.innerHTML = `<div class="layout debug-page">
      <aside class="sidebar">
        <div id="dbgNoRom" class="notice info" hidden>Load a ROM to use the debug tools.</div>
        <section class="card">
          <div class="card-head"><h2>File Dump</h2></div>
          <p class="hint dbg-first">Every MainFS file in a .zip. Edit them and import the .zip: your changes are
            applied to the ROM blindly.</p>
          <div class="dbg-btns">
            <button type="button" class="btn btn-sm" data-rom id="dbgExport" title="Download every MainFS file in a .zip (FORM and MTNX files are named so)">Export File Dump</button>
            <button type="button" class="btn btn-sm" data-rom id="dbgImport" title="Write the files of a .zip made by Export File Dump back into the ROM">Import File Dump…</button>
            <button type="button" class="btn btn-sm" data-rom id="dbgImages" title="Download the ROM's images as PNGs: model bitmaps, fonts and image packs">Dump Images</button>
          </div>
        </section>

        <section class="card">
          <div class="card-head"><h2>Scenes</h2><span class="muted small" id="dbgSceneCount"></span></div>
          <div class="dbg-btns">
            <button type="button" class="btn btn-sm" data-rom data-scenes="table" title="Print the overlay table">Scene Table</button>
            <button type="button" class="btn btn-sm" data-rom data-scenes="n64split" title="Print the overlay table for n64split">n64split</button>
            <button type="button" class="btn btn-sm" data-rom data-scenes="n64splat" title="Print the overlay table for n64splat">n64splat</button>
          </div>
          <div class="section">
            <div class="input-row">
              ${field('dbgScene', 'Scene Number', 'An overlay (scene) number, in decimal', 'e.g. 70')}
            </div>
            <div class="dbg-scene-grid">
              ${FIELDS.map(([k, label, title]) => field(`dbgSc_${k}`, label, `${title}, in hexadecimal (used by Replace)`, '', 'dbg-small')).join('')}
            </div>
            <div class="dbg-btns">
              <button type="button" class="btn btn-sm" data-rom id="dbgSceneAsm" title="Print the overlay's code as assembly, then its rodata and bss">Print Assembly</button>
              <button type="button" class="btn btn-sm" data-rom id="dbgSceneDl" title="Download the overlay's bytes">Download</button>
              <button type="button" class="btn btn-sm" data-rom id="dbgSceneReplace" title="Replace the overlay with a file, using the addresses above">Replace…</button>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-head"><h2>Strings</h2></div>
          <div class="input-row">
            ${field('dbgStrDir', 'Directory', 'The strings directory, in hexadecimal (Mario Party 3)', 'hex', 'dbg-small')}
            ${field('dbgStrIdx', 'Index', 'The string number, in hexadecimal', 'hex', 'dbg-small')}
          </div>
          <div class="dbg-row">
            <label class="toggle" title="Print the string's bytes instead of its text"><input type="checkbox" id="dbgStrRaw"><span></span>Raw</label>
            <button type="button" class="btn btn-sm" data-rom id="dbgStrPrint" title="Print the string">Print String</button>
          </div>
          <div class="section">
            <div class="input-row">
              <input id="dbgFind" class="input" placeholder="Search text…" title="Find the strings containing this text">
              <button type="button" class="btn btn-sm" data-rom id="dbgFindBtn" title="Print every string containing the text (with their bytes if Raw is on)">Find</button>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-head"><h2>Offsets</h2></div>
          <div class="input-row dbg-end">
            ${field('dbgRomOff', 'ROM Offset', 'A ROM offset, in hexadecimal', 'e.g. 1000')}
            <button type="button" class="btn btn-sm" data-rom id="dbgRomToRam" title="Where this ROM offset is: an overlay's RAM address, a MainFS file, or plain RAM">ROM → RAM</button>
          </div>
          <pre class="dbg-result mono" id="dbgRomToRamOut"></pre>
          <div class="input-row dbg-end">
            ${field('dbgFsDir', 'Directory', 'A MainFS directory, in decimal', '', 'dbg-small')}
            ${field('dbgFsFile', 'File', 'A MainFS file, in decimal', '', 'dbg-small')}
            <button type="button" class="btn btn-sm" data-rom id="dbgFsToRom" title="Where this MainFS file's data starts in the ROM">MainFS → ROM</button>
          </div>
          <pre class="dbg-result mono" id="dbgFsToRomOut"></pre>
          <div class="section input-row dbg-end">
            ${field('dbgAsmStart', 'Start', 'The first ROM offset to disassemble, in hexadecimal', '', 'dbg-small')}
            ${field('dbgAsmEnd', 'End', 'The last ROM offset to disassemble, in hexadecimal', '', 'dbg-small')}
            <button type="button" class="btn btn-sm" data-rom id="dbgAsm" title="Print this part of the ROM as MIPS assembly">Disassemble</button>
          </div>
        </section>
      </aside>
      <main class="main">
        <div class="dbg-out-head">
          <div class="tabs"><button type="button" class="active" title="What the tools print">Output <span class="count" id="dbgCount">0</span></button></div>
          <div class="console-actions">
            <button type="button" class="btn btn-ghost btn-sm" id="dbgCopy" title="Copy the output">Copy</button>
            <button type="button" class="btn btn-ghost btn-sm" id="dbgClear" title="Clear the output">Clear</button>
          </div>
        </div>
        <pre class="log active dbg-log" id="dbgLog"></pre>
      </main>
    </div>`;
  wire();
  app.on('state', render);
  app.on('rom', () => { render(); $('#dbgSceneCount', root).textContent = ''; });
  render();
  clearOut();
}

export function show() {
  render();
}

function render() {
  const rom = !!app.state?.rom;
  $('#dbgNoRom', root).hidden = rom;
  for (const el of $$('[data-rom]', root)) el.disabled = !rom;
  $('#dbgStrDir', root).closest('.field').hidden = rom && app.state.rom.gameVersion !== 3;
}

function clearOut() {
  blocks = 0;
  $('#dbgCount', root).textContent = '0';
  $('#dbgLog', root).innerHTML = '<span class="muted">The tools on the left print here. Load a ROM, then pick one.</span>';
}

/** Adds a block of output: a heading and text. */
function out(title, text, kind = '') {
  const log = $('#dbgLog', root);
  if (!blocks) log.innerHTML = '';
  blocks++;
  $('#dbgCount', root).textContent = String(blocks);
  const div = document.createElement('div');
  div.className = 'dbg-block';
  div.innerHTML = `<span class="l-cmd">› ${esc(title)}</span>\n<span class="${kind}">${esc(text || '(nothing)')}</span>\n`;
  log.append(div);
  div.scrollIntoView({ block: 'start' });
}

const val = id => $(id, root).value.trim();

function wire() {
  $('#dbgClear', root).addEventListener('click', clearOut);
  $('#dbgCopy', root).addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($('#dbgLog', root).innerText);
      toast('Copied the output.', 'success', 2500);
    } catch {
      toast('Copying is blocked by the browser.', 'warn');
    }
  });
  $('#dbgExport', root).addEventListener('click', () => busy('Packing every MainFS file…', async () => {
    toast(`Saved ${await download('/api/debug/dump', undefined, 'files.zip')}.`, 'success');
  }));
  $('#dbgImages', root).addEventListener('click', () => busy('Converting the ROM\'s images…', async () => {
    toast(`Saved ${await download('/api/debug/images', undefined, 'images.zip')}.`, 'success');
  }));
  $('#dbgImport', root).addEventListener('click', async () => {
    const file = await pickFile('.zip');
    if (!file) return;
    await busy(`Importing ${file.name}…`, async () => {
      const res = await api('/api/debug/dump', file);
      out(`Import ${file.name}`, `Overwrote ${res.written} MainFS file${res.written === 1 ? '' : 's'}:\n${res.files.join(' ')}`, 'l-ok');
      toast(`Overwrote ${res.written} MainFS files. Save the ROM to keep them.`, 'success');
    });
  });
  for (const b of $$('[data-scenes]', root)) {
    b.addEventListener('click', () => act(async () => {
      const res = await api(`/api/debug/scenes?format=${b.dataset.scenes}`);
      $('#dbgSceneCount', root).textContent = `${res.count} scenes`;
      out(`${b.textContent} (${res.count} scenes)`, res.text);
    }));
  }
  let sceneTimer = 0;
  $('#dbgScene', root).addEventListener('input', () => {
    clearTimeout(sceneTimer);
    sceneTimer = setTimeout(loadScene, 250);
  });
  $('#dbgSceneAsm', root).addEventListener('click', () => withScene(i => busy(`Disassembling scene ${i}…`, async () => {
    const res = await api(`/api/debug/scenes/${i}/asm`);
    out(`Scene ${i} assembly`, res.text);
  })));
  $('#dbgSceneDl', root).addEventListener('click', () => withScene(i => act(async () => {
    toast(`Saved ${await download(`/api/debug/scenes/${i}/download`, undefined, `overlay-${i}.bin`)}.`, 'success', 3000);
  })));
  $('#dbgSceneReplace', root).addEventListener('click', () => withScene(async i => {
    const file = await pickFile('');
    if (!file) return;
    const q = FIELDS.map(([k]) => `${k}=${encodeURIComponent(val(`#dbgSc_${k}`))}`).join('&');
    await busy(`Replacing scene ${i}…`, async () => {
      const res = await api(`/api/debug/scenes/${i}/replace?${q}`, file);
      out(`Replace scene ${i}`, `Replaced with ${file.name} (${res.size} bytes).`, 'l-ok');
      toast(`Replaced scene ${i}. Save the ROM to keep it.`, 'success');
    });
  }));
  $('#dbgStrPrint', root).addEventListener('click', () => act(async () => {
    const raw = $('#dbgStrRaw', root).checked;
    const res = await api(`/api/debug/string?dir=${encodeURIComponent(val('#dbgStrDir'))}&index=${encodeURIComponent(val('#dbgStrIdx'))}&raw=${raw ? 1 : 0}`);
    out(`String ${res.where}${raw ? ' (raw)' : ''}`, res.text);
  }));
  const find = () => act(async () => {
    const raw = $('#dbgStrRaw', root).checked;
    const q = $('#dbgFind', root).value;
    const res = await busy('Searching the strings…', () => api(`/api/debug/find-string?q=${encodeURIComponent(q)}&raw=${raw ? 1 : 0}`));
    if (res) out(`Find "${q}" (${res.count} found)`, res.text);
  });
  $('#dbgFindBtn', root).addEventListener('click', find);
  $('#dbgFind', root).addEventListener('keydown', e => { if (e.key === 'Enter') find(); });
  $('#dbgRomToRam', root).addEventListener('click', () => act(async () => {
    const res = await api(`/api/debug/rom-to-ram?offset=${encodeURIComponent(val('#dbgRomOff'))}`);
    $('#dbgRomToRamOut', root).textContent = res.result;
  }));
  $('#dbgFsToRom', root).addEventListener('click', () => act(async () => {
    const res = await api(`/api/debug/mainfs-to-rom?dir=${encodeURIComponent(val('#dbgFsDir'))}&file=${encodeURIComponent(val('#dbgFsFile'))}`);
    $('#dbgFsToRomOut', root).textContent = res.result;
  }));
  $('#dbgAsm', root).addEventListener('click', () => act(async () => {
    const res = await api(`/api/debug/asm?start=${encodeURIComponent(val('#dbgAsmStart'))}&end=${encodeURIComponent(val('#dbgAsmEnd'))}`);
    out(`Disassemble ${val('#dbgAsmStart')}–${val('#dbgAsmEnd')}`, res.text);
  }));
  for (const [id, btn] of [['#dbgRomOff', '#dbgRomToRam'], ['#dbgFsFile', '#dbgFsToRom'], ['#dbgStrIdx', '#dbgStrPrint']]) {
    $(id, root).addEventListener('keydown', e => { if (e.key === 'Enter') $(btn, root).click(); });
  }
}

function withScene(fn) {
  const i = parseInt(val('#dbgScene'), 10);
  if (Number.isNaN(i)) {
    toast('Enter a scene number first.', 'warn');
    return undefined;
  }
  return fn(i);
}

async function loadScene() {
  const i = parseInt(val('#dbgScene'), 10);
  const clear = () => { for (const [k] of FIELDS) $(`#dbgSc_${k}`, root).value = ''; };
  if (Number.isNaN(i) || !app.state?.rom) {
    clear();
    return;
  }
  try {
    const res = await api(`/api/debug/scenes/${i}`);
    for (const [k] of FIELDS) $(`#dbgSc_${k}`, root).value = res.info[k];
  } catch {
    clear();
  }
}
