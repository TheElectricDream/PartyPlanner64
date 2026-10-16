// Patches: GameShark cheats written into the ROM when it is saved (views/gameshark.tsx).
import { $, $$, api, act, esc, loadCss, toast, confirmDialog } from '../api.js';

const OPCODE_INFO = {
  WRITE8: 'Writes the 8-bit value to the address, every frame',
  WRITE16: 'Writes the 16-bit value to the address, every frame',
  IF8: 'Runs the next code only if the byte at the address equals the value',
  IF16: 'Runs the next code only if the halfword at the address equals the value',
  IFNOT8: 'Runs the next code only if the byte at the address differs from the value',
  IFNOT16: 'Runs the next code only if the halfword at the address differs from the value',
};

let root = null;
let app = null;
let data = null;
let parseTimer = 0;

const hex = (n, w = 8) => (n >>> 0).toString(16).toUpperCase().padStart(w, '0');

export function init(container, theApp) {
  loadCss('patches');
  root = container;
  app = theApp;
  root.innerHTML = `<div class="scroll-page patches-page">
      <div class="page-head">
        <div>
          <h2>Patches</h2>
          <p class="hint">GameShark cheats embedded in the ROM: they're written with it when you save the ROM, and run
            on every frame of the game, in emulators and on real hardware. They're kept until the ROM is closed.</p>
        </div>
        <span class="pill" id="gsGame"></span>
      </div>
      <div id="gsNotice"></div>
      <div class="grid patches-grid">
        <section class="card">
          <div class="card-head"><h2>Add Cheats</h2>
            <span class="pill" id="gsParsePill" title="Whether the codes below can be read">Empty</span></div>
          <label class="field-label tip" for="gsInput" title="Each code is an address and a value in hexadecimal, e.g. 8105E418 2400. Spaces and line breaks don't matter.">GameShark Codes</label>
          <textarea id="gsInput" class="input mono gs-input" rows="8" spellcheck="false"
            placeholder="8105E418 2400" title="Paste GameShark codes: pairs of address and value, in hexadecimal"></textarea>
          <div id="gsPreview" class="gs-preview"></div>
          <div class="gs-actions">
            <button type="button" class="btn btn-ghost btn-sm" id="gsExample" title="Fill in an example: show the memory meter in Mario Party 1">Example</button>
            <button type="button" class="btn btn-primary" id="gsApply" title="Compile the codes and add them to the ROM's cheats">Apply</button>
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>Applied Cheats</h2>
            <button type="button" class="btn btn-sm" id="gsClear" title="Remove every cheat added since the ROM was opened">Clear All</button></div>
          <div id="gsList"></div>
        </section>
      </div>
    </div>`;
  const input = $('#gsInput', root);
  input.addEventListener('input', () => {
    clearTimeout(parseTimer);
    parseTimer = setTimeout(preview, 250);
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) apply();
  });
  $('#gsApply', root).addEventListener('click', apply);
  $('#gsExample', root).addEventListener('click', () => {
    input.value = '8105E418 2400';
    preview();
  });
  $('#gsClear', root).addEventListener('click', clearAll);
  app.on('rom', () => load());
  app.on('state', () => renderHead());
}

export function show() {
  load();
}

async function load() {
  await act(async () => {
    data = await api('/api/patches');
    render();
  });
}

function renderHead() {
  const rom = app.state?.rom;
  const pill = $('#gsGame', root);
  pill.textContent = rom ? (rom.title || rom.gameName) : 'No ROM';
  pill.className = 'pill' + (rom && data?.supported ? ' ok' : '');
}

function render() {
  renderHead();
  const supported = !!data?.supported;
  const notice = $('#gsNotice', root);
  notice.innerHTML = !data?.romOpen
    ? '<div class="notice info">Open a ROM to add cheats to it.</div>'
    : !supported
      ? '<div class="notice warn">Embeddable GameShark cheats are not supported with this ROM: only Mario Party 1, 2 and 3 (U) have the hook they need.</div>'
      : '';
  for (const el of ['#gsInput', '#gsApply', '#gsExample']) $(el, root).disabled = !supported;
  const cheats = data?.cheats || [];
  $('#gsClear', root).disabled = !supported || !cheats.length;
  const list = $('#gsList', root);
  if (!cheats.length) {
    list.innerHTML = `<div class="empty-state"><b>No Cheats Yet</b>
      <span>Paste codes on the left and Apply them; they're written when you save the ROM.</span></div>`;
    return;
  }
  list.innerHTML = cheats.map(c => `<div class="gs-cheat">
      <div class="gs-cheat-head">
        <b>Cheat ${c.index + 1}</b>
        <span class="muted small">${c.codes.length || '?'} code${c.codes.length === 1 ? '' : 's'} · ${c.size} bytes of MIPS</span>
        <button type="button" class="btn btn-ghost btn-sm" data-del="${c.index}" title="Remove this cheat from the ROM">Remove</button>
      </div>
      ${c.text ? `<pre class="gs-code mono">${esc(c.text)}</pre>` : '<p class="hint">Added elsewhere (its codes aren\'t known here).</p>'}
      ${codesTable(c.codes)}
    </div>`).join('');
  for (const btn of $$('[data-del]', list)) {
    btn.addEventListener('click', () => act(async () => {
      data = await api(`/api/patches/${btn.dataset.del}/delete`, {});
      render();
      toast('Removed the cheat.', 'success', 2500);
    }));
  }
}

function codesTable(codes) {
  if (!codes?.length) return '';
  return `<table class="table gs-table"><thead><tr>
      <th title="What the code does">Type</th><th class="num" title="The address in RAM">Address</th><th class="num">Value</th></tr></thead>
    <tbody>${codes.map(c => `<tr title="${esc(OPCODE_INFO[c.opcode] || c.opcode)}">
      <td><span class="gs-op">${esc(c.opcode)}</span></td><td class="num">${hex(c.addr)}</td>
      <td class="num">${hex(c.value, c.opcode.endsWith('8') ? 2 : 4)}</td></tr>`).join('')}</tbody></table>`;
}

async function preview() {
  const text = $('#gsInput', root).value;
  const pill = $('#gsParsePill', root);
  const out = $('#gsPreview', root);
  if (!text.trim()) {
    pill.textContent = 'Empty';
    pill.className = 'pill';
    out.innerHTML = '';
    return;
  }
  try {
    const res = await api('/api/patches/parse', { text });
    pill.textContent = `${res.codes.length} Code${res.codes.length === 1 ? '' : 's'}`;
    pill.className = 'pill ok';
    out.innerHTML = codesTable(res.codes);
  } catch (e) {
    pill.textContent = 'Not Valid';
    pill.className = 'pill err';
    out.innerHTML = `<p class="hint bad">${esc(e.message)}</p>`;
  }
}

async function apply() {
  const input = $('#gsInput', root);
  await act(async () => {
    data = await api('/api/patches', { text: input.value });
    input.value = '';
    preview();
    render();
    toast('Applied! The cheat is written when you save the ROM.', 'success');
  });
}

async function clearAll() {
  if (!await confirmDialog('Remove every cheat added to this ROM?', { title: 'Clear Cheats', yes: 'Clear All', danger: true })) return;
  await act(async () => {
    data = await api('/api/patches/clear', {});
    render();
  });
}
