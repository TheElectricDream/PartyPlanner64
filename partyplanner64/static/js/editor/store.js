// The current board as the Editor and Details pages see it, and the editor's own UI state
// (selection, tool, highlights). The server holds the board and its undo history: every edit is
// an op (POST /api/board/op or /ops) and the answer carries the new board.
import { api, toast } from '../api.js';
import { Action } from './constants.js';

const listeners = new Map();

function emit(kind, data) {
  for (const fn of listeners.get(kind) || []) {
    try {
      fn(data);
    } catch (e) {
      console.error(e);
    }
  }
}

let queue = Promise.resolve();
let pending = 0;
let inited = false;
let reloadTimer = null;

export const store = {
  app: null,
  /** The current board (JSON; images are /api/image/<sha1> URLs), or null before loading. */
  board: null,
  index: 0,
  rom: false,
  revision: -1,
  canUndo: false,
  canRedo: false,
  /** Selected space indices (in order of selection). */
  selected: [],
  action: Action.MOVE,
  /** The event library: { id: event } (GET /api/events). */
  library: {},
  libraryLoaded: false,
  /** A background shown instead of the board's (animation frames, additional backgrounds). */
  overrideBg: null,
  /** Spaces shown with a red highlight (dead ends, find space), or null. */
  highlighted: null,
  /** The board event the pointer is over in the board events list (its spaces are highlighted). */
  hoveredBoardEvent: -1,
  /** Temporary lines while linking: [[x1, y1, x2, y2], ...] or null. */
  tempConnections: null,
  /** Selection box [xs, ys, xf, yf] or null. */
  selectionBox: null,
  /** Lines of the console's Log tab. */
  log: [],

  /** Calls fn(data) on: board, selection, action, highlight, library, overridebg, log. */
  on(kind, fn) {
    if (!listeners.has(kind)) listeners.set(kind, new Set());
    listeners.get(kind).add(fn);
    return () => listeners.get(kind).delete(fn);
  },
  emit,

  /** Hooks the store to the app's server events (once). */
  init(app) {
    this.app = app;
    if (inited) return;
    inited = true;
    app.on('board', data => {
      if (!data || data.revision !== this.revision) this.scheduleReload();
    });
    app.on('boards', () => {
      app.refresh().catch(() => {});
      this.scheduleReload();
    });
    app.on('rom', () => this.scheduleReload());
    app.on('events', () => this.loadLibrary());
    app.on('settings', () => emit('board', this.board));
  },

  scheduleReload() {
    clearTimeout(reloadTimer);
    reloadTimer = setTimeout(() => {
      if (pending) {
        this.scheduleReload();
        return;
      }
      this.load().catch(e => console.error(e));
    }, 60);
  },

  /** Loads the current board (GET /api/board). */
  async load() {
    const res = await api('/api/board');
    const changedBoard = res.index !== this.index || !!res.rom !== this.rom || !this.board;
    this.apply(res);
    if (changedBoard) this.clearSelection();
    return res;
  },

  async loadLibrary() {
    try {
      const res = await api('/api/events');
      const lib = {};
      for (const e of res.events || []) lib[e.id] = e;
      this.library = lib;
      this.libraryLoaded = true;
      emit('library', lib);
      emit('board', this.board);
    } catch (e) {
      console.error(e);
    }
  },

  apply(res) {
    if (!res) return;
    if ('index' in res) this.index = res.index;
    if ('rom' in res) this.rom = !!res.rom;
    if ('revision' in res) this.revision = res.revision;
    if ('canUndo' in res) this.canUndo = !!res.canUndo;
    if ('canRedo' in res) this.canRedo = !!res.canRedo;
    if (res.board) {
      this.board = res.board;
      // Drop selected spaces that no longer exist.
      const n = this.board.spaces.length;
      const sel = this.selected.filter(i => i < n && this.board.spaces[i]);
      if (sel.length !== this.selected.length) this.setSelection(sel);
      emit('board', this.board);
    }
  },

  /** True if the current board is one of the ROM's (read-only). */
  get readonly() {
    return this.rom || !!this.board?._rom;
  },

  /**
   * Applies an edit (a reducer of boardState.ts without "Action"), as one undo step.
   * Edits run one after another, in order.
   */
  op(op, args = {}, label) {
    return this.ops([{ op, args }], label);
  },

  /** Applies several edits as one undo step. */
  ops(list, label) {
    if (!list.length) return Promise.resolve(null);
    if (this.readonly) {
      toast('This board is from the ROM and cannot be edited. Copy it to make changes.', 'warn');
      return Promise.resolve(null);
    }
    pending++;
    const run = async () => {
      try {
        const res = list.length === 1
          ? await api('/api/board/op', list[0])
          : await api('/api/board/ops', { ops: list });
        this.apply(res);
        this.addLog(label || list.map(o => o.op).join(', '));
        return res;
      } catch (e) {
        console.error(e);
        toast(e.message, 'error', 9000);
        this.addLog(`${list.map(o => o.op).join(', ')} failed: ${e.message}`, 'err');
        // Resync with the server's board.
        this.scheduleReload();
        return null;
      } finally {
        pending--;
      }
    };
    queue = queue.then(run, run);
    return queue;
  },

  async undo() {
    if (!this.canUndo || this.readonly) return;
    await this._history('undo');
  },

  async redo() {
    if (!this.canRedo || this.readonly) return;
    await this._history('redo');
  },

  _history(which) {
    pending++;
    const run = async () => {
      try {
        const res = await api(`/api/board/${which}`, {});
        this.apply(res);
        this.addLog(which === 'undo' ? 'Undo' : 'Redo');
      } catch (e) {
        toast(e.message, 'error');
      } finally {
        pending--;
      }
    };
    queue = queue.then(run, run);
    return queue;
  },

  /** Makes another board current (POST /api/boards/current). */
  async setCurrent(index, rom) {
    const res = await api('/api/boards/current', { index, rom: !!rom });
    this.clearSelection();
    this.overrideBg = null;
    this.highlighted = null;
    await this.app.refresh();
    if (res && res.board) {
      this.apply(res);
    } else {
      await this.load();
    }
  },

  // Selection

  setSelection(indices) {
    this.selected = [...new Set(indices)].filter(i => i >= 0);
    emit('selection', this.selected);
  },
  clearSelection() {
    if (!this.selected.length) return;
    this.setSelection([]);
  },
  addSelected(index) {
    if (!this.selected.includes(index)) this.setSelection([...this.selected, index]);
  },
  isSelected(index) {
    return this.selected.includes(index);
  },
  /** The selected spaces that exist, as [index, space] pairs. */
  selectedSpaces() {
    if (!this.board) return [];
    return this.selected.filter(i => this.board.spaces[i]).map(i => [i, this.board.spaces[i]]);
  },

  setAction(action) {
    if (this.action === action) return;
    this.action = action;
    emit('action', action);
  },

  setHighlighted(indices) {
    this.highlighted = indices && indices.length ? indices : null;
    emit('highlight');
  },

  setHoveredBoardEvent(index) {
    this.hoveredBoardEvent = index;
    emit('highlight');
  },

  setOverrideBg(src) {
    this.overrideBg = src || null;
    emit('overridebg', this.overrideBg);
  },

  addLog(text, kind = '') {
    const t = new Date();
    const stamp = t.toTimeString().slice(0, 8);
    this.log.push({ stamp, text, kind });
    if (this.log.length > 500) this.log.splice(0, this.log.length - 500);
    emit('log', this.log);
  },
};
