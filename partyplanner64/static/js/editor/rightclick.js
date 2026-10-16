// The quick menu of a space (port of rightclick.tsx): its coordinates and type, next to it on
// the board. Opened by right-clicking (or double-clicking) a space.
import { esc } from '../api.js';
import { Space, getTypeToggles, getSubtypeToggles } from './constants.js';
import { store } from './store.js';

export class RightClickMenu {
  /** host: the element positioned over the board; place(x, y) -> [left, top] in host pixels. */
  constructor(host, place, app) {
    this.host = host;
    this.place = place;
    this.app = app;
    this.index = -1;
    this.el = document.createElement('div');
    this.el.className = 'rc-menu';
    this.el.hidden = true;
    host.append(this.el);
    this.el.addEventListener('contextmenu', e => e.preventDefault()); // No right click on right click menu.
    this.el.addEventListener('pointerdown', e => e.stopPropagation());
    document.addEventListener('pointerdown', e => {
      // Clicks outside close the menu; the board's own handlers decide for clicks on it.
      if (this.isOpen() && !this.el.contains(e.target) && e.target.tagName !== 'CANVAS') this.close();
    });
  }

  isOpen() {
    return this.index >= 0;
  }

  open(index) {
    this.index = index;
    this.render();
  }

  update(index) {
    if (index < 0) this.close(); else this.open(index);
  }

  close() {
    this.index = -1;
    this.el.hidden = true;
    this.el.innerHTML = '';
  }

  /** Moves the menu with its space (while dragging) without rebuilding it. */
  reposition() {
    const space = store.board?.spaces[this.index];
    if (!space) return;
    let [left, top] = this.place(space.x - 8, space.y + 15);
    // Keep the menu in the visible part of the view: above the space if there is no room below.
    const scroller = this.host.closest('.board-scroll');
    if (scroller) {
      const host = this.host.getBoundingClientRect();
      const view = scroller.getBoundingClientRect();
      const h = this.el.offsetHeight;
      const w = this.el.offsetWidth;
      if (host.top + top + h > view.bottom - 8) {
        const [, above] = this.place(space.x, space.y - 18);
        top = above - h;
      }
      if (host.left + left + w > view.right - 8) left = Math.max(view.right - 8 - w - host.left, -host.left + view.left + 8);
    }
    this.el.style.transform = `translate(${left}px, ${top}px)`;
    const [xIn, yIn] = this.el.querySelectorAll('input');
    if (xIn && document.activeElement !== xIn) xIn.value = space.x;
    if (yIn && document.activeElement !== yIn) yIn.value = space.y;
  }

  render() {
    const board = store.board;
    const space = board?.spaces[this.index];
    if (!space) {
      this.close();
      return;
    }
    const ro = store.readonly;
    const advanced = !!this.app.setting('ui.advanced');
    const toggles = (items, isSub) => items.map(item => {
      const selected = isSub
        ? space.subtype !== undefined && space.subtype === item.subtype
        : space.type === item.type;
      return `<button type="button" class="type-btn${selected ? ' active' : ''}${isSub ? ' sub' : ''}"
        data-type="${item.type ?? ''}" data-subtype="${item.subtype ?? ''}" title="${esc(item.name)}"
        ${ro ? 'disabled' : ''}><img src="${item.icon}" alt=""></button>`;
    }).join('');
    // Can't switch start space type (unless advanced).
    const showTypes = !(space.type === Space.START && !advanced);
    const subs = getSubtypeToggles(board.game, board.type);
    this.el.innerHTML = `
      <div class="rc-head"><span class="rc-title">Space ${this.index}</span>
        <button type="button" class="btn btn-ghost btn-sm btn-icon" data-close title="Close this menu (Esc)">✕</button></div>
      <div class="rc-coords">
        <label title="The space's X coordinate, in pixels from the left of the background">X <input class="input mono" type="number" min="0" max="${board.bg.width}" value="${space.x}" ${ro ? 'disabled' : ''}></label>
        <label title="The space's Y coordinate, in pixels from the top of the background">Y <input class="input mono" type="number" min="0" max="${board.bg.height}" value="${space.y}" ${ro ? 'disabled' : ''}></label>
      </div>
      ${showTypes ? `<div class="type-grid">${toggles(getTypeToggles(board.game, board.type, advanced), false)}</div>` : ''}
      ${showTypes && subs.length ? `<div class="type-grid subs">${toggles(subs, true)}</div>` : ''}`;
    this.el.hidden = false;
    this.reposition();

    this.el.querySelector('[data-close]').addEventListener('click', () => this.close());
    const [xIn, yIn] = this.el.querySelectorAll('input');
    const commit = () => {
      const x = parseInt(xIn.value, 10);
      const y = parseInt(yIn.value, 10);
      const sp = store.board.spaces[this.index];
      if (!sp || isNaN(x) || isNaN(y)) return;
      if (x < 0 || x > store.board.bg.width || y < 0 || y > store.board.bg.height) return;
      if (x === sp.x && y === sp.y) return;
      store.op('setSpacePositions', { spaceIndices: [this.index], coords: [{ x, y }] }, `Move space ${this.index}`);
    };
    for (const input of [xIn, yIn]) {
      input.addEventListener('change', commit);
      input.addEventListener('keyup', e => { if (e.key === 'Enter') commit(); });
    }
    for (const btn of this.el.querySelectorAll('.type-btn')) {
      btn.addEventListener('click', () => {
        const isSub = btn.classList.contains('sub');
        const args = { spaceIndices: store.selected.length ? store.selected.filter(i => store.board.spaces[i]) : [this.index] };
        if (!isSub) {
          args.type = Number(btn.dataset.type);
        } else if (!btn.classList.contains('active')) {
          args.subtype = Number(btn.dataset.subtype);
        }
        // As the original: changing the type clears the subtype; a subtype keeps the type.
        store.op('setSpaceType', args, isSub ? 'Change character' : 'Change space type');
      });
    }
  }
}
