// The Editor page: lay out a board's spaces and paths.
// A sidebar of cards (Boards, Tools, Properties) next to the board view, with its toolbar, and a
// console (Validation, Log) underneath. The drawing and editing are in js/editor/.
import { $, $$, api, esc, act, toast, loadCss } from '../api.js';
import { Action, BoardType, getEditTools, getPalette, SpaceNames, IMG } from '../editor/constants.js';
import { store } from '../editor/store.js';
import { BoardView } from '../editor/renderer.js';
import { preloadImages } from '../editor/images.js';
import { Interaction, isAddAction } from '../editor/interaction.js';
import { RightClickMenu } from '../editor/rightclick.js';
import { PropertiesCard } from '../editor/properties.js';
import { BoardsCard, messageHtml } from '../editor/boards.js';
import { screenshotDialog } from '../editor/screenshot.js';
import { plainText } from '../editor/board.js';

let app;
let root;
let view;
let interaction;
let rc;
let props;
let boardsCard;
let visible = false;
let zoom = 'fit';          // 'fit' or a scale
let scale = 1;
let validateTimer = null;
let validatedRevision = null;
let consoleTab = 'validation';

const ICON = {
  undo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M9 14 4 9l5-5"/><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg>',
  redo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m15 14 5-5-5-5"/><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></svg>',
  camera: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  fit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m5 12 5 5 9-10"/></svg>',
};

const TEMPLATE = `
<div class="layout editor-page">
  <aside class="sidebar">
    <section class="card boards-card">
      <div class="card-head"><h2>Boards <span class="count board-count"></span></h2>
        <div class="card-actions">
          <button type="button" class="btn btn-sm btn-primary" data-new title="Create a new board for Mario Party 1, 2 or 3">New…</button>
          <button type="button" class="btn btn-sm" data-import title="Open a board saved as a .json file">Import…</button>
        </div></div>
      <ul class="list-box board-list" role="listbox" aria-label="Boards"></ul>
      <div class="board-actions">
        <button type="button" class="btn btn-sm" data-export title="Download the current board as a .json file">Export</button>
        <button type="button" class="btn btn-sm" data-copy title="Make a copy of the current board">Copy</button>
        <button type="button" class="btn btn-sm btn-ghost" data-delete title="Delete the current board">Delete</button>
        <button type="button" class="btn btn-sm btn-go" data-overwrite hidden title="Write the current board over one of the ROM's boards (checked for problems first)">
          <img src="${IMG}/header/romoverwrite.png" alt="">Overwrite to ROM…</button>
      </div>
    </section>

    <section class="card tools-card">
      <div class="card-head"><h2>Tools</h2><span class="pill tool-pill" title="The tool in use: click the board to use it">Move</span></div>
      <div class="tools-body"></div>
    </section>

    <section class="card props-card">
      <div class="card-head"><h2>Properties</h2><span class="pill" hidden></span></div>
      <div class="props-body"></div>
    </section>
  </aside>

  <main class="main">
    <div class="viewer editor-viewer">
      <div class="viewer-toolbar">
        <div class="segmented edit-tools" role="group" aria-label="Editing tools"></div>
        <span class="tb-sep"></span>
        <button type="button" class="btn btn-sm btn-icon" data-undo title="Undo the last change (Ctrl+Z)">${ICON.undo}</button>
        <button type="button" class="btn btn-sm btn-icon" data-redo title="Redo the change undone (Ctrl+Y)">${ICON.redo}</button>
        <span class="tb-sep"></span>
        <div class="zoom" role="group" aria-label="Zoom">
          <button type="button" class="btn btn-sm btn-icon" data-zoom="-" title="Zoom out (Ctrl+scroll)">−</button>
          <button type="button" class="btn btn-sm zoom-level" data-zoom="1" title="Zoom to actual size (100%)">100%</button>
          <button type="button" class="btn btn-sm btn-icon" data-zoom="+" title="Zoom in (Ctrl+scroll)">+</button>
          <button type="button" class="btn btn-sm btn-icon" data-zoom="fit" title="Fit the board in the view">${ICON.fit}</button>
        </div>
        <span class="tb-sep"></span>
        <button type="button" class="btn btn-sm" data-shot title="Take a screenshot of the board">${ICON.camera}<span>Screenshot</span></button>
      </div>
      <div class="legend editor-legend" aria-live="off">
        <span class="lg-board" title="The board shown"></span>
        <span class="lg-cursor mono" title="The pointer's position on the board, in pixels">–</span>
        <span class="lg-hover" title="The space under the pointer"></span>
      </div>
      <div class="board-scroll">
        <div class="board-wrap"><div class="board-stage"></div></div>
      </div>
      <div class="viewer-empty editor-empty"><strong>Loading the Board…</strong><span>One moment.</span></div>
      <div class="ro-banner" hidden>
        <span class="pill warn">Read-Only</span><span>This board is from the ROM.</span>
        <button type="button" class="btn btn-sm btn-primary" data-copyedit title="Make an editable copy of this board and switch to it">Copy to Edit</button>
      </div>
    </div>
    <div class="console editor-console">
      <div class="console-head">
        <div class="tabs" role="tablist">
          <button type="button" data-tab="validation" class="active" title="Problems that would stop the board from working in the game">Validation <span class="count" data-vcount>0</span></button>
          <button type="button" data-tab="log" title="The changes made to the board in this session">Log <span class="count" data-lcount>0</span></button>
        </div>
        <div class="console-actions">
          <button type="button" class="btn btn-ghost btn-sm" data-validate title="Check the board again for problems">${ICON.check}<span>Validate</span></button>
          <button type="button" class="btn btn-ghost btn-sm" data-clearlog title="Clear the log" hidden>Clear</button>
          <button type="button" class="btn btn-ghost btn-sm" data-collapse title="Hide or show the console">▾</button>
        </div>
      </div>
      <div class="log active" data-pane="validation"></div>
      <div class="log" data-pane="log"></div>
    </div>
  </main>
</div>`;

/** The state the renderer draws. */
function st() {
  return {
    board: store.board,
    selected: store.selected,
    library: store.library,
    debug: !!app.setting('ui.debug'),
    highlighted: store.highlighted,
    hoveredBoardEvent: store.hoveredBoardEvent,
    overrideBg: store.overrideBg,
    tempConnections: store.tempConnections,
    selectionBox: store.selectionBox,
  };
}

function redraw(part = 'all') {
  if (!store.board || !view) return;
  const s = st();
  switch (part) {
    case 'lines': view.renderLines(s); break;
    case 'box': view.renderBox(s); break;
    case 'select': view.renderAssociations(s); view.renderSelection(s); break;
    case 'spaces': view.renderSpaces(s); break;
    case 'move':
      view.renderLines(s);
      view.renderAssociations(s);
      view.renderSelection(s);
      view.renderSpaces(s);
      rc.reposition();
      break;
    default:
      view.render(s);
      applyZoom();
      break;
  }
}

// ---------- zoom ----------

function fitScale() {
  const scroll = $('.board-scroll', root);
  const b = store.board;
  if (!b || !scroll.clientWidth) return 1;
  const s = Math.min((scroll.clientWidth - 32) / b.bg.width, (scroll.clientHeight - 78) / b.bg.height);
  return Math.max(0.1, Math.min(1, s));
}

function applyZoom() {
  const b = store.board;
  if (!b) return;
  scale = zoom === 'fit' ? fitScale() : zoom;
  const wrap = $('.board-wrap', root);
  wrap.style.width = `${Math.round(b.bg.width * scale)}px`;
  wrap.style.height = `${Math.round(b.bg.height * scale)}px`;
  $('.board-stage', root).style.transform = `scale(${scale})`;
  const lvl = $('.zoom-level', root);
  lvl.textContent = `${Math.round(scale * 100)}%`;
  $('[data-zoom="fit"]', root).classList.toggle('active', zoom === 'fit');
  rc?.reposition();
}

function setZoom(z, anchor) {
  const scroll = $('.board-scroll', root);
  const old = scale;
  let next;
  if (z === 'fit') next = 'fit';
  else next = Math.max(0.25, Math.min(4, z));
  // Keep the point under the pointer (or the centre) in place.
  const rect = scroll.getBoundingClientRect();
  const ax = anchor ? anchor[0] - rect.left : scroll.clientWidth / 2;
  const ay = anchor ? anchor[1] - rect.top : scroll.clientHeight / 2;
  const bx = (scroll.scrollLeft + ax) / old;
  const by = (scroll.scrollTop + ay) / old;
  zoom = next;
  applyZoom();
  scroll.scrollLeft = bx * scale - ax;
  scroll.scrollTop = by * scale - ay;
}

const ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1, 1.25, 1.5, 2, 3, 4];
function stepZoom(dir) {
  const cur = scale;
  const next = dir > 0 ? ZOOM_STEPS.find(z => z > cur + 0.001) : [...ZOOM_STEPS].reverse().find(z => z < cur - 0.001);
  return next ?? cur;
}

/** Board coordinates of a client point. */
function toBoard(clientX, clientY) {
  const stage = $('.board-stage', root);
  const rect = stage.getBoundingClientRect();
  const b = store.board;
  const sx = b ? b.bg.width / rect.width : 1;
  const sy = b ? b.bg.height / rect.height : 1;
  return [Math.round((clientX - rect.left) * sx), Math.round((clientY - rect.top) * sy)];
}

// ---------- tools ----------

function renderTools() {
  const b = store.board;
  const tools = $('.edit-tools', root);
  const body = $('.tools-body', root);
  const pill = $('.tool-pill', root);
  if (!b) {
    tools.innerHTML = '';
    body.innerHTML = '<p class="hint">Loading…</p>';
    return;
  }
  const ro = store.readonly;
  const edit = getEditTools(b.game, b.type);
  tools.innerHTML = edit.map(t => `<button type="button" data-action="${t.type}" title="${esc(t.title)}"
      class="${store.action === t.type ? 'active' : ''}" ${ro && t.type !== Action.MOVE && t.type !== Action.TELESCOPE ? 'disabled' : ''}>
      <img src="${t.icon}" alt=""><span>${esc(t.name)}</span></button>`).join('');
  const palette = getPalette(b.game, b.type, !!app.setting('ui.advanced'));
  const group = g => palette.filter(p => p.group === g).map(p => `<button type="button" class="tool-btn${store.action === p.type ? ' active' : ''}"
      data-action="${p.type}" title="${esc(p.name)}${p.draggable ? ' (click the board, or drag this onto it)' : ''}" draggable="${p.draggable && !ro}" ${ro ? 'disabled' : ''}>
      <img src="${p.icon}" alt=""></button>`).join('');
  const chars = group('character');
  body.innerHTML = ro
    ? `<div class="notice warn ro-tools">This board is from the ROM and is read-only: you can look at its spaces, but not change them.
        <button type="button" class="btn btn-sm btn-primary" data-copyedit title="Make an editable copy of this board and switch to it">Copy to Edit</button></div>`
    : `<span class="field-label">Spaces</span>
    <div class="palette">${group('space')}</div>
    ${chars ? `<span class="field-label">${b.game === 1 ? 'Characters' : 'Characters & Buildings'}</span><div class="palette">${chars}</div>` : ''}
    <p class="hint tool-hint"></p>`;
  for (const btn of $$('[data-action]', root)) {
    btn.addEventListener('click', () => setAction(Number(btn.dataset.action)));
    btn.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text', JSON.stringify({ action: Number(btn.dataset.action) }));
    });
  }
  $('[data-copyedit]', body)?.addEventListener('click', () => boardsCard.copyBoard(true));
  const cur = [...edit, ...palette].find(t => t.type === store.action);
  pill.textContent = cur ? (cur.group ? cur.name.replace(/^Add |^Mark space as /, '').replace(/^\w/, c => c.toUpperCase()) : cur.name) : 'Move';
  const hint = $('.tool-hint', body);
  if (hint) hint.textContent = toolHint(store.action);
}

function toolHint(action) {
  switch (action) {
    case Action.MOVE: return 'Drag spaces to move them; drag on the board to select several. Ctrl+click adds to the selection. Right-click a space for its menu.';
    case Action.LINE: return 'Drag from a space to another to connect them (in that direction).';
    case Action.LINE_STICKY: return 'Drag across spaces: each is connected to the next one you reach.';
    case Action.ERASE: return 'Click or drag over spaces and lines to erase them.';
    case Action.ROTATE: return 'Select an arrow space, then drag toward where it should point.';
    case Action.TELESCOPE: return 'Move the pointer over the board to see it as the game camera would.';
    case Action.MARK_STAR: return 'Click spaces to toggle whether they can host the star.';
    case Action.MARK_GATE: return 'Click invisible spaces to make them Skeleton Key gates.';
    default:
      return isAddAction(action)
        ? 'Click the board to add this space (Ctrl+click to keep the selection), or drag the button onto the board.'
        : 'Click a space to put this on it (click again to remove it), or click the board to add it on an invisible space.';
  }
}

function setAction(action) {
  if (store.readonly && action !== Action.MOVE && action !== Action.TELESCOPE) return;
  store.setAction(action);
}

function onAction() {
  renderTools();
  const canvas = view.input;
  canvas.dataset.tool = store.action === Action.ERASE ? 'erase'
    : store.action === Action.LINE || store.action === Action.LINE_STICKY ? 'line'
      : store.action === Action.ROTATE ? 'rotate'
        : store.action === Action.MOVE ? 'move' : 'add';
  const telescoping = store.action === Action.TELESCOPE;
  if (telescoping) view.setTelescope(true, st());
  else view.setTelescope(false);
  store.tempConnections = null;
  redraw('lines');
}

// ---------- console ----------

function renderLog() {
  const pane = $('[data-pane="log"]', root);
  pane.innerHTML = store.log.length
    ? store.log.map(l => `<div class="${l.kind === 'err' ? 'l-err' : ''}"><span class="muted">${l.stamp}</span>  ${esc(l.text)}</div>`).join('')
    : '<span class="muted">Changes you make to the board are listed here.</span>';
  pane.scrollTop = pane.scrollHeight;
  $('[data-lcount]', root).textContent = store.log.length;
}

function scheduleValidation(delay = 900) {
  clearTimeout(validateTimer);
  validateTimer = setTimeout(() => runValidation(), delay);
}

async function runValidation(force = false) {
  if (!store.board || !visible) return;
  if (!force && validatedRevision === `${store.index}:${store.rom}:${store.revision}`) return;
  validatedRevision = `${store.index}:${store.rom}:${store.revision}`;
  const pane = $('[data-pane="validation"]', root);
  const count = $('[data-vcount]', root);
  try {
    const res = await api('/api/board/validate');
    if (!res.romLoaded) {
      count.textContent = '–';
      count.className = 'count';
      count.title = 'Validation needs a ROM';
      pane.innerHTML = '<span class="muted">Load a ROM to check this board against the game\'s rules: problems that would stop it from working are listed here.</span>';
      return;
    }
    const results = res.results || [];
    const errors = results.filter(r => r.level === 1).length;
    const warnings = results.length - errors;
    count.textContent = results.length;
    count.className = 'count' + (errors ? ' bad' : warnings ? ' warn' : '');
    count.title = `${errors} error${errors === 1 ? '' : 's'}, ${warnings} warning${warnings === 1 ? '' : 's'}`;
    const line = (level, message) => `<div class="${level === 1 ? 'l-err' : 'l-warn'}">${level === 1 ? '✕ Error' : '! Warning'}  ${messageHtml(message)}</div>`;
    let html = results.length
      ? results.map(r => line(r.level, r.message)).join('')
      : '<div class="l-ok">✓ No problems found.</div>';
    // What stops the board from replacing each of the ROM's boards.
    for (const rb of res.boards || []) {
      if (!rb.errors.length && !rb.warnings.length && !rb.unavailable && !rb.forcedDisabled) continue;
      html += `<div class="l-head">${esc(plainText(rb.name) || `ROM board ${rb.index}`)}${rb.unavailable ? ' (cannot be overwritten currently)' : ''}</div>`;
      html += rb.errors.map(m => line(1, m)).join('') + rb.warnings.map(m => line(2, m)).join('');
    }
    pane.innerHTML = html;
  } catch (e) {
    count.textContent = '?';
    count.className = 'count';
    pane.innerHTML = `<div class="l-err">Validation failed: ${esc(e.message)}</div>`;
  }
}

function setConsoleTab(tab) {
  consoleTab = tab;
  for (const b of $$('.editor-console .tabs button', root)) b.classList.toggle('active', b.dataset.tab === tab);
  for (const p of $$('.editor-console [data-pane]', root)) p.classList.toggle('active', p.dataset.pane === tab);
  $('[data-validate]', root).hidden = tab !== 'validation';
  $('[data-clearlog]', root).hidden = tab !== 'log';
  $('.editor-console', root).classList.remove('collapsed');
}

// ---------- board changes ----------

function onBoard() {
  const b = store.board;
  const empty = $('.editor-empty', root);
  if (!b) return;
  empty.hidden = true;
  if (store.readonly && store.action !== Action.MOVE && store.action !== Action.TELESCOPE) store.setAction(Action.MOVE);
  redraw('all');
  renderTools();
  $('[data-undo]', root).disabled = !store.canUndo || store.readonly;
  $('[data-redo]', root).disabled = !store.canRedo || store.readonly;
  $('.ro-banner', root).hidden = !store.readonly;
  const name = plainText(b.name) || 'Untitled';
  const lg = $('.lg-board', root);
  lg.innerHTML = `<i style="background:var(--accent)"></i>${esc(name)} · MP${b.game}${b.type === BoardType.DUEL ? ' Duel' : ''} · ${b.spaces.length} spaces`;
  if (rc.isOpen()) rc.render();
  if (store.action === Action.TELESCOPE) view.setTelescope(true, st());
  scheduleValidation();
  document.title = `${name} · PartyPlanner64`;
}

function onPointer(x, y) {
  const cur = $('.lg-cursor', root);
  const hover = $('.lg-hover', root);
  if (x === null || x === undefined || !store.board) {
    cur.textContent = '–';
    hover.textContent = '';
    hover.hidden = true;
    return;
  }
  cur.textContent = `${x}, ${y}`;
  const i = interaction.getClickedSpace(x, y);
  hover.hidden = i < 0;
  if (i >= 0) {
    const s = store.board.spaces[i];
    hover.textContent = `Space ${i} · ${SpaceNames[s.type] || 'Type ' + s.type}${s.events?.length ? ` · ${s.events.length} event${s.events.length === 1 ? '' : 's'}` : ''}${s.star ? ' · ★' : ''}`;
  }
}

function onKeyDown(e) {
  if (!visible || !store.board) return;
  if ($('#appDialog').open) return;
  const t = e.target;
  const typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
  const ctrl = e.ctrlKey || e.metaKey;
  if (typing) return;
  if (ctrl && !e.altKey) {
    const k = e.key.toLowerCase();
    if (k === 'z' && !e.shiftKey) { e.preventDefault(); store.undo(); return; }
    if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); store.redo(); return; }
  }
  if (interaction.onKeyDown(e)) {
    e.preventDefault();
    return;
  }
  if (!ctrl && !e.altKey && e.key.length === 1) {
    const tool = getEditTools(store.board.game, store.board.type).find(x => x.key === e.key.toLowerCase());
    if (tool) {
      setAction(tool.type);
      e.preventDefault();
    }
  }
}

async function loadBoard() {
  const empty = $('.editor-empty', root);
  try {
    await store.load();
  } catch (e) {
    empty.hidden = false;
    empty.innerHTML = `<strong>The Board Could Not Be Loaded</strong><span>${esc(e.message)}</span>
      <button type="button" class="btn btn-sm" data-retry title="Try loading the board again">Retry</button>`;
    $('[data-retry]', empty).addEventListener('click', () => {
      empty.innerHTML = '<strong>Loading the Board…</strong><span>One moment.</span>';
      loadBoard();
    });
  }
}

export async function init(container, appRef) {
  app = appRef;
  loadCss('editor');
  root = container;
  root.innerHTML = TEMPLATE;
  store.init(app);

  view = new BoardView($('.board-stage', root));
  rc = new RightClickMenu($('.board-wrap', root), (x, y) => [x * scale, y * scale], app);
  interaction = new Interaction({
    view,
    toBoard,
    redraw,
    rc,
    onPointer,
    onDragged: () => props.syncCoords(),
    onTelescope: (x, y) => {
      if (x === null) view.telescopeLeave(st());
      else view.telescopeAt(st(), x, y);
    },
  });
  boardsCard = new BoardsCard($('.boards-card', root), app);
  props = new PropertiesCard($('.props-card', root), app, {
    showPage: (name, section) => {
      if (section) sessionStorage.setItem('pp64.details.section', section);
      app.showPage(name);
    },
    copyBoard: () => boardsCard.copyBoard(true),
  });

  // Toolbar
  $('[data-undo]', root).addEventListener('click', () => store.undo());
  $('[data-redo]', root).addEventListener('click', () => store.redo());
  for (const btn of $$('[data-zoom]', root)) {
    btn.addEventListener('click', () => {
      const z = btn.dataset.zoom;
      setZoom(z === 'fit' ? 'fit' : z === '1' ? 1 : stepZoom(z === '+' ? 1 : -1));
    });
  }
  $('.board-scroll', root).addEventListener('wheel', e => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    setZoom(stepZoom(e.deltaY < 0 ? 1 : -1), [e.clientX, e.clientY]);
  }, { passive: false });
  $('[data-shot]', root).addEventListener('click', () => act(() => screenshotDialog()));
  $('.ro-banner [data-copyedit]', root).addEventListener('click', () => boardsCard.copyBoard(true));

  // Console
  for (const b of $$('.editor-console .tabs button', root)) b.addEventListener('click', () => setConsoleTab(b.dataset.tab));
  $('[data-validate]', root).addEventListener('click', () => runValidation(true));
  $('[data-clearlog]', root).addEventListener('click', () => {
    store.log.length = 0;
    renderLog();
  });
  $('[data-collapse]', root).addEventListener('click', e => {
    const c = $('.editor-console', root);
    c.classList.toggle('collapsed');
    e.currentTarget.textContent = c.classList.contains('collapsed') ? '▴' : '▾';
    applyZoom();
  });
  setConsoleTab('validation');
  renderLog();

  store.on('board', onBoard);
  store.on('selection', () => {
    redraw('select');
    if (rc.isOpen() && !store.selected.includes(rc.index)) rc.close();
  });
  store.on('highlight', () => redraw('select'));
  store.on('overridebg', () => redraw('all'));
  store.on('action', onAction);
  store.on('library', () => redraw('all'));
  store.on('log', renderLog);
  app.on('state', () => renderTools());
  app.on('settings', () => { renderTools(); redraw('all'); });

  document.addEventListener('keydown', onKeyDown);
  new ResizeObserver(() => { if (visible && zoom === 'fit') applyZoom(); }).observe($('.board-scroll', root));

  preloadImages().then(() => redraw('all'));
  store.loadLibrary();
  await loadBoard();
  onAction();
}

export function show() {
  visible = true;
  if (store.board) {
    redraw('all');
    scheduleValidation(200);
  }
}

export function hide() {
  visible = false;
  rc?.close();
}

export { toast };
