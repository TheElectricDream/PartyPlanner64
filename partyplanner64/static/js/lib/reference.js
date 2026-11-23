// The code reference: what the words of event, background and music code mean.
// GET /api/reference (lib/reference, explained entries) and GET /api/symbols (the games'
// functions and data, with the symbol tables' comments) are loaded once and shared by the
// code editor (hover help, completions: js/lib/codeeditor.js) and the Reference page.
//
//   const ref = await loadReference();
//   lookupWord(ref, 'addiu', { lang: 'mips', context: 'event', symbols });   // an entry, or null
//   searchEntries(ref, 'coins', { category: 'Game', symbols });              // [{entry, score}]
//   el.innerHTML = renderEntry(entry, { compact: true }); highlightCode(el);
//
// An entry is as lib/reference/__init__.py describes. A game symbol without an explained entry
// becomes one here (symbolEntry), with the symbol table's comment and a generated example.

let refPromise = null;

/** The reference (once): {categories, entries, functions: {name: sentence}, byId: Map, byWord: Map<word, entry[]>}. */
export function loadReference() {
  if (!refPromise) {
    refPromise = fetch('/api/reference')
      .then(r => (r.ok ? r.json() : { categories: [], entries: [], functions: {} }))
      .catch(() => ({ categories: [], entries: [], functions: {} }))
      .then(data => {
        const byId = new Map();
        const byWord = new Map();
        for (const e of data.entries) {
          byId.set(e.id, e);
          for (const w of e.words) {
            if (!byWord.has(w)) byWord.set(w, []);
            byWord.get(w).push(e);
          }
        }
        return { ...data, byId, byWord };
      });
  }
  return refPromise;
}

// The games' symbols, by the games and type asked for.
const symbolCache = new Map();

/** Symbols every one of the games has (GET /api/symbols), cached: [{name, type, addr, desc, note}]. */
export async function fetchSymbols(games, type = '') {
  if (!games?.length) return [];
  const key = `${[...games].sort().join(',')}|${type || ''}`;
  if (!symbolCache.has(key)) {
    const p = fetch(`/api/symbols?games=${encodeURIComponent(games.join(','))}${type ? `&type=${type}` : ''}`)
      .then(r => (r.ok ? r.json() : { symbols: [] }))
      .then(d => d.symbols || [])
      .catch(() => []);
    symbolCache.set(key, p);
  }
  return symbolCache.get(key);
}

/** The symbols of the games as a Map by lower-case name (cached with fetchSymbols). */
const symbolMaps = new Map();
export async function symbolMap(games) {
  const key = [...(games || [])].sort().join(',');
  if (!symbolMaps.has(key)) {
    symbolMaps.set(key, fetchSymbols(games).then(list => new Map(list.map(s => [s.name.toLowerCase(), s]))));
  }
  return symbolMaps.get(key);
}

/** The game names ("MP3_USA") for game ids ("NMVE") or names. */
const GAME_IDS = { CLBE: 'MP1_USA', NMWE: 'MP2_USA', NMVE: 'MP3_USA', CLBJ: 'MP1_JPN', NMWJ: 'MP2_JPN',
  NMVJ: 'MP3_JPN', NLBP: 'MP1_PAL', NMWP: 'MP2_PAL', NMVP: 'MP3_PAL' };
export const gameNames = games => (games || []).map(g => GAME_IDS[g] || g);

export const hex = n => '0x' + (n >>> 0).toString(16).toUpperCase().padStart(8, '0');

const KIND_NAMES = {
  instruction: 'Instruction', pseudo: 'Pseudo-instruction', register: 'Register', directive: 'Directive',
  syntax: 'Assembler syntax', header: 'Event header', parameter: 'Parameter type', concept: 'Guide',
  'c-keyword': 'C', 'c-type': 'C type', 'c-library': 'C library', board: 'Board code',
  function: 'Game function', variable: 'Game data', param: 'Your parameter', label: 'Your label',
};
export const kindName = kind => KIND_NAMES[kind] || kind;

// Symbols without an explained entry

/** The arguments a symbol's comment names: [{reg: 'A0', name: 'player_index'}]. */
function argsOf(note) {
  const out = [];
  for (const piece of (note || '').split(',')) {
    const m = /^\s*A([0-3])\s*=\s*(.+?)\s*$/i.exec(piece);
    if (m) out.push({ reg: `A${m[1]}`, name: m[2] });
  }
  return out;
}

const DATA_TYPES = { u8: ['u8', 'LBU'], s8: ['s8', 'LB'], u16: ['u16', 'LHU'], s16: ['s16', 'LH'],
  u32: ['u32', 'LW'], s32: ['s32', 'LW'] };

/** An entry for a game symbol (the explained one, or one made from the symbol table). */
export function symbolEntry(ref, sym, games) {
  // The explained entry, if it is about (one of) these games: the same name can mean something
  // else in another game (MP2's current_turn is a u16).
  const known = ref.byId.get(`game:${sym.name}`);
  const note = sym.note || sym.desc || '';
  if (known && (!games?.length || known.games?.some(g => games.includes(g)))) {
    return { ...known, symbol: sym, symbolGames: games };
  }
  const isCode = sym.type === 'code';
  const args = argsOf(note);
  let examples;
  let syntax;
  if (isCode) {
    syntax = `${sym.name}(${args.map(a => a.name.replace(/\s+/g, '_')).join(', ')})`;
    examples = [{
      title: 'Call (MIPS)', lang: 'mips', check: 'none',
      code: [...args.map(a => `; ${a.reg} = ${a.name}`), `JAL ${sym.name}`, 'NOP', /return/i.test(note) ? '; the answer is in V0' : '']
        .filter(Boolean).join('\n'),
    }, {
      title: 'Call (C)', lang: 'c', check: 'none',
      code: `${sym.name}(${args.map(a => `/* ${a.name} */ 0`).join(', ')});`,
    }];
  } else {
    const [ctype, load] = DATA_TYPES[sym.type] || ['u8', null];
    syntax = `extern ${ctype} ${sym.name}${load ? '' : '[]'};`;
    examples = load ? [{
      title: 'Read (MIPS)', lang: 'mips', check: 'none',
      code: `LUI T0 hi(${sym.name})\n${load} T1 lo(${sym.name})(T0)   ; T1 = ${sym.name}`,
    }, {
      title: 'Read (C)', lang: 'c', check: 'none',
      code: `extern ${ctype} ${sym.name};\n\n${ctype} value = ${sym.name};`,
    }] : [{
      title: 'Address (MIPS)', lang: 'mips', check: 'none',
      code: `LUI A0 hi(${sym.name})\nADDIU A0 A0 lo(${sym.name})   ; A0 = the address of ${sym.name}`,
    }];
  }
  // What the symbol table's comment says besides the arguments.
  const extra = note.split(',').filter(p => !/^\s*A[0-3]\s*=/i.test(p)).join(',').trim();
  const body = isCode
    ? `${args.length ? 'Arguments: ' + args.map(a => `\`${a.reg}\` ${a.name}`).join(', ') + '. ' : 'Arguments unknown. '}${extra ? `Symbol notes: ${extra}. ` : ''}See [[concept:calling-functions]].`
    : `Game data (${sym.type}). Read with [[syntax:hi-lo]] or [[c:extern|extern]].`;
  // Every named function has a sentence (lib/reference/sentences.py); unnamed ones are by address.
  const summary = isCode
    ? (ref.functions?.[sym.name] || (/^func_/.test(sym.name) ? 'Unnamed game function, named by its address.' : 'Game function.'))
    : (note || 'Game data.');
  return {
    id: `sym:${sym.name}`, kind: isCode ? 'function' : 'variable', category: 'Game', lang: 'any',
    name: sym.name, words: [sym.name.toLowerCase()], syntax, summary,
    body, examples, see: [], tags: [], games, symbol: sym, symbolGames: games, generated: true,
  };
}

// Looking up a word

/** Whether an entry applies in a language and a code context (event, background, music). */
function fits(entry, lang, context) {
  if (entry.lang !== 'any' && lang && entry.lang !== lang) return false;
  if (entry.contexts && context && !entry.contexts.includes(context)) return false;
  return true;
}

/**
 * The entry for a word of code, or null.
 * @param {{lang?: string, context?: string, symbols?: Map, games?: Array<string>,
 *     opcodePosition?: boolean, header?: boolean, user?: Map}} opts
 *   symbols: symbolMap() of the code's games; opcodePosition: the word is a MIPS line's first;
 *   header: the word is a header comment's property; user: the code's own names (parameters,
 *   labels: lower-case name -> entry).
 */
export function lookupWord(ref, word, opts = {}) {
  const w = word.toLowerCase();
  const { lang, context } = opts;
  if (opts.header) return (ref.byWord.get(w) || []).find(e => e.kind === 'header') || null;
  if (opts.user?.has(w)) return opts.user.get(w);
  const candidates = (ref.byWord.get(w) || []).filter(e => fits(e, lang, context));
  if (lang === 'mips') {
    // An opcode only as the line's first word; registers and the rest elsewhere.
    const pick = kinds => candidates.find(e => kinds.includes(e.kind));
    const found = opts.opcodePosition
      ? pick(['instruction', 'pseudo', 'directive', 'syntax'])
      : pick(['register', 'directive', 'syntax', 'board', 'header', 'concept']);
    if (found) return found;
  } else {
    const found = candidates.find(e => e.kind !== 'header' && e.category !== 'Game');
    if (found) return found;
  }
  const sym = opts.symbols?.get(w);
  if (sym) return symbolEntry(ref, sym, opts.games || []);
  const game = candidates.find(e => e.category === 'Game');
  if (game) return { ...game, notInGames: true, checkedGames: opts.games || [] };
  if (/^func_8[0-9a-f]{7}$/i.test(word) || /^d_8[0-9a-f]{7}$/i.test(word)) return ref.byId.get('syntax:func-addr') || null;
  return null;
}

// Searching

/** Entries matching a query, best first: [{entry, score}]. */
export function searchEntries(ref, query, { category = '', symbols = null, games = [], limit = 300 } = {}) {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const pool = ref.entries.filter(e => !category || e.category === category);
  const out = [];
  const scoreOf = e => {
    let total = 0;
    const name = e.name.toLowerCase();
    for (const t of terms) {
      let s = 0;
      if (name === t || e.words.includes(t)) s = 100;
      else if (name.startsWith(t) || e.words.some(w => w.startsWith(t))) s = 60;
      else if (name.includes(t)) s = 45;
      else if (e.tags.some(tag => tag.toLowerCase().includes(t))) s = 35;
      else if ((e.syntax || '').toLowerCase().includes(t)) s = 25;
      else if (e.summary.toLowerCase().includes(t)) s = 20;
      else if (e.body.toLowerCase().includes(t)) s = 8;
      else if (e.examples.some(x => x.code.toLowerCase().includes(t) || x.title.toLowerCase().includes(t))) s = 5;
      if (!s) return 0;
      total += s;
    }
    // Guides and explained entries first, among equals.
    return total + (e.kind === 'concept' ? 3 : 0) + (e.generated ? -2 : 0);
  };
  for (const e of pool) {
    const s = terms.length ? scoreOf(e) : 1;
    if (s) out.push({ entry: e, score: s });
  }
  if (symbols && (!category || category === 'Game')) {
    for (const sym of symbols.values()) {
      if (ref.byId.has(`game:${sym.name}`)) continue;
      const e = symbolEntry(ref, sym, games);
      const s = terms.length ? scoreOf(e) : 1;
      if (s) out.push({ entry: e, score: s });
    }
  }
  // Best first; with nothing to search for, in the reference's own order.
  if (terms.length) out.sort((a, b) => b.score - a.score || a.entry.name.localeCompare(b.entry.name));
  return out.slice(0, limit);
}

// Drawing

function escHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function inline(text, ref) {
  // `code` first (nothing inside it is markup), then **bold** and [[links]].
  return text.split(/(`[^`]*`)/).map(part => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1) return `<code>${escHtml(part.slice(1, -1))}</code>`;
    return escHtml(part)
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/\[\[([^\]|]+)(?:\|([^\]]*))?\]\]/g, (m, id, label) => {
        const target = ref?.byId.get(id);
        const text = label || target?.name || id;
        return `<a href="#" class="ref-link" data-ref="${escHtml(id)}" title="${escHtml(target?.summary || '')}">${text}</a>`;
      });
  }).join('');
}

/** The reference's little markup as HTML: paragraphs, "- " and "1. " lists, `code`, **bold**, [[links]]. */
export function renderMarkup(text, ref) {
  const out = [];
  let para = [];
  let list = null;      // {tag, items}
  const flushPara = () => { if (para.length) out.push(`<p>${inline(para.join(' '), ref)}</p>`); para = []; };
  const flushList = () => { if (list) out.push(`<${list.tag}>${list.items.map(i => `<li>${inline(i, ref)}</li>`).join('')}</${list.tag}>`); list = null; };
  for (const line of (text || '').split('\n')) {
    const bullet = /^\s*- (.*)$/.exec(line);
    const numbered = /^\s*\d+\. (.*)$/.exec(line);
    if (!line.trim()) { flushPara(); flushList(); continue; }
    if (bullet || numbered) {
      flushPara();
      const tag = bullet ? 'ul' : 'ol';
      if (list && list.tag !== tag) flushList();
      if (!list) list = { tag, items: [] };
      list.items.push((bullet || numbered)[1]);
      continue;
    }
    if (list) {
      // A continuation of the last item.
      list.items[list.items.length - 1] += ' ' + line.trim();
      continue;
    }
    para.push(line.trim());
  }
  flushPara();
  flushList();
  return out.join('');
}

const CHECKED = { mips: 'Assembles', event: null, c: 'Compiles', 'c-top': 'Compiles', background: null, music: null };

function exampleHtml(ex, games) {
  const checked = ex.check === 'none' ? null
    : (ex.check === 'event' || ex.check === 'background' || ex.check === 'music') ? (ex.lang === 'c' ? 'Compiles' : 'Assembles')
      : CHECKED[ex.check];
  const forGames = ex.games || games || ['MP3_USA'];
  const params = (ex.params || []).map(([t, n]) => `<code>${escHtml(n)}</code> (${escHtml(t)})`).join(', ');
  return `<figure class="ref-example">
    <figcaption><span class="ref-ex-title">${escHtml(ex.title)}</span>
      <span class="ref-ex-tags"><span class="pill">${ex.lang === 'c' ? 'C' : 'MIPS'}</span>
      ${checked ? `<span class="pill ok" title="The tests ${checked === 'Compiles' ? 'compile' : 'assemble'} this example for ${escHtml(forGames.join(', '))}${ex.check === 'mips' ? ', inside an event that saves RA' : ex.check === 'c' ? ', inside main()' : ''}">✓ ${checked}</span>` : ''}</span></figcaption>
    ${params ? `<div class="ref-ex-note">Parameter${ex.params.length > 1 ? 's' : ''}: ${params}</div>` : ''}
    <pre class="ref-code" data-lang="${ex.lang}">${escHtml(ex.code)}</pre></figure>`;
}

function symbolHtml(entry) {
  const sym = entry.symbol;
  if (!sym) return '';
  const games = entry.symbolGames?.length ? entry.symbolGames.join(', ') : '';
  const note = sym.note || sym.desc;
  return `<div class="ref-symbol">
    <span class="mono">${hex(sym.addr)}</span> <span class="muted">${escHtml(sym.type)}${games ? ` · ${escHtml(games)}` : ''}</span>
    ${note && !entry.generated ? `<div class="ref-symbol-note"><span class="muted">Symbols:</span> ${escHtml(note)}</div>` : ''}
  </div>`;
}

/**
 * An entry as HTML. compact: for hover help (the summary, one short example, a link to the
 * Reference). Call highlightCode() on the element after inserting it.
 */
export function renderEntry(entry, ref, { compact = false } = {}) {
  const kicker = [entry.category, kindName(entry.kind)].filter((x, i, a) => x && a.indexOf(x) === i).join(' · ');
  const games = entry.games?.length ? `<span class="ref-games">${entry.games.map(g => `<span class="pill">${escHtml(g.replace('_USA', ''))}</span>`).join('')}</span>` : '';
  const warn = entry.notInGames
    ? `<div class="ref-warn">Not in ${escHtml((entry.checkedGames || []).join(', ') || 'this game')}${entry.games ? `; only ${escHtml(entry.games.join(', '))}` : ''}.</div>` : '';
  if (compact) {
    const ex = entry.examples.find(x => x.code.split('\n').length <= 9);
    const openable = !String(entry.id).startsWith('user:');
    return `<div class="ref-pop">
      <div class="ref-kicker">${escHtml(kicker)}${games}</div>
      <div class="ref-pop-title"><span class="mono">${escHtml(entry.name)}</span></div>
      ${entry.syntax && entry.syntax !== entry.name ? `<div class="ref-syntax mono">${escHtml(entry.syntax)}</div>` : ''}
      ${warn}
      <div class="ref-pop-summary">${inline(entry.summary, ref)}</div>
      ${symbolHtml(entry)}
      ${ex ? exampleHtml(ex, entry.games) : ''}
      ${openable ? `<div class="ref-pop-foot"><a href="#" class="ref-link" data-ref="${escHtml(entry.id)}">Reference</a><span class="muted">F1</span></div>` : ''}
    </div>`;
  }
  const see = entry.see.map(id => ref.byId.get(id)).filter(Boolean);
  return `<article class="ref-article">
    <div class="ref-kicker">${escHtml(kicker)}${games}</div>
    <h1 class="ref-title${entry.kind === 'concept' ? '' : ' mono'}">${escHtml(entry.name)}</h1>
    ${entry.syntax && entry.syntax !== entry.name ? `<div class="ref-syntax mono">${escHtml(entry.syntax)}</div>` : ''}
    ${warn}
    <p class="ref-lead">${inline(entry.summary, ref)}</p>
    ${symbolHtml(entry)}
    <div class="ref-body">${renderMarkup(entry.body, ref)}</div>
    ${entry.examples.length ? `<h2 class="ref-h2">Example${entry.examples.length > 1 ? 's' : ''}</h2>
      ${entry.examples.map(ex => exampleHtml(ex, entry.games)).join('')}` : ''}
    ${see.length ? `<h2 class="ref-h2">See Also</h2><div class="ref-see">${see.map(s => `<a href="#" class="ref-chip ref-link" data-ref="${escHtml(s.id)}" title="${escHtml(s.summary)}"><span class="mono">${escHtml(s.name)}</span><span class="muted">${escHtml(kindName(s.kind))}</span></a>`).join('')}</div>` : ''}
  </article>`;
}

/** Colours the code of the examples in el (as the code editor does), once CodeMirror is loaded. */
export async function highlightCode(el) {
  const blocks = [...el.querySelectorAll('pre.ref-code:not([data-done])')];
  if (!blocks.length) return;
  const { loadCodeMirror, mipsMode } = await import('./codeeditor.js');
  const cm = await loadCodeMirror();
  for (const pre of blocks) {
    pre.dataset.done = '1';
    const code = pre.textContent;
    try {
      const language = pre.dataset.lang === 'c' ? cm.languageFor('c').language : cm.StreamLanguage.define(mipsMode);
      const tree = language.parser.parse(code);
      let html = '';
      let pos = 0;
      cm.highlightTree(tree, cm.classHighlighter, (from, to, classes) => {
        if (from > pos) html += escHtml(code.slice(pos, from));
        html += `<span class="${classes}">${escHtml(code.slice(from, to))}</span>`;
        pos = to;
      });
      html += escHtml(code.slice(pos));
      pre.innerHTML = html;
    } catch (e) {
      console.warn('Could not highlight an example', e);
    }
  }
}

/** Shows an entry on the Reference page (or, with no id, the results of a search). */
export async function openInReference(id, query = '') {
  const app = window.pp64;
  if (!app) return;
  await app.showPage('reference');
  const page = await import('../pages/reference.js');
  if (id) page.openEntry(id);
  else page.search(query);
}
