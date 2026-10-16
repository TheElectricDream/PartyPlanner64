// Strings: read and edit the ROM's text (views/strings.tsx), drawn with the game's formatting.
import { $, $$, api, act, esc, loadCss, toast, dialog } from '../api.js';
import { COLORS, IMAGES, toHtml, toEditable, fromEditable, toPlain, imageUrl } from '../lib/mptext.js';

let root = null;
let app = null;
let info = null;          // GET /api/strings
let strings = [];         // the directory shown: [{index, text}]
let locale = 'en';
let dir = 0;
let filter = '';
let light = true;         // the preview background (no effect on the game)
let searchTimer = 0;

const hex = n => '0x' + n.toString(16).toUpperCase();

export function init(container, theApp) {
  loadCss('strings');
  root = container;
  app = theApp;
  root.innerHTML = `<div class="layout strings-page">
      <aside class="sidebar">
        <section class="card">
          <div class="card-head"><h2>Strings</h2><span class="pill" id="strGame"></span></div>
          <div id="strLocaleField" class="field" hidden>
            <span class="field-label tip" title="Mario Party 3 keeps its text in several languages">Language</span>
            <div class="segmented" id="strLocales" role="group" aria-label="Language"></div>
          </div>
          <label class="field">
            <span class="field-label tip" title="Show only the strings containing this text (in the directory shown)">Filter</span>
            <input id="strFilter" class="input" placeholder="Text to find…" spellcheck="false" title="Show only strings containing this text">
          </label>
          <p class="hint" id="strCount"></p>
        </section>
        <section class="card" id="strDirsCard" hidden>
          <div class="card-head"><h2>Directories</h2><span class="muted small" id="strDirCount"></span></div>
          <ul class="list-box str-dirs" id="strDirs"></ul>
        </section>
        <section class="card">
          <div class="card-head"><h2>Search Everything</h2></div>
          <div class="input-row">
            <input id="strSearch" class="input" placeholder="e.g. Koopa" spellcheck="false" title="Find strings containing this text in every directory">
          </div>
          <ul class="list-box str-results" id="strResults"><li class="empty">Type to search every string.</li></ul>
        </section>
        <section class="card">
          <div class="card-head"><h2>Formatting</h2></div>
          <p class="hint str-legend-hint">How the game's text codes are shown:</p>
          <div class="str-legend">
            ${Object.entries(COLORS).map(([k, c]) => `<span class="str-swatch" title="&lt;${k}&gt; starts this colour"><i style="background:${c}"></i>${k[0]}${k.slice(1).toLowerCase()}</span>`).join('')}
            <span class="str-swatch" title="{0}…{5}: filled in by the game (a player's name, a number…)"><span class="mp-param">{0}</span>Value</span>
          </div>
        </section>
      </aside>
      <main class="main">
        <div class="str-bar">
          <span class="str-where" id="strWhere"></span>
          <div class="segmented" role="group" aria-label="Preview background" title="The background of the text (has no effect on the game)">
            <button type="button" data-bg="light" class="active" title="Light background, like the game's text boxes">Light</button>
            <button type="button" data-bg="dark" title="Dark background, to read white and yellow text">Dark</button>
          </div>
        </div>
        <div class="str-scroll"><div class="str-list light" id="strList"></div></div>
      </main>
    </div>`;
  $('#strFilter', root).addEventListener('input', e => {
    filter = e.target.value;
    renderList();
  });
  $('#strSearch', root).addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => searchAll(e.target.value), 300);
  });
  for (const b of $$('[data-bg]', root)) {
    b.addEventListener('click', () => {
      light = b.dataset.bg === 'light';
      for (const o of $$('[data-bg]', root)) o.classList.toggle('active', o === b);
      $('#strList', root).classList.toggle('light', light);
      $('#strResults', root).classList.toggle('light', light);
    });
  }
  $('#strList', root).addEventListener('click', e => {
    const row = e.target.closest('[data-index]');
    if (row) edit(+row.dataset.index);
  });
  app.on('rom', () => {
    info = null;
    if (app.page === 'strings') load();
  });
}

export function show() {
  if (!info) load();
}

async function load() {
  strings = [];
  renderList();
  if (!app.state?.rom) {
    renderEmpty('No ROM Open', 'Open a ROM to see its text.');
    return;
  }
  await act(async () => {
    info = await api(`/api/strings?locale=${encodeURIComponent(locale)}`);
    locale = info.locale || 'en';
    if (dir >= info.directories.length) dir = 0;
    renderSide();
    await loadDir();
  }) ?? renderEmpty('Strings Unavailable', 'The ROM\'s strings couldn\'t be read.');
}

async function loadDir() {
  const res = await api(`/api/strings/list?locale=${encodeURIComponent(locale)}&dir=${dir}`);
  strings = res.strings;
  renderSide();
  renderList();
}

function renderSide() {
  const rom = app.state?.rom;
  $('#strGame', root).textContent = rom ? (rom.shortName || rom.gameName) : 'No ROM';
  if (!info) return;
  $('#strLocaleField', root).hidden = !info.multi;
  $('#strDirsCard', root).hidden = !info.multi;
  const locs = $('#strLocales', root);
  locs.innerHTML = info.locales.map(l => `<button type="button" data-locale="${esc(l)}" class="${l === locale ? 'active' : ''}"
      title="Show the ${esc(l.toUpperCase())} strings">${esc(l.toUpperCase())}</button>`).join('');
  for (const b of $$('[data-locale]', locs)) {
    b.addEventListener('click', () => {
      locale = b.dataset.locale;
      dir = 0;
      act(() => load());
    });
  }
  const dirs = $('#strDirs', root);
  $('#strDirCount', root).textContent = `${info.directories.length}`;
  dirs.innerHTML = info.directories.map(d => `<li data-dir="${d.index}" class="${d.index === dir ? 'active' : ''}"
      title="Directory ${d.index} (${hex(d.index)}): ${d.count} strings"><span class="mono">${d.index}</span>
      <span class="muted small">${d.count} strings</span></li>`).join('');
  for (const li of $$('[data-dir]', dirs)) {
    li.addEventListener('click', () => {
      dir = +li.dataset.dir;
      act(() => loadDir());
    });
  }
  const total = info.directories.reduce((n, d) => n + d.count, 0);
  $('#strCount', root).textContent = info.multi
    ? `${total.toLocaleString()} strings in ${info.directories.length} directories (${locale.toUpperCase()}).`
    : `${total.toLocaleString()} strings.`;
}

function renderEmpty(title, text) {
  $('#strList', root).innerHTML = `<div class="empty-state str-empty"><b>${esc(title)}</b><span>${esc(text)}</span></div>`;
  $('#strWhere', root).textContent = '';
}

function renderList() {
  const list = $('#strList', root);
  if (!strings.length) {
    if (info) renderEmpty('No Strings', 'This directory is empty.');
    return;
  }
  const f = filter.trim().toLowerCase();
  const shown = f ? strings.filter(s => toPlain(s.text).toLowerCase().includes(f) || s.text.toLowerCase().includes(f)) : strings;
  $('#strWhere', root).innerHTML = (info?.multi ? `<b>${esc(locale.toUpperCase())}</b> · Directory <b>${dir}</b> · ` : '')
    + `${shown.length === strings.length ? strings.length : `${shown.length} of ${strings.length}`} strings · click one to edit it`;
  if (!shown.length) {
    list.innerHTML = `<div class="empty-state str-empty"><b>No Matches</b><span>No string here contains “${esc(filter)}”.</span></div>`;
    return;
  }
  list.innerHTML = shown.map(s => `<div class="str-row" data-index="${s.index}" title="Edit string ${s.index} (${hex(s.index)})">
      <span class="str-idx mono">${s.index}<span>${hex(s.index)}</span></span>
      <div class="str-text mp-text">${s.text ? toHtml(s.text) : '<span class="str-blank">(empty)</span>'}</div>
    </div>`).join('');
}

async function searchAll(q) {
  const out = $('#strResults', root);
  if (!q.trim()) {
    out.innerHTML = '<li class="empty">Type to search every string.</li>';
    return;
  }
  await act(async () => {
    const res = await api(`/api/strings/search?q=${encodeURIComponent(q)}&locale=${encodeURIComponent(locale)}`);
    if (!res.results.length) {
      out.innerHTML = `<li class="empty">Nothing contains “${esc(q)}”.</li>`;
      return;
    }
    out.innerHTML = res.results.map(r => `<li data-dir="${r.dir ?? 0}" data-index="${r.index}" title="${esc(toPlain(r.text))}">
        <span class="mono str-res-at">${r.dir === null || r.dir === undefined ? '' : r.dir + '/'}${r.index}</span>
        <span class="str-res-text">${esc(toPlain(r.text))}</span></li>`).join('')
      + (res.truncated ? '<li class="empty">More results not shown; refine the search.</li>' : '');
    for (const li of $$('li[data-index]', out)) {
      li.addEventListener('click', () => act(async () => {
        const d = +li.dataset.dir;
        if (info.multi && d !== dir) {
          dir = d;
          await loadDir();
        }
        edit(+li.dataset.index);
      }));
    }
  });
}

/** The editor for one string, in a dialog. */
async function edit(index) {
  const entry = strings.find(s => s.index === index);
  if (!entry) return;
  const original = toEditable(entry.text);
  const advanced = !!app.setting('ui.advanced');
  const body = document.createElement('div');
  body.className = 'str-editor';
  body.innerHTML = `
    <div class="str-toolbar" role="toolbar" aria-label="Formatting">
      <div class="str-tool-group" title="Font colour: starts at the cursor and lasts until the next colour">
        ${Object.entries(COLORS).map(([k, c]) => `<button type="button" class="str-tool" data-insert="<${k}>"
          title="Insert &lt;${k}&gt;: the text after it is ${k.toLowerCase()}"><i style="background:${c}"></i></button>`).join('')}
      </div>
      <div class="str-tool-group">
        ${IMAGES.filter(i => advanced || !i.advanced).map(i => `<button type="button" class="str-tool" data-insert="[${i.token}]"
          title="Insert the ${esc(i.desc)} ([${i.token}])">${imageUrl(i) ? `<img src="${imageUrl(i)}" alt="">` : i.glyph}</button>`).join('')}
      </div>
    </div>
    <textarea class="input mono str-input" rows="6" spellcheck="false"
      title="The text. <COLOR> tags change the colour; [A], [COIN]… are images; {0} is filled in by the game"></textarea>
    <div class="field-label str-prev-label">Preview</div>
    <div class="str-preview mp-text ${light ? 'light' : ''}"></div>
    <p class="hint">Some of the game's characters share a look (two kinds of quotes, two tab codes), so saving
      can change bytes you didn't edit. Edits are written to the ROM when you save it.</p>
    <details class="advanced"><summary>Raw Bytes</summary><pre class="str-raw mono">Loading…</pre></details>`;
  const ta = $('textarea', body);
  ta.value = original;
  const preview = () => {
    $('.str-preview', body).innerHTML = toHtml(fromEditable(ta.value)) || '<span class="str-blank">(empty)</span>';
  };
  ta.addEventListener('input', preview);
  for (const b of $$('[data-insert]', body)) {
    b.addEventListener('click', () => {
      const ins = b.dataset.insert;
      ta.setRangeText(ins, ta.selectionStart, ta.selectionEnd, 'end');
      ta.focus();
      preview();
    });
  }
  preview();
  api(`/api/strings/${index}?locale=${encodeURIComponent(locale)}&dir=${dir}`)
    .then(r => { $('.str-raw', body).textContent = r.raw || '(none)'; })
    .catch(e => { $('.str-raw', body).textContent = e.message; });
  const where = info?.multi ? `${locale.toUpperCase()} ${dir}/${index}` : `${index}`;
  const r = await dialog({
    title: `String ${where} (${hex(index)})`, body, wide: true,
    buttons: [{ label: 'Cancel', value: false }, { label: 'Save', value: true, kind: 'primary' }],
    onOpen: () => ta.focus(),
  });
  if (r !== true || ta.value === original) return;
  await act(async () => {
    const res = await api('/api/strings/write', { locale, dir, index, text: fromEditable(ta.value) });
    entry.text = res.text;
    renderList();
    toast(`Saved string ${where}. Save the ROM to keep it.`, 'success');
  });
}
