// Events: the event library (built-in and custom events), the custom events kept in the current
// board's file, and the editor for custom events in MIPS assembly or C
// (views/eventsview.tsx, createevent_asm.tsx, createevent_c.tsx, createevent_shared.tsx).
// The server keeps the library (/api/events, docs/API.md).
import { $, $$, api, act, busy, esc, loadCss, toast, download, pickFile, confirmDialog, saveBlob } from '../api.js';
import { createCodeEditor } from '../lib/codeeditor.js';
import { GAMES, GAME_BY_ID, PARAM_TYPES, VALID_PARAM_NAME, DEFAULT_CODE, readHeader, writeHeader } from './events/header.js';

const LANG = { 0: 'MIPS', 1: 'C' };
const EXT = { 0: '.s', 1: '.c' };
const EXEC = { 1: 'Direct', 2: 'Process' };
const ACTIVATION = { 1: 'Walk Over', 3: 'Land On', 7: 'Special', 8: 'Begin or Walk Over',
  '-2': 'Before Turn', '-3': 'After Turn', '-4': 'Before Player Turn', '-5': 'Before Dice Roll' };

let root = null;
let app = null;
let data = null;              // GET /api/events
let mode = 'list';
let newLanguage = 1;          // the original defaulted to C
let filter = '';
let gameFilter = '';
let showBuiltIn = false;

// The editor
let editor = null;            // createCodeEditor()
let asmView = null;           // the compiled assembly (C events), read-only
let ed = null;                // {id, board, language, saved, form, tab}
let syncing = false;

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const gameChips = ids => `<span class="chips ev-games">${(ids || []).map(id => {
  const g = GAME_BY_ID[id];
  return `<span class="chip ev-game g${g ? g[0][2] : ''}" title="${esc(g ? g[0] : id)}">${esc(g ? g[2] : id)}</span>`;
}).join('') || '<span class="muted small">No games</span>'}</span>`;

export function init(container, theApp) {
  loadCss('events');
  root = container;
  app = theApp;
  root.innerHTML = `<div class="ev-mode" id="evList"></div><div class="ev-mode" id="evEdit" hidden></div>`;
  buildList();
  buildEditor();
  app.on('events', () => { if (mode === 'list') load(); });
  app.on('boards', () => { if (mode === 'list') load(); });
  app.on('board', () => { if (mode === 'list') load(); });
}

export function show() {
  if (mode === 'list') load();
}

// The library

function buildList() {
  $('#evList', root).innerHTML = `<div class="layout ev-layout">
      <aside class="sidebar">
        <section class="card">
          <div class="card-head"><h2>Create Event</h2></div>
          <span class="field-label">Code Language</span>
          <div class="segmented ev-lang" role="group" aria-label="Code language">
            <button type="button" data-lang="1" class="active" title="C programming language (compiled with Smaller C)">C</button>
            <button type="button" data-lang="0" title="MIPS assembly language">MIPS</button>
          </div>
          <div class="ev-create-row">
            <button type="button" class="btn btn-primary" id="evCreate" title="Write your own event code">Create Event</button>
            <button type="button" class="btn" id="evImport" title="Load event code from a file (.s or .c) into the library">Import…</button>
          </div>
          <p class="hint">For code examples, see the
            <a href="https://github.com/PartyPlanner64/events" target="_blank" rel="noopener noreferrer" title="Example events on GitHub">events repository</a>.</p>
        </section>
        <section class="card">
          <div class="card-head"><h2>Find</h2></div>
          <input id="evFilter" class="input" placeholder="Event name…" spellcheck="false" title="Show only the events whose name contains this text">
          <div class="field">
            <span class="field-label">Game</span>
            <div class="segmented" role="group" aria-label="Game" id="evGameFilter">
              <button type="button" data-game="" class="active" title="Events for any game">All</button>
              <button type="button" data-game="1" title="Events that support Mario Party 1">MP1</button>
              <button type="button" data-game="2" title="Events that support Mario Party 2">MP2</button>
              <button type="button" data-game="3" title="Events that support Mario Party 3">MP3</button>
            </div>
          </div>
          <label class="toggle ev-opt" title="List the events of the original boards too"><input type="checkbox" id="evBuiltIn"><span></span>Show Built-In Events</label>
        </section>
        <section class="card">
          <div class="card-head"><h2>About Events</h2></div>
          <p class="hint ev-first">Spaces run events. Custom events are kept in your <b>library</b>, on this computer;
            a board's <b>file</b> also carries the custom events it uses, so that it opens anywhere. Copy events between
            the two with the arrows.</p>
        </section>
      </aside>
      <main class="main"><div class="ev-scroll" id="evScroll"></div></main>
    </div>`;
  const list = $('#evList', root);
  for (const b of $$('[data-lang]', list)) {
    b.addEventListener('click', () => {
      newLanguage = +b.dataset.lang;
      for (const o of $$('[data-lang]', list)) o.classList.toggle('active', o === b);
    });
  }
  $('#evCreate', list).addEventListener('click', () => openEditor({ language: newLanguage }));
  $('#evImport', list).addEventListener('click', importEvent);
  $('#evFilter', list).addEventListener('input', e => { filter = e.target.value.trim().toLowerCase(); renderList(); });
  for (const b of $$('[data-game]', list)) {
    b.addEventListener('click', () => {
      gameFilter = b.dataset.game;
      for (const o of $$('[data-game]', list)) o.classList.toggle('active', o === b);
      renderList();
    });
  }
  $('#evBuiltIn', list).addEventListener('change', e => { showBuiltIn = e.target.checked; renderList(); });
  $('#evScroll', list).addEventListener('click', onListClick);
}

async function load() {
  const res = await act(() => api('/api/events'));
  if (res) data = res;
  renderList();
}

function boardName() {
  const b = app.state?.boards;
  if (!b?.current) return 'the Board';
  const list = b.current.rom ? b.romList : b.list;
  return list?.[b.current.index]?.name || 'the Board';
}

function matches(ev) {
  if (filter && !`${ev.name} ${ev.id}`.toLowerCase().includes(filter)) return false;
  if (gameFilter && !(ev.supportedGames || []).some(id => GAME_BY_ID[id]?.[0][2] === gameFilter)) return false;
  return true;
}

function renderList() {
  const box = $('#evScroll', root);
  if (!data) {
    box.innerHTML = '<div class="empty-state ev-empty"><b>Loading the Events…</b></div>';
    return;
  }
  const byName = (a, b) => a.name.localeCompare(b.name);
  const boardEvents = (data.boardEvents || []).filter(matches).sort(byName);
  const custom = data.events.filter(e => e.custom).filter(matches).sort(byName);
  const builtIn = data.events.filter(e => !e.custom && !e.fakeEvent).filter(matches).sort(byName);
  const boardIds = new Map((data.boardEvents || []).map(e => [e.id, e]));
  const filtered = filter || gameFilter;

  const boardCard = `<section class="card ev-card">
      <div class="card-head"><h2>Events for ${esc(boardName())}</h2>
        <span class="muted small">${(data.boardEvents || []).length} in the board's file</span></div>
      ${boardEvents.length ? `<table class="table ev-table"><thead><tr><th>Name</th><th>Games</th><th class="num">Parameters</th><th>Library</th><th></th></tr></thead>
        <tbody>${boardEvents.map(ev => boardRow(ev)).join('')}</tbody></table>`
        : `<div class="empty-state"><b>${filtered ? 'No Matches' : 'No Board Events'}</b>
            <span>${filtered ? 'No event of the board matches the filter.' : 'No custom events are associated with this board. Copy one from the library below.'}</span></div>`}
    </section>`;
  const libCard = `<section class="card ev-card">
      <div class="card-head"><h2>Event Library</h2>
        <span class="muted small">${plural(data.events.filter(e => e.custom).length, 'custom event')}</span></div>
      ${custom.length ? `<table class="table ev-table"><thead><tr><th>Name</th><th>Games</th><th class="num">Parameters</th><th>Board</th><th></th></tr></thead>
        <tbody>${custom.map(ev => libRow(ev, boardIds.get(ev.id))).join('')}</tbody></table>`
        : `<div class="empty-state"><b>${filtered ? 'No Matches' : 'No Custom Events'}</b>
            <span>${filtered ? 'No custom event matches the filter.' : 'No custom events present: load or create your own!'}</span></div>`}
    </section>`;
  const builtInCard = showBuiltIn ? `<section class="card ev-card">
      <div class="card-head"><h2>Built-In Events</h2><span class="muted small">${builtIn.length} from the original boards</span></div>
      ${builtIn.length ? `<table class="table ev-table"><thead><tr><th>Name</th><th>Games</th><th>Execution</th><th>Parameters</th></tr></thead>
        <tbody>${builtIn.map(ev => `<tr title="${esc(ev.id)}">
          <td><span class="ev-name">${esc(ev.name)}</span></td><td>${gameChips(ev.supportedGames)}</td>
          <td class="muted">${esc(EXEC[ev.executionType] || '')}</td>
          <td>${ev.parameters.length ? ev.parameters.map(p => `<span class="ev-param" title="${esc(p.type)}">${esc(p.name)}</span>`).join(' ') : '<span class="muted">None</span>'}</td>
        </tr>`).join('')}</tbody></table>` : '<div class="empty-state"><b>No Matches</b></div>'}
    </section>` : '';
  box.innerHTML = boardCard + libCard + builtInCard;
}

function nameCell(ev) {
  return `<td><button type="button" class="ev-link" data-act="edit" title="Edit ${esc(ev.name)}">
      <span class="ev-name">${esc(ev.name)}</span><span class="ev-ext">${EXT[ev.language] || ''}</span></button>
      ${ev.error ? `<div class="hint bad">${esc(ev.error)}</div>` : ''}</td>`;
}

function boardRow(ev) {
  const status = !ev.inLibrary ? '<span class="pill" title="Only the board\'s file has this event">Not in Library</span>'
    : ev.differs ? '<span class="pill warn" title="The library has different code for this event">Differs</span>'
      : '<span class="pill ok" title="The board and the library have the same code">Same</span>';
  const copy = ev.inLibrary && !ev.differs ? ''
    : `<button type="button" class="btn btn-ghost btn-sm ${ev.differs ? 'ev-destructive' : ''}" data-act="to-library"
        title="${ev.differs ? 'Copy this event into the library, replacing the library\'s different copy' : 'Copy this event into the local library'}">→ Library</button>`;
  return `<tr data-id="${esc(ev.id)}" data-board="1" data-language="${ev.language}">
      ${nameCell(ev)}<td>${gameChips(ev.supportedGames)}</td><td class="num">${ev.parameters.length}</td><td>${status}</td>
      <td class="ev-actions">${copy}
        <button type="button" class="btn btn-ghost btn-sm" data-act="export" title="Download the event's code">Export</button>
        <button type="button" class="btn btn-ghost btn-sm ev-del" data-act="delete" title="Delete the event from the board (and its uses on the board)">Delete</button></td>
    </tr>`;
}

function libRow(ev, onBoard) {
  const status = !onBoard ? '<span class="muted small">Not on Board</span>'
    : onBoard.differs ? '<span class="pill warn" title="The board\'s file has different code for this event">Differs</span>'
      : '<span class="pill ok" title="The board and the library have the same code">Same</span>';
  const copy = onBoard && !onBoard.differs ? ''
    : `<button type="button" class="btn btn-ghost btn-sm ${onBoard?.differs ? 'ev-destructive' : ''}" data-act="to-board"
        title="${onBoard?.differs ? 'Copy this event into the board file, replacing the board\'s different copy' : 'Copy this event into the board file'}">→ Board</button>`;
  return `<tr data-id="${esc(ev.id)}" data-language="${ev.language}">
      ${nameCell(ev)}<td>${gameChips(ev.supportedGames)}</td><td class="num">${ev.parameters.length}</td><td>${status}</td>
      <td class="ev-actions">${copy}
        <button type="button" class="btn btn-ghost btn-sm" data-act="export" title="Download the event's code">Export</button>
        <button type="button" class="btn btn-ghost btn-sm ev-del" data-act="delete" title="Delete the event from the library">Delete</button></td>
    </tr>`;
}

async function onListClick(e) {
  const btn = e.target.closest('[data-act]');
  const tr = e.target.closest('tr[data-id]');
  if (!btn || !tr) return;
  const id = tr.dataset.id;
  const board = tr.dataset.board === '1';
  const enc = encodeURIComponent(id);
  const ev = (board ? data.boardEvents : data.events).find(x => x.id === id);
  switch (btn.dataset.act) {
    case 'edit':
      await act(async () => {
        const full = await api(board ? `/api/board/events/${enc}` : `/api/events/${enc}`);
        openEditor({ id, board, language: full.language ?? 0, code: full.code || '' });
      });
      break;
    case 'export':
      await act(async () => {
        if (board) {
          const full = await api(`/api/board/events/${enc}`);
          saveBlob(new Blob([full.code || '']), id + (EXT[full.language] || '.s'));
          toast(`Saved ${id}${EXT[full.language] || '.s'}.`, 'success', 3000);
        } else {
          toast(`Saved ${await download(`/api/events/${enc}/export`, undefined, id + (EXT[ev?.language] || '.s'))}.`, 'success', 3000);
        }
      });
      break;
    case 'delete':
      if (!await confirmDialog(board ? `Delete ${ev?.name || id} from the board? Spaces using it lose it.`
        : `Are you sure you want to delete ${ev?.name || id}?`, { title: 'Delete Event', yes: 'Delete', danger: true })) return;
      await act(async () => {
        await api(board ? `/api/board/events/${enc}/delete` : `/api/events/${enc}/delete`, {});
        toast(`Deleted ${ev?.name || id}.`, 'success', 3000);
        await load();
      });
      break;
    case 'to-board': {
      const onBoard = data.boardEvents.find(x => x.id === id);
      if (onBoard?.differs && !await confirmDialog(`Are you sure you want to overwrite the board's copy of ${id}? The two copies are different.`,
        { title: 'Copy to Board', yes: 'Overwrite', danger: true })) return;
      await act(async () => {
        await api(`/api/events/${enc}/copy-to-board`, {});
        toast(`Copied ${id} into the board's file.`, 'success', 3000);
        await load();
      });
      break;
    }
    case 'to-library':
      if (ev?.differs && !await confirmDialog(`Are you sure you want to overwrite the library's copy of ${id}? The two copies are different.`,
        { title: 'Copy to Library', yes: 'Overwrite', danger: true })) return;
      await act(async () => {
        await api(`/api/board/events/${enc}/copy-to-library`, {});
        toast(`Copied ${id} into the library.`, 'success', 3000);
        await load();
      });
      break;
    default:
  }
}

async function importEvent() {
  const file = await pickFile('.s,.asm,.c,.txt');
  if (!file) return;
  await busy(`Importing ${file.name}…`, async () => {
    const res = await api(`/api/events/import?name=${encodeURIComponent(file.name)}`, file);
    toast(`Imported ${res.event?.name || file.name} into the library.`, 'success');
    await load();
  });
}

// The editor

function buildEditor() {
  $('#evEdit', root).innerHTML = `<div class="layout ev-layout">
      <aside class="sidebar">
        <section class="card">
          <div class="card-head"><h2>Event Details</h2><span class="pill" id="edLangPill"></span></div>
          <label class="field"><span class="field-label tip" title="The event's name, also its id: it must not be a built-in event's">Name</span>
            <input id="edName" class="input" spellcheck="false" placeholder="My Event" title="The event's name (the NAME comment of the code)"></label>
          <div class="field">
            <span class="field-label tip" title="The games the event's code is written for (the GAMES comment)">Supported Games</span>
            <div class="ev-game-grid" id="edGames">
              ${GAMES.map(([name, id, label]) => `<button type="button" class="ev-game-toggle" data-game="${id}" title="${esc(`Supports ${name.replace('_', ' ')} (${id})`)}">${esc(label)}</button>`).join('')}
            </div>
          </div>
          <div class="field">
            <span class="field-label tip" title="How the game runs the event (the EXECUTION comment)">Execution Type</span>
            <div class="segmented" role="group" aria-label="Execution type" id="edExec">
              <button type="button" data-exec="1" title="The game will execute the event function directly">Direct</button>
              <button type="button" data-exec="2" title="The game will use its process system when executing the event function">Process</button>
            </div>
          </div>
          <div class="field">
            <span class="field-label tip" title="Values chosen for each use of the event on a board (the PARAM comments)">Parameters</span>
            <ul class="ev-params" id="edParams"></ul>
            <div class="input-row ev-param-add">
              <select id="edParamType" class="input" title="The parameter's type">
                <option value="">Type…</option>
                ${PARAM_TYPES.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('')}
              </select>
              <input id="edParamName" class="input mono" placeholder="Name" spellcheck="false" title="The parameter's name: letters, digits, _, ? and !">
              <button type="button" class="btn btn-sm" id="edParamAdd" title="Add the parameter">Add</button>
            </div>
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>Test</h2>
            <button type="button" class="btn btn-sm" id="edTest" title="Assemble or compile the event for each supported game, without saving it">Test Compile</button></div>
          <div id="edTestOut"><p class="hint ev-first">Checks that the code assembles (or compiles) for each supported game.</p></div>
        </section>
      </aside>
      <main class="main ev-editor-main">
        <div class="ev-editor-bar">
          <button type="button" class="btn btn-sm btn-ghost" id="edBack" title="Return to the event list">← Events</button>
          <div class="ev-editor-file"><span class="ev-dirty" id="edDirty" title="Unsaved changes" hidden>●</span>
            <span class="mono" id="edFile"></span><span class="pill" id="edWhere"></span></div>
          <div class="card-actions">
            <button type="button" class="btn btn-sm" id="edExport" title="Download the code as it is in the editor">Export</button>
            <button type="button" class="btn btn-sm btn-ghost ev-del" id="edDelete" title="Delete the event">Delete</button>
            <button type="button" class="btn btn-sm btn-primary" id="edSave" title="Save the event (Ctrl+S)">Save</button>
          </div>
        </div>
        <div class="ev-code-tabs" id="edTabs" hidden>
          <div class="tabs">
            <button type="button" data-tab="src" class="active" title="The C source">C Source</button>
            <button type="button" data-tab="asm" title="The MIPS assembly the C compiles to (for the first supported game)">MIPS Assembly</button>
          </div>
        </div>
        <div class="ev-code" id="edCode"></div>
        <div class="ev-code ev-asm" id="edAsm" hidden></div>
        <div class="ev-editor-foot"><span id="edPos">Line 1, column 1</span>
          <span class="muted" id="edHint">Ctrl+Space completes the game's symbols for the supported games.</span></div>
      </main>
    </div>`;
  const box = $('#evEdit', root);
  $('#edBack', box).addEventListener('click', () => closeEditor());
  $('#edSave', box).addEventListener('click', () => save());
  $('#edExport', box).addEventListener('click', () => {
    const name = (ed.form.name || 'event').trim() || 'event';
    saveBlob(new Blob([editor.getValue()]), name + EXT[ed.language]);
    toast(`Saved ${name}${EXT[ed.language]}.`, 'success', 3000);
  });
  $('#edDelete', box).addEventListener('click', deleteFromEditor);
  $('#edTest', box).addEventListener('click', () => test());
  $('#edName', box).addEventListener('input', e => { ed.form.name = e.target.value; formChanged(); });
  for (const b of $$('[data-game]', $('#edGames', box))) {
    b.addEventListener('click', () => {
      const id = b.dataset.game;
      ed.form.games = ed.form.games.includes(id) ? ed.form.games.filter(g => g !== id)
        : GAMES.map(g => g[1]).filter(g => g === id || ed.form.games.includes(g));
      formChanged();
    });
  }
  for (const b of $$('[data-exec]', box)) {
    b.addEventListener('click', () => { ed.form.executionType = +b.dataset.exec; formChanged(); });
  }
  const nameInput = $('#edParamName', box);
  nameInput.addEventListener('input', () => {
    // Only valid characters for an assembler label.
    if (!VALID_PARAM_NAME.test(nameInput.value)) nameInput.value = nameInput.value.replace(/[^\w?!]/g, '');
  });
  const addParam = () => {
    const type = $('#edParamType', box).value;
    const name = nameInput.value;
    if (!type || !name) {
      toast('Choose a type and a name for the parameter.', 'warn', 3000);
      return;
    }
    if (ed.form.parameters.some(p => p.name === name)) {
      toast(`There is already a parameter named ${name}.`, 'warn', 3000);
      return;
    }
    ed.form.parameters = [...ed.form.parameters, { name, type }];
    nameInput.value = '';
    $('#edParamType', box).value = '';
    formChanged();
  };
  $('#edParamAdd', box).addEventListener('click', addParam);
  nameInput.addEventListener('keydown', e => { if (e.key === 'Enter') addParam(); });
  $('#edParams', box).addEventListener('click', e => {
    const del = e.target.closest('[data-del-param]');
    if (!del) return;
    ed.form.parameters = ed.form.parameters.filter(p => p.name !== del.dataset.delParam);
    formChanged();
  });
  for (const b of $$('[data-tab]', box)) b.addEventListener('click', () => showCodeTab(b.dataset.tab));
}

async function ensureEditor() {
  if (editor) return;
  editor = await createCodeEditor($('#edCode', root), {
    language: ed.language,
    value: '',
    onChange: code => codeChanged(code),
    onCursor: (line, col) => { $('#edPos', root).textContent = `Line ${line}, column ${col}`; },
    getGames: () => ed?.form.games || [],
    onSave: () => save(),
  });
}

async function openEditor({ id = null, board = false, language = 1, code = null }) {
  const text = code ?? DEFAULT_CODE[language];
  const header = readHeader(text);
  ed = {
    id, board, language, saved: code === null ? null : text, tab: 'src',
    form: { name: header.name || '', games: header.games || [], executionType: header.executionType || 1, parameters: header.parameters },
  };
  mode = 'edit';
  $('#evList', root).hidden = true;
  $('#evEdit', root).hidden = false;
  try {
    await ensureEditor();
  } catch (e) {
    toast(`The code editor couldn't be loaded: ${e.message}`, 'error');
    closeEditor(true);
    return;
  }
  editor.setLanguage(language);
  editor.setValue(text);
  if (asmView) asmView.setValue('');
  showCodeTab('src');
  $('#edTestOut', root).innerHTML = '<p class="hint ev-first">Checks that the code assembles (or compiles) for each supported game.</p>';
  renderEditor();
  editor.focus();
}

async function closeEditor(force) {
  if (!force && isDirty() && !await confirmDialog('Are you sure you want to exit without saving the event?',
    { title: 'Unsaved Event', yes: 'Discard Changes', danger: true })) return;
  mode = 'list';
  $('#evEdit', root).hidden = true;
  $('#evList', root).hidden = false;
  load();
}

function isDirty() {
  return !!ed && mode === 'edit' && (ed.saved === null || ed.saved !== editor?.getValue());
}

/** The form changed: rewrite the code's header comments. */
function formChanged() {
  const code = writeHeader(editor.getValue(), ed.form, ed.language);
  syncing = true;
  try {
    editor.setValue(code);
  } finally {
    syncing = false;
  }
  renderEditor();
}

/** The code changed: read its header comments into the form. */
function codeChanged(code) {
  if (syncing) return;
  const h = readHeader(code);
  if (h.name !== null) ed.form.name = h.name;
  if (h.games !== null) ed.form.games = h.games;
  if (h.executionType) ed.form.executionType = h.executionType;
  ed.form.parameters = h.parameters;
  renderEditor(true);
}

function renderEditor(fromCode) {
  const box = $('#evEdit', root);
  const name = $('#edName', box);
  if (!fromCode || document.activeElement !== name) {
    if (name.value !== ed.form.name) name.value = ed.form.name;
  }
  for (const b of $$('[data-game]', $('#edGames', box))) b.classList.toggle('active', ed.form.games.includes(b.dataset.game));
  for (const b of $$('[data-exec]', box)) b.classList.toggle('active', +b.dataset.exec === ed.form.executionType);
  $('#edParams', box).innerHTML = ed.form.parameters.length
    ? ed.form.parameters.map(p => `<li><span class="ev-param-type">${esc(PARAM_TYPES.find(t => t[0] === p.type)?.[1] || p.type)}</span>
        <span class="mono ev-param-name" title="${esc(p.name)}">${esc(p.name)}</span>
        <button type="button" class="btn btn-ghost btn-sm btn-icon" data-del-param="${esc(p.name)}" title="Remove the parameter ${esc(p.name)}">✕</button></li>`).join('')
    : '<li class="ev-params-empty">No parameters.</li>';
  $('#edLangPill', box).textContent = ed.language === 1 ? 'C' : 'MIPS';
  $('#edFile', box).textContent = (ed.form.name.trim() || 'Untitled Event') + EXT[ed.language];
  const where = $('#edWhere', box);
  where.textContent = ed.board ? 'Board File' : (ed.id ? 'Library' : 'New');
  where.title = ed.board ? `Kept in the file of ${boardName()}` : (ed.id ? 'Kept in your event library' : 'Not saved yet: Save adds it to the library');
  $('#edDirty', box).hidden = !isDirty();
  $('#edDelete', box).hidden = !ed.id;
  $('#edTabs', box).hidden = ed.language !== 1;
}

async function showCodeTab(tab) {
  if (tab === 'asm') {
    const asm = await compileToAsm();
    if (asm === null) return;
    if (!asmView) {
      asmView = await createCodeEditor($('#edAsm', root), { language: 0, readOnly: true, getGames: () => ed?.form.games || [] });
    }
    asmView.setValue(asm);
  }
  ed.tab = tab;
  for (const b of $$('[data-tab]', root)) b.classList.toggle('active', b.dataset.tab === tab);
  $('#edCode', root).hidden = tab !== 'src';
  $('#edAsm', root).hidden = tab !== 'asm';
}

/** The C compiled to MIPS for the first supported game (null when it can't be). */
async function compileToAsm() {
  if (!ed.form.name.trim()) {
    toast('The event name is missing.', 'warn');
    return null;
  }
  if (!ed.form.games.length) {
    toast('At least one game must be supported.', 'warn');
    return null;
  }
  const res = await busy('Compiling…', () => api('/api/events/test', { code: editor.getValue(), language: ed.language }));
  if (!res) return null;
  renderTest(res);
  const first = res.results?.[0];
  if (first && !first.ok) {
    toast(first.error || 'The event didn\'t compile.', 'error', 9000);
    return null;
  }
  if (first?.asm) return first.asm;
  toast('The server didn\'t send the compiled assembly; see the test results.', 'warn');
  return null;
}

function renderTest(res) {
  const outEl = $('#edTestOut', root);
  if (res.error) {
    outEl.innerHTML = `<div class="notice err">${esc(res.error)}</div>`;
    return;
  }
  if (!res.results?.length) {
    outEl.innerHTML = '<div class="notice warn">No supported games: choose at least one.</div>';
    return;
  }
  const ok = res.results.filter(r => r.ok).length;
  outEl.innerHTML = `<p class="hint ev-first ${ok === res.results.length ? 'ok' : 'bad'}">${ok} of ${res.results.length} games passed.</p>
    <ul class="ev-test">${res.results.map(r => `<li>
      <span class="pill ${r.ok ? 'ok' : 'err'}">${r.ok ? 'OK' : 'Failed'}</span>
      <span class="ev-test-game">${esc(GAME_BY_ID[r.game]?.[2] || r.gameName || r.game)}</span>
      ${r.ok ? '' : `<pre class="ev-test-err">${esc(r.error || '')}</pre>`}</li>`).join('')}</ul>`;
}

async function test() {
  const res = await busy('Testing the event…', () => api('/api/events/test', { code: editor.getValue(), language: ed.language }));
  if (!res) return;
  renderTest(res);
  const failed = (res.results || []).filter(r => !r.ok).length;
  if (res.error) toast(res.error, 'error', 9000);
  else if (!failed && res.results.length) toast(`The event works for ${res.results.length} game${res.results.length === 1 ? '' : 's'}.`, 'success', 3000);
}

async function save() {
  if (!ed || mode !== 'edit') return;
  const name = ed.form.name.trim();
  if (!name) {
    toast('An event name must be specified.', 'warn');
    return;
  }
  if (!ed.form.games.length) {
    toast('At least one game must be supported.', 'warn');
    return;
  }
  const code = editor.getValue();
  await busy('Saving the event…', async () => {
    const res = await api('/api/events', { code, language: ed.language, board: ed.board || undefined });
    ed.saved = code;
    ed.id = res.event?.id || name;
    renderEditor();
    if (res.warning) {
      toast(`Saved ${name}, but: ${res.warning}`, 'warn', 12000);
    } else {
      toast(`Saved ${name}${ed.board ? ' in the board\'s file' : ' in the library'}.`, 'success', 3000);
    }
  });
}

async function deleteFromEditor() {
  if (!ed?.id) return;
  if (!await confirmDialog(ed.board ? `Delete ${ed.id} from the board? Spaces using it lose it.`
    : `Are you sure you want to delete ${ed.id}?`, { title: 'Delete Event', yes: 'Delete', danger: true })) return;
  await act(async () => {
    const enc = encodeURIComponent(ed.id);
    await api(ed.board ? `/api/board/events/${enc}/delete` : `/api/events/${enc}/delete`, {});
    toast(`Deleted ${ed.id}.`, 'success', 3000);
    ed.saved = editor.getValue();
    closeEditor(true);
  });
}
