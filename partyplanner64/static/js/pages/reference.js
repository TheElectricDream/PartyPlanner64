// Reference: what the words of event code (MIPS and C), and of a board's background and music
// code, mean, with examples. Search on the left, the entry on the right. The entries come from
// GET /api/reference (lib/reference); the games' functions and data from GET /api/symbols.
// The code editor's hover help links here (js/lib/reference.js openInReference).
import { $, $$, esc, loadCss } from '../api.js';
import {
  loadReference, searchEntries, renderEntry, highlightCode, symbolMap, symbolEntry, kindName,
} from '../lib/reference.js';

// The guides, in the order to read them.
const START = ['concept:events', 'concept:delay-slot', 'concept:stack', 'concept:calling-functions',
  'concept:branches', 'concept:players', 'concept:messages', 'concept:message-text', 'concept:prompts',
  'concept:parameters', 'concept:sleeping', 'concept:random', 'concept:player-struct', 'concept:chains',
  'concept:c-events', 'board:code'];

const GAMES = [['MP1_USA', 'MP1'], ['MP2_USA', 'MP2'], ['MP3_USA', 'MP3']];

let root = null;
let ref = null;
let symbols = new Map();
const view = {
  query: '', category: '', game: 'MP3_USA', current: null, history: [],
};
let ready = null;

function remembered(key, fallback) {
  try {
    return localStorage.getItem(`pp64.reference.${key}`) || fallback;
  } catch {
    return fallback;
  }
}

function remember(key, value) {
  try {
    localStorage.setItem(`pp64.reference.${key}`, value);
  } catch {
    // Storage blocked.
  }
}

export function init(container) {
  loadCss('reference');
  root = container;
  view.game = remembered('game', 'MP3_USA');
  container.innerHTML = `
    <div class="layout ref-layout">
      <aside class="sidebar ref-side">
        <div class="ref-search">
          <input id="refQuery" class="input" type="search" placeholder="Search" spellcheck="false"
            title="Instruction, register, keyword, function or topic" autocomplete="off">
          <div class="segmented ref-cats" id="refCats" role="group" aria-label="Kind"></div>
          <div class="ref-game-row" id="refGameRow">
            <span class="muted">Symbols</span>
            <div class="segmented" id="refGame" role="group" aria-label="Game">
              ${GAMES.map(([id, label]) => `<button type="button" data-game="${id}" title="The functions and data of ${label} (USA)">${label}</button>`).join('')}
            </div>
          </div>
        </div>
        <div class="ref-results" id="refResults" role="listbox" aria-label="Entries"></div>
      </aside>
      <main class="main"><div class="scroll-page ref-main" id="refMain"></div></main>
    </div>`;
  const q = $('#refQuery', root);
  let t = null;
  q.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(() => { view.query = q.value; renderResults(); }, 120);
  });
  q.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const first = $('.ref-result', $('#refResults', root));
      if (first) first.click();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      $('.ref-result', $('#refResults', root))?.focus();
    }
  });
  $('#refResults', root).addEventListener('keydown', e => {
    const items = $$('.ref-result', $('#refResults', root));
    const i = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown' && i >= 0) { e.preventDefault(); items[Math.min(i + 1, items.length - 1)].focus(); }
    if (e.key === 'ArrowUp' && i >= 0) { e.preventDefault(); (i === 0 ? q : items[i - 1]).focus(); }
  });
  for (const b of $$('#refGame button', root)) {
    b.addEventListener('click', async () => {
      view.game = b.dataset.game;
      remember('game', view.game);
      await loadSymbols();
      renderResults();
      if (view.current) show(view.current, { keepHistory: true });
    });
  }
  root.addEventListener('click', e => {
    const a = e.target.closest('.ref-link');
    if (!a || !root.contains(a)) return;
    e.preventDefault();
    openEntry(a.dataset.ref);
  });
  ready = start();
  return ready;
}

async function loadSymbols() {
  symbols = await symbolMap([view.game]);
  for (const b of $$('#refGame button', root)) b.classList.toggle('active', b.dataset.game === view.game);
}

async function start() {
  ref = await loadReference();
  await loadSymbols();
  const cats = $('#refCats', root);
  cats.innerHTML = [['', 'All'], ...ref.categories.map(c => [c, c === 'Board code' ? 'Board' : c])]
    .map(([c, label]) => `<button type="button" data-cat="${esc(c)}" class="${c === view.category ? 'active' : ''}"
      title="${c ? `Only ${esc(c)} entries` : 'Every entry'}">${esc(label)}</button>`).join('');
  for (const b of $$('button', cats)) {
    b.addEventListener('click', () => {
      view.category = b.dataset.cat;
      for (const x of $$('button', cats)) x.classList.toggle('active', x === b);
      renderResults();
    });
  }
  renderResults();
  if (!view.current) renderHome();
}

function resultHtml(e) {
  const active = view.current?.id === e.id ? ' active' : '';
  return `<button type="button" class="ref-result${active}" data-id="${esc(e.id)}" role="option" title="${esc(e.summary)}">
    <span class="ref-r-name${e.kind === 'concept' ? '' : ' mono'}">${esc(e.name)}</span>
    <span class="ref-r-kind">${esc(kindName(e.kind))}</span>
    <span class="ref-r-sum">${esc(e.summary)}</span></button>`;
}

function renderResults() {
  if (!ref) return;
  const box = $('#refResults', root);
  $('#refGameRow', root).hidden = !(view.category === '' || view.category === 'Game');
  const results = searchEntries(ref, view.query, { category: view.category, symbols, games: [view.game] });
  if (!results.length) {
    box.innerHTML = `<div class="empty-state ref-none"><b>No matches</b></div>`;
    return;
  }
  let html;
  if (view.query.trim()) {
    html = `<div class="ref-count muted">${results.length === 300 ? 'The first 300' : results.length} result${results.length === 1 ? '' : 's'}</div>`
      + results.map(r => resultHtml(r.entry)).join('');
  } else {
    // Grouped: by category, then kind; the game's symbols last.
    const groups = new Map();
    for (const { entry } of results) {
      const key = entry.generated ? `More ${view.game.replace('_USA', '')} functions and data` : `${entry.category} · ${kindName(entry.kind)}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(entry);
    }
    html = [...groups].map(([name, list]) => `<div class="ref-group">${esc(name)} <span class="muted">${list.length}</span></div>`
      + list.map(resultHtml).join('')).join('');
  }
  box.innerHTML = html;
  for (const b of $$('.ref-result', box)) b.addEventListener('click', () => openEntry(b.dataset.id));
}

function renderHome() {
  view.current = null;
  const main = $('#refMain', root);
  const guides = START.map(id => ref.byId.get(id)).filter(Boolean);
  main.innerHTML = `<article class="ref-article ref-home">
    <div class="ref-kicker">Reference</div>
    <h1 class="ref-title">Event Code Reference</h1>
    <p class="ref-lead">MIPS, C, event headers and game functions. Every example is test-compiled.</p>
    <div class="ref-body"><p>In code editors: hover a word, or press <b>F1</b>.</p></div>
    <h2 class="ref-h2">Start Here</h2>
    <ol class="ref-guides">${guides.map(g => `<li><a href="#" class="ref-link" data-ref="${esc(g.id)}">${esc(g.name)}</a>
      <span class="muted">${esc(g.summary)}</span></li>`).join('')}</ol>
    <h2 class="ref-h2">Browse</h2>
    <div class="ref-see">${ref.categories.map(c => `<a href="#" class="ref-chip" data-cat="${esc(c)}"><span>${esc(c)}</span>
      <span class="muted">${ref.entries.filter(e => e.category === c).length}</span></a>`).join('')}</div>
  </article>`;
  for (const a of $$('[data-cat]', main)) {
    a.addEventListener('click', e => {
      e.preventDefault();
      $(`#refCats button[data-cat="${CSS.escape(a.dataset.cat)}"]`, root)?.click();
    });
  }
  renderResults();
}

function entryFor(id) {
  if (id.startsWith('sym:')) {
    const sym = symbols.get(id.slice(4).toLowerCase());
    return sym ? symbolEntry(ref, sym, [view.game]) : null;
  }
  const e = ref.byId.get(id);
  if (!e) return null;
  if (e.category === 'Game') {
    const sym = symbols.get(e.name.toLowerCase());
    if (sym) return symbolEntry(ref, sym, [view.game]);
    return { ...e, notInGames: !(e.games || []).includes(view.game), checkedGames: [view.game] };
  }
  return e;
}

function show(entry, { keepHistory = false } = {}) {
  if (!keepHistory && view.current && view.current.id !== entry.id) view.history.push(view.current.id);
  view.current = entry;
  const main = $('#refMain', root);
  main.innerHTML = `<div class="ref-nav">
      <button type="button" class="btn btn-sm btn-ghost" id="refBack" ${view.history.length ? '' : 'disabled'} title="Back">← Back</button>
      <button type="button" class="btn btn-sm btn-ghost" id="refHome" title="Start page">Start</button>
    </div>${renderEntry(entryFor(entry.id) || entry, ref)}`;
  $('#refBack', main).addEventListener('click', () => {
    const prev = view.history.pop();
    if (prev) openEntry(prev, { fromHistory: true });
  });
  $('#refHome', main).addEventListener('click', () => { view.history = []; renderHome(); });
  highlightCode(main);
  main.scrollTop = 0;
  for (const b of $$('.ref-result', $('#refResults', root))) {
    b.classList.toggle('active', b.dataset.id === entry.id);
  }
}

/** Shows an entry (by id: "mips:addiu", "game:AdjustPlayerCoins", "sym:PlaySound"). */
export async function openEntry(id, { fromHistory = false } = {}) {
  await ready;
  const entry = entryFor(id);
  if (!entry) {
    search(id.replace(/^\w+:/, ''));
    return;
  }
  show(entry, { keepHistory: fromHistory });
}

/** Shows the results of a search (e.g. for a word the reference doesn't know). */
export async function search(query) {
  await ready;
  view.query = query;
  view.category = '';
  $('#refQuery', root).value = query;
  for (const x of $$('#refCats button', root)) x.classList.toggle('active', x.dataset.cat === '');
  renderResults();
  $('#refQuery', root).focus();
}

