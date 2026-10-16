// The Boards card (boardmenu.tsx, newboard.tsx and the board actions of header.tsx): your boards
// and the ROM's, new, import, export, copy, delete, and Overwrite to ROM with validation.
import { $, $$, api, esc, toast, act, busy, dialog, confirmDialog, pickFile, download } from '../api.js';
import { IMG, BoardType, GameNames } from './constants.js';
import { store } from './store.js';
import { plainText } from './board.js';

/** Escapes a validation message, keeping its links and line breaks (they were HTML). */
export function messageHtml(text) {
  return esc(text)
    .replace(/&lt;a href=&quot;(https?:\/\/[^&"]+)&quot;[^&]*?&gt;(.*?)&lt;\/a&gt;/g,
      '<a href="$1" target="_blank" rel="noopener">$2</a>')
    .replace(/&lt;br\s*\/?&gt;/g, '<br>');
}

/** Copies the current board; makeCurrent: switch to the copy (Copy to Edit). */
export async function copyCurrentBoard(app, makeCurrent = false) {
  const cur = { ...(app.state?.boards?.current || { index: 0, rom: false }) };
  const countBefore = (app.state?.boards?.list || []).length;
  await act(async () => {
    const res = await api('/api/boards/copy', { index: cur.index, rom: !!cur.rom, makeCurrent });
    await app.refresh();
    if (makeCurrent) {
      // The copy goes after the board, or at the end for a ROM board (copyCurrentBoardAction).
      const index = typeof res?.index === 'number' ? res.index : (cur.rom ? countBefore : cur.index + 1);
      const now = app.state.boards.current;
      if (now.index !== index || now.rom) await store.setCurrent(index, false);
      else await store.load();
      store.clearSelection();
    }
    toast(makeCurrent ? 'Copied the board: you are now editing the copy.' : 'Copied the board.', 'success');
  });
}

export class BoardsCard {
  constructor(card, app) {
    this.card = card;
    this.app = app;
    this.list = $('.board-list', card);
    this.foot = $('.board-actions', card);
    $('[data-new]', card).addEventListener('click', () => this.newBoard());
    $('[data-import]', card).addEventListener('click', () => this.importBoard());
    $('[data-export]', card).addEventListener('click', () => this.exportBoard());
    $('[data-copy]', card).addEventListener('click', () => this.copyBoard());
    $('[data-delete]', card).addEventListener('click', () => this.deleteBoard());
    $('[data-overwrite]', card).addEventListener('click', () => this.overwrite());
    app.on('state', () => this.render());
    store.on('board', () => this.render());
    this.render();
  }

  get boards() {
    return this.app.state?.boards || { list: [], romList: [], current: { index: 0, rom: false } };
  }

  render() {
    const b = this.boards;
    const cur = b.current || { index: 0, rom: false };
    const showRom = !!this.app.setting('ui.showromboards') || cur.rom;
    const item = (s, rom) => {
      const active = cur.index === s.index && !!cur.rom === rom;
      const name = plainText(s.name) || 'Untitled';
      return `<li class="${active ? 'active' : ''}" data-index="${s.index}" data-rom="${rom ? 1 : 0}" role="option"
          aria-selected="${active}" title="Open “${esc(name)}” (${GameNames[s.game] || 'MP' + s.game}${s.type === BoardType.DUEL ? ', duel board' : ''}, ${s.spaceCount ?? '?'} spaces)${rom ? '. Loaded from the ROM: read-only.' : ''}">
        ${rom ? `<img src="${IMG}/boardmenu/cart.png" class="rom-icon" alt="ROM">` : ''}
        <span class="board-item-name">${esc(name)}</span>
        <span class="board-item-meta">MP${s.game}${s.type === BoardType.DUEL ? ' Duel' : ''}</span></li>`;
    };
    let html = (b.list || []).map(s => item(s, false)).join('');
    if (!html) html = '<li class="empty">No boards yet: create one.</li>';
    const romList = b.romList || [];
    if (showRom && romList.length) {
      html += `<li class="list-sep" aria-hidden="true">ROM Boards</li>` + romList.map(s => item(s, true)).join('');
    }
    this.list.innerHTML = html;
    for (const li of $$('li[data-index]', this.list)) {
      li.addEventListener('click', () => {
        const index = +li.dataset.index;
        const rom = li.dataset.rom === '1';
        if (index === cur.index && rom === !!cur.rom) return;
        act(() => store.setCurrent(index, rom));
      });
      li.addEventListener('contextmenu', e => {
        e.preventDefault();
        const index = +li.dataset.index;
        const rom = li.dataset.rom === '1';
        act(async () => {
          if (index !== cur.index || rom !== !!cur.rom) await store.setCurrent(index, rom);
          this.boardMenu(e.clientX, e.clientY);
        });
      });
    }
    const active = $('li.active', this.list);
    if (active) active.scrollIntoView({ block: 'nearest' });
    // Actions on the current board.
    const romOpen = !!this.app.state?.rom;
    $('[data-delete]', this.card).disabled = !!cur.rom;
    $('[data-overwrite]', this.card).hidden = !romOpen || !!cur.rom;
    const count = $('.board-count', this.card);
    count.textContent = `${(b.list || []).length}`;
    count.title = `${(b.list || []).length} board${(b.list || []).length === 1 ? '' : 's'} of your own${romList.length ? `, ${romList.length} in the ROM` : ''}`;
  }

  /** The Copy/Delete menu of a board (right-click), like the original's. */
  boardMenu(x, y) {
    document.querySelector('.ctx-menu')?.remove();
    const cur = this.boards.current;
    const menu = document.createElement('div');
    menu.className = 'ctx-menu';
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.innerHTML = `<button type="button" data-a="copy" title="Make a copy of this board">Copy</button>
      <button type="button" data-a="export" title="Download this board as a .json file">Export</button>
      ${cur.rom ? '' : '<button type="button" data-a="delete" class="danger" title="Delete this board">Delete</button>'}`;
    document.body.append(menu);
    const close = () => menu.remove();
    menu.addEventListener('click', e => {
      const a = e.target.dataset.a;
      close();
      if (a === 'copy') this.copyBoard();
      else if (a === 'export') this.exportBoard();
      else if (a === 'delete') this.deleteBoard();
    });
    setTimeout(() => document.addEventListener('pointerdown', ev => { if (!menu.contains(ev.target)) close(); }, { once: true }), 0);
  }

  async newBoard() {
    const debug = !!this.app.setting('ui.debug');
    let game = 1;
    let type = BoardType.NORMAL;
    const r = await dialog({
      title: 'New Board',
      body: `<label class="field"><span class="field-label">Game</span>
          <div class="segmented" data-game role="group" aria-label="Game">
            <button type="button" data-v="1" class="active" title="Mario Party 1">MP1</button>
            <button type="button" data-v="2" title="Mario Party 2">MP2</button>
            <button type="button" data-v="3" title="Mario Party 3">MP3</button></div></label>
        <label class="field" data-type-field hidden><span class="field-label tip" title="Duel board support is partially finished (debug mode only)">Board Type</span>
          <div class="segmented" data-type role="group" aria-label="Board type">
            <button type="button" data-v="NORMAL" class="active" title="A normal party board">Normal</button>
            <button type="button" data-v="DUEL" title="A duel board (partially supported)">Duel</button></div></label>
        <div class="field"><span class="field-label">Theme</span>
          <div class="theme-pick"><button type="button" class="theme-card active" title="A blank board with the default images">
            <img src="${IMG}/themes/default/preview.png" alt="" width="96" height="72"><span>Blank</span></button></div></div>
        <p class="hint">The board starts with a start space and the theme's background and images; change them on the Details page.</p>`,
      buttons: [{ label: 'Cancel', value: false }, { label: 'Create', value: true, kind: 'primary' }],
      onOpen: el => {
        const typeField = $('[data-type-field]', el);
        for (const btn of $$('[data-game] button', el)) {
          btn.addEventListener('click', () => {
            $$('[data-game] button', el).forEach(b => b.classList.toggle('active', b === btn));
            game = +btn.dataset.v;
            typeField.hidden = !(game === 3 && debug);
            if (game !== 3) type = BoardType.NORMAL;
          });
        }
        for (const btn of $$('[data-type] button', el)) {
          btn.addEventListener('click', () => {
            $$('[data-type] button', el).forEach(b => b.classList.toggle('active', b === btn));
            type = btn.dataset.v;
          });
        }
      },
    });
    if (r !== true) return;
    await act(async () => {
      await api('/api/boards/new', { game, type, theme: 'default' });
      await this.app.refresh();
      await store.load();
      store.clearSelection();
      toast(`Created a new ${GameNames[game]} board.`, 'success');
    });
  }

  async importBoard() {
    const file = await pickFile('.json,application/json');
    if (!file) return;
    await busy(`Importing ${file.name}…`, async () => {
      await api('/api/boards/import', file);
      await this.app.refresh();
      await store.load();
      store.clearSelection();
      toast(`Imported ${file.name}.`, 'success');
    });
  }

  async exportBoard() {
    const cur = this.boards.current;
    await act(async () => {
      const name = await download(`/api/boards/${cur.index}/export${cur.rom ? '?rom=1' : ''}`, undefined,
        `${plainText(store.board?.name) || 'board'}.json`);
      toast(`Saved ${name}.`, 'success');
    });
  }

  /** Copies the current board; makeCurrent: switch to the copy (Copy to Edit). */
  copyBoard(makeCurrent = false) {
    return copyCurrentBoard(this.app, makeCurrent);
  }

  async deleteBoard() {
    const cur = this.boards.current;
    if (cur.rom) return;
    const name = plainText(store.board?.name) || 'this board';
    if (!await confirmDialog(`Delete “${name}”? This cannot be undone (export it first to keep a copy).`,
      { title: 'Delete Board', yes: 'Delete', danger: true })) return;
    await act(async () => {
      await api('/api/boards/delete', { index: cur.index });
      await this.app.refresh();
      await store.load();
      store.clearSelection();
      toast(`Deleted ${name}.`, 'success');
    });
  }

  /** Overwrite to ROM: validates the board against each ROM board and writes it over one. */
  async overwrite() {
    const skip = !!this.app.setting('ui.skipvalidation');
    let chosen = null;
    const body = document.createElement('div');
    body.innerHTML = `<p class="hint">Write the current board over one of the ROM's boards. It is checked against each first${skip ? ' (Skip Overwrite Validation is on in Settings: problems do not block it)' : ''}; boards with errors cannot be overwritten. Save the ROM afterwards to keep the change.</p>
      <div class="overwrite-general"></div>
      <ul class="overwrite-list"><li class="empty">Checking the board…</li></ul>`;
    const msgs = (errors, warnings) => errors.map(m => ['err', m]).concat(warnings.map(m => ['warn', m]))
      .map(([k, m]) => `<div class="ow-msg ${k}"><img src="${IMG}/header/${k === 'err' ? 'boarderror' : 'boardwarning'}.png" alt="">
        <span>${messageHtml(m)}</span></div>`).join('');
    const run = async () => {
      const list = $('.overwrite-list', body);
      let res;
      try {
        res = await api('/api/board/validate');
      } catch (e) {
        list.innerHTML = `<li><div class="notice err">${esc(e.message)}</div></li>`;
        return;
      }
      // General issues (not specific to a ROM board).
      $('.overwrite-general', body).innerHTML = msgs(res.general?.errors || [], res.general?.warnings || []);
      const boards = res.boards || [];
      if (!boards.length) {
        list.innerHTML = '<li class="empty">The ROM has no boards that can be overwritten.</li>';
        return;
      }
      list.innerHTML = boards.map(rb => {
        const errors = rb.errors.length;
        const warnings = rb.warnings.length;
        const blocked = rb.unavailable || rb.forcedDisabled || errors;
        const pill = rb.unavailable ? ['err', 'Unavailable'] : rb.forcedDisabled ? ['err', 'Blocked']
          : errors ? ['err', `${errors} Error${errors === 1 ? '' : 's'}`]
            : warnings ? ['warn', `${warnings} Warning${warnings === 1 ? '' : 's'}`] : ['ok', 'OK'];
        const note = rb.unavailable ? '<div class="ow-msg err"><span>Board cannot be overwritten currently.</span></div>'
          : rb.forcedDisabled ? '<div class="ow-msg err"><span>Current issues must be resolved.</span></div>' : '';
        const name = plainText(rb.name) || `Board ${rb.index}`;
        return `<li data-i="${rb.index}"><div class="ow-head"><span class="ow-name">${esc(name)}</span>
          <span class="pill ${pill[0]}">${pill[1]}</span>
          <button type="button" class="btn btn-sm btn-primary" data-ow ${blocked ? 'disabled' : ''}
            title="${blocked ? 'Fix the problems listed to overwrite this board' : `Overwrite ${esc(name)} with the current board`}">Overwrite</button></div>
          <div class="ow-msgs">${note}${msgs(rb.errors, rb.warnings)}</div></li>`;
      }).join('');
      for (const btn of $$('[data-ow]', list)) {
        btn.addEventListener('click', () => {
          chosen = +btn.closest('li').dataset.i;
          $('#appDialog').close();
        });
      }
    };
    const shown = dialog({ title: 'Overwrite to ROM', body, wide: true, buttons: [{ label: 'Close', value: false }] });
    run();
    await shown;
    if (chosen === null) return;
    const romName = plainText((this.boards.romList || []).find(s => s.index === chosen)?.name) || 'the ROM board';
    await busy('Writing the board into the ROM…', async () => {
      await api('/api/rom/overwrite', { romBoardIndex: chosen });
      await this.app.refresh();
      await store.load();
      toast(`Overwrote ${romName}. Save the ROM to keep it.`, 'success');
      store.addLog(`Overwrote ROM board ${chosen} (${romName})`);
    });
  }
}
