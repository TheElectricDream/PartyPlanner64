// A CodeMirror 6 editor for code run by the game: events, and a board's background and music
// code. MIPS assembly or C. Ports apps/partyplanner64/utils/lib/mp-mips-codemirror.ts (the
// "mips-pp64" mode), mp-mips-autocomplete.ts and components/codemirrorwrapper.tsx, and adds the
// code reference (js/lib/reference.js): hover help on every word, explained completions, and F1
// to open the Reference page at the word by the cursor.
//
//   const ed = await createCodeEditor(parent, { language: 0, value, onChange, getGames, onSave, context });
//   ed.getValue(); ed.setValue(text); ed.setLanguage(1); ed.setReadOnly(true); ed.destroy();
//
// language: 0 MIPS assembly, 1 C (EventCodeLanguage). context: what the code is, for the names
// only it has: 'event' (the default), 'background' (DEFAULT_BG, ...) or 'music'. getGames: the
// games (ids or names) whose symbols complete and explain. The editor styles itself (dark).
import {
  fetchSymbols, gameNames, hex, highlightCode, loadReference, lookupWord, openInReference, renderEntry,
  symbolEntry, symbolMap,
} from './reference.js';

export { fetchSymbols };

const CM_URL = '/static/vendor/codemirror/codemirror.js';
let cmPromise = null;

/** The CodeMirror bundle (loaded once). */
export function loadCodeMirror() {
  if (!cmPromise) cmPromise = import(CM_URL);
  return cmPromise;
}

// mp-mips-codemirror.ts
const DIRECTIVES_RE = /\.(ascii|asciiz|align|beginstatic|byte|definelabel|else|elseif|endif|endstatic|fill|float|halfword|if|skip|word)\b/i;
const REGS_RE = /\$?(a([0-3]|t)|f([0-9][1-9]?|p)|g(p)|k([0-1])|r(0|a)|s([0-8]|p)|t(\d)|v([0-1])|zero)\b/i;
const OPCODES = 'abs.s abs.d add add.s add.d addi addiu addu and andi bc1f bc1fl bc1t bc1tl beq beql beqz bgez bgezal bgezall bgezl bgtz bgtzl blez blezl bltz bltzal bltzall bltzl bne bnel bnez bnezl break c.f.s c.un.s c.eq.s c.ueq.s c.olt.s c.ult.s c.ole.s c.ule.s c.sf.s c.ngle.s c.seq.s c.ngl.s c.lt.s c.nge.s c.le.s c.ngt.s c.f.d c.un.d c.eq.d c.ueq.d c.olt.d c.ult.d c.ole.d c.ule.d c.sf.d c.ngle.d c.seq.d c.ngl.d c.lt.d c.nge.d c.le.d c.ngt.d ceil.l.s ceil.l.d ceil.w.s ceil.w.d cfc1 ctc1 cop0 cop1 cop2 cop3 cvt.d.s cvt.d.w cvt.d.l cvt.l.d cvt.s.d cvt.s.w cvt.s.l cvt.w.s cvt.w.d dadd daddi daddiu daddu ddiv ddivu div div.s div.d divu dmfc1 dmult dmultu dmtc1 dsll dsll32 dsllv dsra dsra32 dsrav dsrl dsrl32 dsrlv dsub dsubu floor.l.s floor.l.d floor.w.s floor.w.d j jal jalr jr lb lbu ld ldc1 ldc2 ldl ldr lh lhu li ll lld lui lw lwc1 lwc2 lwc3 lwl lwr lwu madd.s madd.d mfc1 mfhi mflo mov.s mov.d move movt msub.s msub.d mtc1 mthi mtlo mul.s mul.d mult multu neg.s neg.d nop nor or ori round.l.s round.l.d round.w.s round.w.d sb sc scd sd sdc1 sdc2 sdl sdr sh sll sllv slt slti sltiu sltu sqrt.s sqrt.d sra srav srl srlv sub sub.s sub.d subu sw swc1 swc2 swc3 swl swr sync syscall teq teqi tge tgei tgeiu tgeu tlt tlti tltiu tltu tne tnei trunc.l.s trunc.l.d trunc.w.s trunc.w.d xor xori'.split(' ');
const OPCODES_RE = new RegExp(`\\b(${OPCODES.map(o => o.replace(/\./g, '\\.')).join('|')})\\b`, 'i');
const NUMBERS_RE = /\b(0x[\da-f]+|o[0-7]+|b[0-1]+|\d+)\b/i;

/** The "mips-pp64" mode, for StreamLanguage. */
export const mipsMode = {
  name: 'mips-pp64',
  startState: () => ({ blockComment: false }),
  token(stream, state) {
    if (stream.eatSpace()) return null;
    let ch;
    // Block comments
    if (state.blockComment || stream.match('/*')) {
      state.blockComment = true;
      let maybeEnd = false;
      while ((ch = stream.next())) {
        if (ch === '/' && maybeEnd) {
          state.blockComment = false;
          break;
        }
        maybeEnd = ch === '*';
      }
      return 'comment';
    }
    // Line comments
    if (stream.eat(';') || stream.match('//')) {
      stream.skipToEnd();
      return 'comment';
    }
    if (stream.eat('"')) {
      while ((ch = stream.next())) {
        if (ch === '"') break;
      }
      return 'string';
    }
    if (stream.eat('.')) {
      if (stream.eatWhile(/\w/)) {
        return DIRECTIVES_RE.test(stream.current()) ? 'def' : null;
      }
    } else if (stream.eatWhile(/[$\w.]/)) {
      const item = stream.current();
      if (OPCODES_RE.test(item)) return 'keyword';
      if (REGS_RE.test(item)) return 'atom';
      if (NUMBERS_RE.test(item)) return 'number';
      return null;
    }
    stream.next();
    return null;
  },
  languageData: { commentTokens: { line: ';', block: { open: '/*', close: '*/' } } },
};

// What the code means where: comments, strings, the header, the code's own names.

const HEADER_PROPS = ['NAME', 'GAMES', 'EXECUTION', 'PARAM'];
const PARAM_TYPE_IDS = { Boolean: 'param:boolean', Number: 'param:number', '+Number': 'param:positive-number',
  Space: 'param:space', 'Space[]': 'param:space-array' };
const GAME_NAMES = ['MP1_USA', 'MP2_USA', 'MP3_USA', 'MP1_JPN', 'MP2_JPN', 'MP3_JPN', 'MP1_PAL', 'MP2_PAL', 'MP3_PAL'];

/** Where a comment starts in a line (outside strings), or -1. */
function commentStart(text, lang) {
  let quote = null;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quote) {
      if (ch === '\\') i++;
      else if (ch === quote) quote = null;
      continue;
    }
    if (ch === '"' || (lang === 'c' && ch === "'")) quote = ch;
    else if (lang === 'mips' && ch === ';') return i;
    else if (ch === '/' && text[i + 1] === '/') return i;
    else if (ch === '/' && text[i + 1] === '*') return i;
  }
  return -1;
}

/** Whether position col of a line is inside a string. */
function inString(text, col, lang) {
  let quote = null;
  for (let i = 0; i < col; i++) {
    const ch = text[i];
    if (quote) {
      if (ch === '\\') i++;
      else if (ch === quote) quote = null;
    } else if (ch === '"' || (lang === 'c' && ch === "'")) {
      quote = ch;
    }
  }
  return !!quote;
}

/** The header line's property ("PARAM") if the line is one: "; PARAM: +Number|toll". */
const headerProp = text => /^\s*(?:;|\/\/)+\s*(NAME|GAMES|EXECUTION|PARAM)\s*:/i.exec(text)?.[1]?.toUpperCase() || null;

/** Whether every line before lineNumber is a comment or blank (the header region). */
function inHeaderRegion(doc, lineNumber) {
  for (let n = 1; n < lineNumber; n++) {
    const t = doc.line(n).text.trim();
    if (t && !t.startsWith(';') && !t.startsWith('//')) return false;
  }
  return true;
}

function userEntry(name, kind, summary, extra = {}) {
  return { id: `user:${kind}:${name}`, kind, category: 'Events', lang: 'any', name, words: [], summary,
    body: '', examples: [], see: [], tags: [], ...extra };
}

/** The code's own names: its parameters (and the names made from them) and, in MIPS, its labels. */
function userNames(doc, lang) {
  const map = new Map();
  const add = e => map.set(e.name.toLowerCase(), e);
  const text = doc.toString();
  for (const m of text.matchAll(/^\s*(?:;|\/\/)+\s*PARAM:\s*([^|\s]+)\|([\w?!]+)/gim)) {
    const [, type, name] = m;
    const typeId = PARAM_TYPE_IDS[type];
    const typeLink = typeId ? `[[${typeId}|${type}]]` : type;
    const see = typeId ? [typeId] : [];
    add(userEntry(name, 'param', `Your ${typeLink} parameter; set per space.`, { syntax: `PARAM: ${type}|${name}`, see }));
    if (type === 'Space') {
      add(userEntry(`${name}_chain_index`, 'param', `Chain of \`${name}\`.`, { see }));
      add(userEntry(`${name}_chain_space_index`, 'param', `Position of \`${name}\` on its chain.`, { see }));
    } else if (type === 'Space[]') {
      add(userEntry(`${name}_length`, 'param', `Count of \`${name}\`.`, { see }));
      add(userEntry(`${name}_chain_indices`, 'param', `Chains of \`${name}\`.`, { see }));
      add(userEntry(`${name}_chain_space_indices`, 'param', `Chain positions of \`${name}\`.`, { see }));
    }
  }
  if (lang === 'mips') {
    for (let n = 1; n <= doc.lines; n++) {
      const m = /^\s*([A-Za-z_][\w?!@]*):/.exec(doc.line(n).text);
      if (!m || map.has(m[1].toLowerCase())) continue;
      // Data or code: the next line with something on it.
      let next = '';
      for (let k = n; k <= doc.lines && !next; k++) {
        const t = (k === n ? doc.line(k).text.slice(m[0].length) : doc.line(k).text).replace(/;.*$/, '').trim();
        next = t;
      }
      const isData = /^\.(ascii|asciiz|byte|db|halfword|dh|word|dw|float|fill|skip)\b/i.test(next);
      add(userEntry(m[1], 'label', `Your label, line ${n}: ${isData ? 'data address' : 'branch target'}.`,
        { see: [isData ? 'syntax:hi-lo' : 'syntax:labels'] }));
    }
  }
  return map;
}

/** The word at pos: {from, to, word, line, col}, or null. */
function wordAt(state, pos, lang) {
  const line = state.doc.lineAt(pos);
  const text = line.text;
  const i = pos - line.from;
  const re = lang === 'mips' ? /[\w$.?!@]/ : /[\w#]/;
  let a = i;
  let b = i;
  while (a > 0 && re.test(text[a - 1])) a--;
  while (b < text.length && re.test(text[b])) b++;
  // MIPS: a word doesn't end with "." (".ascii" starts with one), e.g. "message." in a comment.
  while (b > a && text[b - 1] === '.') b--;
  if (a === b) return null;
  return { from: line.from + a, to: line.from + b, word: text.slice(a, b), line, col: a };
}

/** The reference entry for the word at pos, or null. */
async function entryAt(state, pos, lang, games, context) {
  const w = wordAt(state, pos, lang);
  if (!w) return null;
  const ref = await loadReference();
  const text = w.line.text;
  const user = userNames(state.doc, lang);
  const cstart = commentStart(text, lang);
  if (cstart >= 0 && w.col >= cstart) {
    // In a comment: only the header's words mean something.
    const prop = headerProp(text);
    if (!prop) return null;
    if (w.word.toUpperCase() === prop) return { entry: lookupWord(ref, w.word, { header: true }), w };
    if (prop === 'PARAM') {
      const col = w.from - w.line.from;
      const type = (text[col - 1] === '+' ? '+' : '') + w.word + (text.slice(col + w.word.length).startsWith('[]') ? '[]' : '');
      const typeId = PARAM_TYPE_IDS[type];
      if (typeId) return { entry: ref.byId.get(typeId), w };
      return { entry: user.get(w.word.toLowerCase()) || null, w };
    }
    if (prop === 'GAMES' || prop === 'EXECUTION') return { entry: ref.byId.get(`hdr:${prop.toLowerCase()}`), w };
    return null;
  }
  if (inString(text, w.col, lang)) return null;
  const before = text.slice(0, w.col);
  const symbols = await symbolMap(games);
  const entry = lookupWord(ref, w.word, {
    lang, context, symbols, games: gameNames(games), user,
    opcodePosition: lang === 'mips' && /^\s*([A-Za-z_][\w?!@]*:\s*)?$/.test(before),
  });
  return { entry, w };
}

// Completion

function infoNode(entry, ref) {
  return () => {
    const div = document.createElement('div');
    div.className = 'ref-info';
    div.innerHTML = renderEntry(entry, ref, { compact: true });
    wireLinks(div);
    highlightCode(div);
    return div;
  };
}

function wireLinks(el, after) {
  el.addEventListener('mousedown', e => {
    const a = e.target.closest('.ref-link');
    if (!a) return;
    e.preventDefault();
    e.stopPropagation();
    after?.();
    openInReference(a.dataset.ref);
  });
  el.addEventListener('click', e => { if (e.target.closest('.ref-link')) e.preventDefault(); });
}

const REGISTER_NAMES = ['R0', 'AT', 'V0', 'V1', 'A0', 'A1', 'A2', 'A3', 'T0', 'T1', 'T2', 'T3', 'T4', 'T5', 'T6',
  'T7', 'T8', 'T9', 'S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'SP', 'RA', 'FP', 'GP', 'K0', 'K1'];

function symbolOptions(ref, syms, games, type = '') {
  return syms.filter(s => !type || s.type === type).map(s => {
    const known = ref.byId.has(`game:${s.name}`);
    return {
      label: s.name, type: s.type === 'code' ? 'function' : 'variable',
      detail: `${s.type} ${hex(s.addr)}`, boost: known ? 2 : 0,
      info: infoNode(symbolEntry(ref, s, games), ref),
    };
  });
}

function userOptions(ref, user) {
  return [...user.values()].map(e => ({
    label: e.name, type: e.kind === 'label' ? 'constant' : 'variable', detail: e.kind === 'label' ? 'label' : 'parameter',
    boost: 5, info: infoNode(e, ref),
  }));
}

function boardOptions(ref, context) {
  // PickBackground, DEFAULT_BG, ADDITIONAL_BG_1 to _9, ...
  return ref.entries.filter(e => e.kind === 'board' && e.contexts?.includes(context))
    .flatMap(e => (e.words.length === 1 ? [e.name] : e.words.slice(0, 9).map(w => w.toUpperCase())).map(label => ({
      label, type: 'constant', detail: 'board code', boost: 4, info: infoNode(e, ref),
    })));
}

/** Completion of the header lines: the properties, games, execution types and parameter types. */
function headerCompletion(context, before, lang) {
  const cc = lang === 'c' ? '\\/\\/+' : ';+';
  if (!new RegExp(`^\\s*${cc}`).test(before)) return null;
  if (!inHeaderRegion(context.state.doc, context.state.doc.lineAt(context.pos).number)) return null;
  const prop = new RegExp(`^\\s*${cc}\\s*([A-Za-z]*)$`).exec(before);
  if (prop && (prop[1] || context.explicit)) {
    if (prop[1] && prop[1] !== prop[1].toUpperCase()) return null;   // ordinary comment text
    const from = context.pos - prop[1].length;
    return { from, options: HEADER_PROPS.map(p => ({ label: `${p}: `, displayLabel: `${p}:`, type: 'keyword' })), validFor: /^[A-Z]*$/ };
  }
  const value = new RegExp(`^\\s*${cc}\\s*(GAMES|EXECUTION|PARAM)\\s*:\\s*(?:[\\w+\\[\\]]*,\\s*)*([\\w+\\[\\]]*)$`, 'i').exec(before);
  if (!value) return null;
  const from = context.pos - value[2].length;
  const kind = value[1].toUpperCase();
  if (kind === 'GAMES') return { from, options: GAME_NAMES.map(g => ({ label: g, type: 'enum' })), validFor: /^\w*$/ };
  if (kind === 'EXECUTION') return { from, options: [{ label: 'Direct', type: 'enum', detail: 'usually' }, { label: 'Process', type: 'enum', detail: 'advanced' }], validFor: /^\w*$/ };
  if (/\|/.test(before)) return null;
  return { from, options: Object.keys(PARAM_TYPE_IDS).map(t => ({ label: `${t}|`, displayLabel: t, type: 'type' })), validFor: /^[\w+[\]]*$/ };
}

/** Completion: the reference's words, the games' symbols, the code's own names. */
function codeCompletion(getLang, getGames, context) {
  return async cx => {
    const lang = getLang() === 1 ? 'c' : 'mips';
    const ref = await loadReference();
    const line = cx.state.doc.lineAt(cx.pos);
    const before = line.text.slice(0, cx.pos - line.from);
    const header = headerCompletion(cx, before, lang);
    if (header) return header;
    if (commentStart(before, lang) >= 0 || inString(before, before.length, lang)) return null;
    const games = getGames();
    const user = userNames(cx.state.doc, lang);
    if (lang === 'c') {
      const word = cx.matchBefore(/#?[A-Za-z_]\w*$/);
      if (!word || (word.to - word.from < 2 && !cx.explicit)) return null;
      const keywords = ref.entries.filter(e => e.category === 'C' && e.words.length).flatMap(e => e.words.map(w => ({
        label: w === 'true' || w === 'false' || w === 'null' ? w.toUpperCase() : w,
        type: e.kind === 'c-type' ? 'type' : 'keyword', detail: e.kind === 'c-type' ? 'type' : 'C', boost: 1, info: infoNode(e, ref),
      })));
      const syms = await fetchSymbols(games);
      return {
        from: word.from,
        options: [...keywords, ...userOptions(ref, user), ...boardOptions(ref, context), ...symbolOptions(ref, syms, gameNames(games))],
        validFor: /^#?\w*$/,
      };
    }
    const trimmed = before.replace(/^\s+/, '');
    if (trimmed.startsWith('.')) {
      const word = cx.matchBefore(/\.\w*$/);
      if (!word) return null;
      const options = ref.entries.filter(e => e.kind === 'directive').flatMap(e => e.words.filter(w => w.startsWith('.')).map(w => ({
        label: w.slice(1), type: 'keyword', detail: e.syntax, info: infoNode(e, ref),
      })));
      return { from: word.from + 1, options, validFor: /^\w*$/ };
    }
    const word = cx.matchBefore(/[\w$.]*$/);
    if (!word || (word.from === word.to && !cx.explicit)) return null;
    const opcodePosition = /^\s*([A-Za-z_][\w?!@]*:\s*)?[\w.]*$/.test(before);
    if (opcodePosition) {
      const options = ref.entries.filter(e => e.kind === 'instruction' || e.kind === 'pseudo').flatMap(e => e.words.map(w => ({
        label: w.toUpperCase(), type: 'keyword', detail: e.syntax?.split(' ').slice(1).join(' ') || '',
        boost: e.body ? 1 : 0, info: infoNode(e, ref),
      })));
      return { from: word.from, options, validFor: /^[\w.]*$/ };
    }
    // An operand: registers, the code's own names, board code's names, the game's symbols.
    const symWord = cx.matchBefore(/[\w$]*$/);
    const jump = /^\s*([A-Za-z_][\w?!@]*:\s*)?(j|jal)\s+/i.test(before);
    const regEntry = name => ref.byWord.get(name.toLowerCase())?.find(e => e.kind === 'register');
    const registers = jump ? [] : REGISTER_NAMES.map(r => ({
      label: r, type: 'variable', detail: 'register', boost: 3, info: regEntry(r) ? infoNode(regEntry(r), ref) : undefined,
    }));
    const syms = await fetchSymbols(games, jump ? 'code' : '');
    const funcs = jump ? [] : [{ label: 'hi', type: 'function', detail: 'hi(label)', info: infoNode(ref.byId.get('syntax:hi-lo'), ref) },
      { label: 'lo', type: 'function', detail: 'lo(label)', info: infoNode(ref.byId.get('syntax:hi-lo'), ref) }];
    return {
      from: symWord.from,
      options: [...registers, ...funcs, ...userOptions(ref, user), ...boardOptions(ref, context), ...symbolOptions(ref, syms, gameNames(games))],
      validFor: /^[\w$]*$/,
    };
  };
}

// Hover help: the reference entry of the word under the mouse, in a box beside it.

let popEl = null;
let popTimer = null;
let popKey = null;
let overPop = false;

function hidePop() {
  clearTimeout(popTimer);
  popTimer = null;
  popKey = null;
  if (popEl) popEl.hidden = true;
}

function popElement() {
  if (popEl) return popEl;
  popEl = document.createElement('div');
  popEl.className = 'code-ref-pop';
  popEl.hidden = true;
  popEl.addEventListener('mouseenter', () => { overPop = true; });
  popEl.addEventListener('mouseleave', () => { overPop = false; hidePop(); });
  wireLinks(popEl, hidePop);
  document.body.append(popEl);
  return popEl;
}

function showPop(view, entry, w, ref) {
  const el = popElement();
  el.innerHTML = renderEntry(entry, ref, { compact: true });
  highlightCode(el);
  el.hidden = false;
  const start = view.coordsAtPos(w.from);
  const end = view.coordsAtPos(w.to) || start;
  if (!start) return hidePop();
  const box = el.getBoundingClientRect();
  const margin = 8;
  let left = Math.min(start.left, window.innerWidth - box.width - margin);
  left = Math.max(margin, left);
  let top = end.bottom + 6;
  if (top + box.height > window.innerHeight - margin) top = Math.max(margin, start.top - box.height - 6);
  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
}

function hoverExtension(cm, getLang, getGames, context) {
  return [
    cm.EditorView.domEventHandlers({
      mousemove(event, view) {
        const pos = view.posAtCoords({ x: event.clientX, y: event.clientY }, true);
        const lang = getLang() === 1 ? 'c' : 'mips';
        const w = pos === null ? null : wordAt(view.state, pos, lang);
        // Over the word itself, not past the end of a line.
        const over = w && (() => {
          const a = view.coordsAtPos(w.from);
          const b = view.coordsAtPos(w.to);
          return a && b && event.clientX >= a.left - 1 && event.clientX <= b.right + 1
            && event.clientY >= a.top - 1 && event.clientY <= a.bottom + 1;
        })();
        const key = over ? `${w.from}:${w.to}` : null;
        if (key === popKey) return false;
        clearTimeout(popTimer);
        if (!key) {
          // Give the mouse time to reach the box.
          popTimer = setTimeout(() => { if (!overPop) hidePop(); }, 250);
          return false;
        }
        popTimer = setTimeout(async () => {
          popKey = key;
          const found = await entryAt(view.state, pos, lang, getGames(), context).catch(() => null);
          if (popKey !== key) return;
          if (!found?.entry) return hidePop();
          showPop(view, found.entry, found.w, await loadReference());
        }, 380);
        return false;
      },
      mouseleave() {
        clearTimeout(popTimer);
        popTimer = setTimeout(() => { if (!overPop) hidePop(); }, 250);
        return false;
      },
      keydown() { hidePop(); return false; },
      scroll() { hidePop(); return false; },
      mousedown() { hidePop(); return false; },
    }),
    cm.ViewPlugin.define(() => ({ destroy: hidePop })),
  ];
}

/** F1: the Reference page, at the word by the cursor (or a search for it). */
function referenceAtCursor(getLang, getGames, context) {
  return view => {
    const lang = getLang() === 1 ? 'c' : 'mips';
    const pos = view.state.selection.main.head;
    entryAt(view.state, pos, lang, getGames(), context).then(found => {
      if (found?.entry && !String(found.entry.id).startsWith('user:')) {
        openInReference(found.entry.id);
      } else {
        const w = wordAt(view.state, pos, lang) || (pos > 0 ? wordAt(view.state, pos - 1, lang) : null);
        openInReference(null, w?.word || '');
      }
    });
    return true;
  };
}

const STYLE = `
.code-editor { display: flex; flex: 1; min-height: 0; min-width: 0; }
.code-editor .cm-editor { flex: 1; min-width: 0; height: 100%; background: var(--bg-deep); color: var(--text); font-size: 13px; }
.code-editor .cm-editor.cm-focused { outline: none; }
.code-editor .cm-scroller { font-family: var(--mono); line-height: 1.55; }
.code-editor .cm-gutters { background: var(--bg-deep); color: var(--border-hover); border-right: 1px solid var(--panel-2); }
.code-editor .cm-activeLineGutter { background: var(--panel-deep); color: var(--muted); }
.code-editor .cm-activeLine { background: rgba(255,255,255,.03); }
.code-editor .cm-cursor { border-left-color: var(--text); }
.code-editor .cm-selectionBackground, .code-editor .cm-editor ::selection { background: rgba(var(--accent-rgb),.3) !important; }
.code-editor .cm-focused .cm-selectionBackground { background: rgba(var(--accent-rgb),.35) !important; }
.code-editor .cm-selectionMatch { background: rgba(var(--accent-rgb),.14); }
.code-editor .cm-matchingBracket { background: rgba(var(--accent-rgb),.22); color: inherit !important; outline: 1px solid rgba(var(--accent-rgb),.4); }
.code-editor .cm-foldPlaceholder { background: var(--panel-3); border: 1px solid var(--border-strong); color: var(--muted); }
.code-editor .cm-panels { background: var(--panel-deep); color: var(--text); border-color: var(--border) !important; }
.code-editor .cm-panels input, .code-editor .cm-panels button { font: 12px var(--sans); color: var(--text); background: var(--input-bg); border: 1px solid var(--border-strong); border-radius: 5px; }
.code-editor .cm-searchMatch { background: rgba(245,165,36,.35); }
.code-editor .cm-searchMatch-selected { background: rgba(245,165,36,.85); }
.code-editor .cm-tooltip { background: var(--panel-deep); border: 1px solid var(--border-strong); color: var(--text); border-radius: 6px; }
.code-editor .cm-tooltip-autocomplete ul li[aria-selected] { background: rgba(var(--accent-rgb),.3); color: #fff; }
.code-editor .cm-completionDetail { color: var(--muted); font-family: var(--mono); font-size: 11px; margin-left: 10px; font-style: normal; }
.code-editor .cm-completionInfo { max-width: 440px; font-size: 12px; padding: 0 !important; }
.code-editor .cm-completionInfo .ref-pop { padding: 10px 12px; }
.code-ref-pop {
  position: fixed; z-index: 1000; width: max-content; max-width: min(460px, calc(100vw - 16px));
  max-height: min(70vh, 520px); overflow-y: auto; background: var(--panel-deep); color: var(--text);
  border: 1px solid var(--border-strong); border-radius: 8px; box-shadow: 0 12px 32px rgba(0,0,0,.5);
  padding: 10px 12px; font-size: 12.5px;
}
.code-editor.read-only .cm-editor { background: var(--bg-deep); }
.code-editor .tok-keyword { color: #c792ea; }
.code-editor .tok-string, .code-editor .tok-character { color: #a6d189; }
.code-editor .tok-number { color: #f5a97f; }
.code-editor .tok-bool, .code-editor .tok-atom, .code-editor .tok-null { color: #ff9e64; }
.code-editor .tok-comment { color: #6f7889; font-style: italic; }
.code-editor .tok-definition, .code-editor .tok-function { color: #82aaff; }
.code-editor .tok-typeName, .code-editor .tok-className, .code-editor .tok-macroName { color: #ffcb6b; }
.code-editor .tok-propertyName { color: #89ddff; }
.code-editor .tok-operator, .code-editor .tok-punctuation { color: #9fb4cc; }
.code-editor .tok-meta { color: #c3e88d; }
.code-editor .tok-labelName { color: #f07178; }
`;

function injectStyle() {
  if (document.getElementById('pp64-code-editor-style')) return;
  const style = document.createElement('style');
  style.id = 'pp64-code-editor-style';
  style.textContent = STYLE;
  document.head.append(style);
}

/**
 * Creates an editor in parent.
 * @param {!HTMLElement} parent
 * @param {{language?: number, value?: string, readOnly?: boolean, onChange?: function(string),
 *     onCursor?: function(number, number), getGames?: function(): !Array<string>,
 *     onSave?: function(), context?: string}} opts getGames: the supported games (ids or names)
 *     whose symbols complete and explain; onSave: Ctrl+S; context: 'event', 'background' or 'music'.
 */
export async function createCodeEditor(parent, opts = {}) {
  const cm = await loadCodeMirror();
  injectStyle();
  parent.classList.add('code-editor');
  const getGames = opts.getGames || (() => []);
  const language = new cm.Compartment();
  const readOnly = new cm.Compartment();
  const completion = new cm.Compartment();
  let lang = opts.language ?? 0;
  let silent = false;

  const langExt = l => (l === 1 ? cm.languageFor('c') : cm.StreamLanguage.define(mipsMode));
  const context = opts.context || 'event';
  const getLang = () => lang;
  const completeExt = () => cm.autocompletion({
    override: [codeCompletion(getLang, getGames, context)],
    activateOnTyping: true,
  });
  const roExt = ro => [cm.EditorState.readOnly.of(!!ro), cm.EditorView.editable.of(!ro)];
  const indent = l => cm.indentUnit.of(l === 1 ? '    ' : '  ');

  const view = new cm.EditorView({
    parent,
    state: cm.EditorState.create({
      doc: opts.value || '',
      extensions: [
        cm.lineNumbers(), cm.highlightActiveLineGutter(), cm.highlightSpecialChars(), cm.history(),
        cm.foldGutter(), cm.drawSelection(), cm.dropCursor(), cm.indentOnInput(),
        cm.syntaxHighlighting(cm.classHighlighter), cm.bracketMatching(), cm.closeBrackets(),
        cm.rectangularSelection(), cm.highlightActiveLine(), cm.highlightSelectionMatches(),
        cm.search({ top: true }), cm.EditorState.tabSize.of(4),
        cm.keymap.of([
          { key: 'Mod-s', run: () => { opts.onSave?.(); return true; }, preventDefault: true },
          { key: 'F1', run: referenceAtCursor(getLang, getGames, context), preventDefault: true },
          ...cm.closeBracketsKeymap, ...cm.defaultKeymap, ...cm.searchKeymap, ...cm.historyKeymap,
          ...cm.foldKeymap, ...cm.completionKeymap, cm.indentWithTab,
        ]),
        language.of([langExt(lang), indent(lang)]),
        completion.of(completeExt()),
        hoverExtension(cm, getLang, getGames, context),
        readOnly.of(roExt(opts.readOnly)),
        cm.EditorView.updateListener.of(u => {
          if (u.docChanged && !silent) opts.onChange?.(u.state.doc.toString());
          if (u.selectionSet || u.docChanged) {
            const pos = u.state.selection.main.head;
            const ln = u.state.doc.lineAt(pos);
            opts.onCursor?.(ln.number, pos - ln.from + 1);
          }
        }),
        cm.EditorView.theme({}, { dark: true }),
      ],
    }),
  });
  parent.classList.toggle('read-only', !!opts.readOnly);

  return {
    view,
    getValue: () => view.state.doc.toString(),
    /** Replaces the text (without calling onChange), keeping the cursor where it can. */
    setValue(text) {
      const cur = view.state.doc.toString();
      if (cur === text) return;
      const head = Math.min(view.state.selection.main.head, text.length);
      silent = true;
      try {
        view.dispatch({ changes: { from: 0, to: cur.length, insert: text }, selection: { anchor: head } });
      } finally {
        silent = false;
      }
    },
    setLanguage(l) {
      lang = l;
      view.dispatch({ effects: [language.reconfigure([langExt(l), indent(l)]), completion.reconfigure(completeExt())] });
    },
    setReadOnly(ro) {
      view.dispatch({ effects: readOnly.reconfigure(roExt(ro)) });
      parent.classList.toggle('read-only', !!ro);
    },
    focus: () => view.focus(),
    destroy: () => { hidePop(); view.destroy(); },
  };
}
