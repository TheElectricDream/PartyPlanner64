// A CodeMirror 6 editor for event code: MIPS assembly (with the game's symbols completed) or C.
// Ports apps/partyplanner64/utils/lib/mp-mips-codemirror.ts (the "mips-pp64" mode) and
// mp-mips-autocomplete.ts (completion from GET /api/symbols), and components/codemirrorwrapper.tsx.
//
//   const ed = await createCodeEditor(parent, { language: 0, value, onChange, getGames, onSave });
//   ed.getValue(); ed.setValue(text); ed.setLanguage(1); ed.setReadOnly(true); ed.destroy();
//
// language: 0 MIPS assembly, 1 C (EventCodeLanguage). The editor styles itself (dark).

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

// mp-mips-autocomplete.ts ("org" and "orga" are left out: they would break events)
const DIRECTIVES = ['ascii', 'asciiz', 'align', 'byte', 'definelabel', 'else', 'elseif', 'endif',
  'fill', 'float', 'halfword', 'if', 'skip', 'word'];

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

// The game's symbols, by the games and type asked for.
const symbolCache = new Map();

/** Symbols every one of the games has (GET /api/symbols), cached. */
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

const hex = n => '0x' + (n >>> 0).toString(16).toUpperCase().padStart(8, '0');
const symOption = s => ({
  label: s.name, type: s.type === 'code' ? 'function' : 'variable',
  detail: `${s.type} ${hex(s.addr)}`, info: s.desc || undefined,
});

/** Completion for MIPS: directives after ".", opcodes, and symbols after an opcode. */
function mipsCompletion(getGames) {
  return async context => {
    const line = context.state.doc.lineAt(context.pos);
    const before = line.text.slice(0, context.pos - line.from).replace(/^\s+/, '');
    if (before.startsWith('.')) {
      const word = context.matchBefore(/\.\w*$/);
      if (!word) return null;
      return { from: word.from + 1, options: DIRECTIVES.map(d => ({ label: d, type: 'keyword' })), validFor: /^\w*$/ };
    }
    if (/^[;/]/.test(before)) return null;
    const word = context.matchBefore(/[\w$.]*$/);
    if (!word || (word.from === word.to && !context.explicit)) return null;
    if (!/\s/.test(before)) {
      // The opcode.
      return { from: word.from, options: OPCODES.map(o => ({ label: o.toUpperCase(), type: 'keyword' })), validFor: /^[\w.]*$/ };
    }
    // From the last "(" (hi(sym), lo(sym)).
    const symWord = context.matchBefore(/[\w$]*$/);
    const type = /^(j|jal)\s+/i.test(before) ? 'code' : '';
    const syms = await fetchSymbols(getGames(), type);
    if (!syms.length) return null;
    return { from: symWord.from, options: syms.map(symOption), validFor: /^[\w$]*$/ };
  };
}

/** Completion for C: the game's symbols (functions and data). */
function cCompletion(getGames) {
  return async context => {
    const word = context.matchBefore(/[A-Za-z_]\w*$/);
    if (!word || (word.to - word.from < 2 && !context.explicit)) return null;
    const syms = await fetchSymbols(getGames(), '');
    if (!syms.length) return null;
    return { from: word.from, options: syms.map(symOption), validFor: /^\w*$/ };
  };
}

const STYLE = `
.code-editor { display: flex; flex: 1; min-height: 0; min-width: 0; }
.code-editor .cm-editor { flex: 1; min-width: 0; height: 100%; background: #0d1016; color: #d4d9e2; font-size: 13px; }
.code-editor .cm-editor.cm-focused { outline: none; }
.code-editor .cm-scroller { font-family: var(--mono); line-height: 1.55; }
.code-editor .cm-gutters { background: #0b0e13; color: #4b5363; border-right: 1px solid #1a1e26; }
.code-editor .cm-activeLineGutter { background: #141924; color: #aeb6c3; }
.code-editor .cm-activeLine { background: rgba(255,255,255,.03); }
.code-editor .cm-cursor { border-left-color: #e6e9ef; }
.code-editor .cm-selectionBackground, .code-editor .cm-editor ::selection { background: rgba(76,141,255,.3) !important; }
.code-editor .cm-focused .cm-selectionBackground { background: rgba(76,141,255,.35) !important; }
.code-editor .cm-selectionMatch { background: rgba(130,170,255,.14); }
.code-editor .cm-matchingBracket { background: rgba(130,170,255,.22); color: inherit !important; outline: 1px solid rgba(130,170,255,.4); }
.code-editor .cm-foldPlaceholder { background: #1f2530; border: 1px solid #2e3542; color: var(--muted); }
.code-editor .cm-panels { background: #10141a; color: var(--text); border-color: var(--border) !important; }
.code-editor .cm-panels input, .code-editor .cm-panels button { font: 12px var(--sans); color: var(--text); background: #0e1117; border: 1px solid var(--border-strong); border-radius: 5px; }
.code-editor .cm-searchMatch { background: rgba(245,165,36,.35); }
.code-editor .cm-searchMatch-selected { background: rgba(245,165,36,.85); }
.code-editor .cm-tooltip { background: #161a22; border: 1px solid var(--border-strong); color: var(--text); border-radius: 6px; }
.code-editor .cm-tooltip-autocomplete ul li[aria-selected] { background: rgba(76,141,255,.3); color: #fff; }
.code-editor .cm-completionDetail { color: var(--muted); font-family: var(--mono); font-size: 11px; margin-left: 10px; font-style: normal; }
.code-editor .cm-completionInfo { max-width: 360px; font-size: 12px; }
.code-editor.read-only .cm-editor { background: #0b0d12; }
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
 *     onSave?: function()}} opts getGames: the supported games (ids or names) whose symbols
 *     complete; onSave: Ctrl+S.
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
  const completeExt = l => cm.autocompletion({
    override: [l === 1 ? cCompletion(getGames) : mipsCompletion(getGames)],
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
          ...cm.closeBracketsKeymap, ...cm.defaultKeymap, ...cm.searchKeymap, ...cm.historyKeymap,
          ...cm.foldKeymap, ...cm.completionKeymap, cm.indentWithTab,
        ]),
        language.of([langExt(lang), indent(lang)]),
        completion.of(completeExt(lang)),
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
      view.dispatch({ effects: [language.reconfigure([langExt(l), indent(l)]), completion.reconfigure(completeExt(l))] });
    },
    setReadOnly(ro) {
      view.dispatch({ effects: readOnly.reconfigure(roExt(ro)) });
      parent.classList.toggle('read-only', !!ro);
    },
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
