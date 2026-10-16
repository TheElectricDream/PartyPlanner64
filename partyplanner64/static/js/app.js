// The PartyPlanner64 page: the top bar, page tabs and the app state shared by the pages.
// Talks to the Python server over JSON (js/api.js) and server-sent events (/api/events).
//
// Pages are modules in js/pages/<name>.js exporting:
//   init(container, app)  once, the first time the page is shown: fill the container;
//   show()                (optional) each time the page is shown;
//   hide()                (optional) each time another page is shown.
import { $, $$, api, act, busy, pickFile, download, confirmDialog, toast } from './api.js';

const listeners = new Map();      // kind -> Set of callbacks
const pages = new Map();          // name -> { module, container }
let currentPage = null;

/** The app, as pages see it. */
export const app = {
  /** The last GET /api/state: { version, rom, settings, boards }. */
  state: null,

  /** Calls fn(data) for an event: a server event (e.g. 'boards', 'rom', 'settings'), or 'state'. */
  on(kind, fn) {
    if (!listeners.has(kind)) listeners.set(kind, new Set());
    listeners.get(kind).add(fn);
    return () => listeners.get(kind).delete(fn);
  },

  /** Tells the listeners of kind (as a server event would). */
  emit(kind, data) {
    for (const fn of listeners.get(kind) || []) {
      try {
        fn(data);
      } catch (e) {
        console.error(e);
      }
    }
  },

  /** Reloads GET /api/state and tells the 'state' listeners. */
  async refresh() {
    app.state = await api('/api/state');
    renderTopbar();
    app.emit('state', app.state);
    return app.state;
  },

  /** A setting's value (settings use the original's ids, e.g. 'ui.advanced'). */
  setting(id) {
    return app.state?.settings?.[id];
  },

  /** Shows a page (by name, e.g. 'editor'). */
  showPage,

  /** The name of the page shown. */
  get page() {
    return currentPage;
  },
};
window.pp64 = app;   // for debugging in the console

// The top bar

function needsMet(needs) {
  if (!needs) return true;
  return needs.split(/\s+/).every(n => (
    n === 'rom' ? !!app.state?.rom
      : n === 'advanced' ? !!app.setting('ui.advanced')
        : n === 'debug' ? !!app.setting('ui.debug')
          : true));
}

function renderTopbar() {
  const s = app.state;
  if (!s) return;
  const rom = s.rom;
  const boards = s.boards?.list?.length ?? 0;
  $('#hostLine').textContent = rom
    ? `${rom.title || rom.gameName} · ${boards} board${boards === 1 ? '' : 's'}`
    : `v${s.version} · ${boards} board${boards === 1 ? '' : 's'} · no ROM open`;
  const badge = $('#romBadge');
  badge.className = 'badge ' + (rom ? (rom.supported ? 'badge-ok' : 'badge-warn') : 'badge-idle');
  badge.lastElementChild.textContent = rom ? (rom.shortName || rom.gameName) : 'No ROM';
  badge.title = rom ? `${rom.fileName || ''} (${rom.game})` : 'Load a ROM to play your boards and to see the game\'s own';
  $('#romLoadBtn').hidden = !!rom;
  $('#romSaveBtn').hidden = !rom;
  $('#romCloseBtn').hidden = !rom;
  for (const btn of $$('.page-tabs button')) {
    btn.hidden = !needsMet(btn.dataset.needs);
  }
  // A page that is no longer available: back to the editor.
  const active = $(`.page-tabs button[data-page="${currentPage}"]`);
  if (currentPage && active?.hidden) showPage('editor');
}

// Pages

async function showPage(name) {
  if (!document.getElementById(`page-${name}`)) name = 'editor';
  if (currentPage && currentPage !== name) {
    const prev = pages.get(currentPage);
    prev?.module?.hide?.();
    document.getElementById(`page-${currentPage}`).hidden = true;
  }
  currentPage = name;
  for (const btn of $$('.page-tabs button')) btn.classList.toggle('active', btn.dataset.page === name);
  const container = document.getElementById(`page-${name}`);
  container.hidden = false;
  try {
    localStorage.setItem('pp64.page', name);
  } catch {
    // Storage blocked.
  }
  let entry = pages.get(name);
  if (!entry) {
    entry = { module: null, container };
    pages.set(name, entry);
    try {
      entry.module = await import(`./pages/${name}.js`);
      await entry.module.init?.(container, app);
    } catch (e) {
      console.error(e);
      container.innerHTML = `<div class="scroll-page"><div class="notice err">This page failed to load: ${e.message}</div></div>`;
      return;
    }
  }
  if (currentPage === name) entry.module?.show?.();
}

// The ROM

async function loadRom() {
  const file = await pickFile('.z64,.n64,.v64,.rom,.bin');
  if (!file) return;
  await busy(`Opening ${file.name}…`, async () => {
    const res = await api(`/api/rom?name=${encodeURIComponent(file.name)}`, file);
    await app.refresh();
    app.emit('rom', res);
    toast(`Opened ${res.rom?.title || file.name}.`, 'success');
  });
}

async function saveRom() {
  await busy('Writing the ROM…', async () => {
    const name = await download('/api/rom/save', {}, 'MarioParty.z64');
    toast(`Saved ${name}.`, 'success');
  });
}

async function closeRom() {
  if (!await confirmDialog('Close the ROM? Boards written to it but not saved are lost; your own boards stay.',
    { title: 'Close ROM', yes: 'Close ROM' })) return;
  await act(async () => {
    await api('/api/rom/close', {});
    await app.refresh();
    app.emit('rom', null);
  });
}

// Server events: changes made elsewhere (another tab, a long job finishing).

function connectEvents() {
  const es = new EventSource('/api/events');
  for (const kind of ['state', 'boards', 'board', 'rom', 'settings', 'events', 'log', 'progress']) {
    es.addEventListener(kind, e => {
      let data = null;
      try {
        data = JSON.parse(e.data);
      } catch {
        // No data.
      }
      if (kind === 'state' || kind === 'rom' || kind === 'settings') {
        act(() => app.refresh());
      }
      app.emit(kind, data);
    });
  }
  es.onerror = () => {
    $('#hostLine').textContent = 'Reconnecting to the PartyPlanner64 server…';
  };
  es.onopen = () => renderTopbar();
}

// Start

async function start() {
  for (const btn of $$('.page-tabs button')) btn.addEventListener('click', () => showPage(btn.dataset.page));
  $('#romLoadBtn').addEventListener('click', () => loadRom());
  $('#romSaveBtn').addEventListener('click', () => saveRom());
  $('#romCloseBtn').addEventListener('click', () => closeRom());
  try {
    await app.refresh();
  } catch (e) {
    $('#hostLine').textContent = `Cannot reach the server: ${e.message}`;
    toast(`Cannot reach the PartyPlanner64 server: ${e.message}`, 'error', 15000);
    return;
  }
  connectEvents();
  let page = 'editor';
  try {
    page = new URLSearchParams(location.search).get('page') || localStorage.getItem('pp64.page') || 'editor';
  } catch {
    // Storage blocked.
  }
  const btn = $(`.page-tabs button[data-page="${page}"]`);
  showPage(btn && !btn.hidden ? page : 'editor');
}

start();
