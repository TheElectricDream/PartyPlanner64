// Mouse, touch and keyboard editing of the board (port of interaction.tsx).
// Every edit goes to the server as an op; while dragging, spaces move locally and the new
// positions are sent when the pointer is released.
import { Action, Space, SpaceSubtype } from './constants.js';
import { store } from './store.js';
import { getSpacesOfType, lineAt, pointFallsWithin, determineAngle } from './board.js';

let eventParamDropHandler = null;

/** The handler for an event parameter being dragged to a space (utils/drag.ts). */
export function setEventParamDropHandler(fn) {
  eventParamDropHandler = fn;
}

const ADD_ACTIONS = new Set([
  Action.ADD_OTHER, Action.ADD_BLUE, Action.ADD_RED, Action.ADD_MINIGAME, Action.ADD_HAPPENING,
  Action.ADD_STAR, Action.ADD_BLACKSTAR, Action.ADD_START, Action.ADD_CHANCE, Action.ADD_SHROOM,
  Action.ADD_BOWSER, Action.ADD_ITEM, Action.ADD_BATTLE, Action.ADD_BANK, Action.ADD_GAMEGUY,
  Action.ADD_ARROW, Action.ADD_DUEL_BASIC, Action.ADD_DUEL_REVERSE, Action.ADD_DUEL_POWERUP,
  Action.ADD_DUEL_START_BLUE, Action.ADD_DUEL_START_RED,
]);
const SUBTYPE_ACTIONS = new Set([
  Action.MARK_GATE, Action.ADD_TOAD_CHARACTER, Action.ADD_BOWSER_CHARACTER,
  Action.ADD_KOOPA_CHARACTER, Action.ADD_BOO_CHARACTER, Action.ADD_BANK_SUBTYPE,
  Action.ADD_BANKCOIN_SUBTYPE, Action.ADD_ITEMSHOP_SUBTYPE,
]);

export function isAddAction(a) {
  return ADD_ACTIONS.has(a);
}

export function getSpaceTypeFromAction(action) {
  switch (action) {
    case Action.ADD_BLUE: return Space.BLUE;
    case Action.ADD_RED: return Space.RED;
    case Action.ADD_HAPPENING: return Space.HAPPENING;
    case Action.ADD_STAR: return Space.STAR;
    case Action.ADD_BLACKSTAR: return Space.BLACKSTAR;
    case Action.ADD_MINIGAME: return Space.MINIGAME;
    case Action.ADD_CHANCE: return Space.CHANCE;
    case Action.ADD_START: return Space.START;
    case Action.ADD_SHROOM: return Space.SHROOM;
    case Action.ADD_BOWSER: return Space.BOWSER;
    case Action.ADD_ITEM: return Space.ITEM;
    case Action.ADD_BATTLE: return Space.BATTLE;
    case Action.ADD_BANK: return Space.BANK;
    case Action.ADD_ARROW: return Space.ARROW;
    case Action.ADD_GAMEGUY: return Space.GAMEGUY;
    case Action.ADD_DUEL_BASIC: return Space.DUEL_BASIC;
    case Action.ADD_DUEL_REVERSE: return Space.DUEL_REVERSE;
    case Action.ADD_DUEL_POWERUP: return Space.DUEL_POWERUP;
    case Action.ADD_DUEL_START_BLUE: return Space.DUEL_START_BLUE;
    case Action.ADD_DUEL_START_RED: return Space.DUEL_START_RED;
    default: return Space.OTHER;
  }
}

export function getSpaceSubTypeFromAction(action) {
  switch (action) {
    case Action.ADD_TOAD_CHARACTER: return SpaceSubtype.TOAD;
    case Action.ADD_BOWSER_CHARACTER: return SpaceSubtype.BOWSER;
    case Action.ADD_KOOPA_CHARACTER: return SpaceSubtype.KOOPA;
    case Action.ADD_BOO_CHARACTER: return SpaceSubtype.BOO;
    case Action.ADD_BANK_SUBTYPE: return SpaceSubtype.BANK;
    case Action.ADD_BANKCOIN_SUBTYPE: return SpaceSubtype.BANKCOIN;
    case Action.ADD_ITEMSHOP_SUBTYPE: return SpaceSubtype.ITEMSHOP;
    case Action.MARK_GATE: return SpaceSubtype.GATE;
    default: return undefined;
  }
}

function canSetSubtypeOnSpaceType(type, subtype) {
  // Don't add gate to non-invisible space.
  return !(type !== Space.OTHER && subtype === SpaceSubtype.GATE);
}

export function canRemoveSpaceAtIndex(board, spaceIndex) {
  const space = board.spaces[spaceIndex];
  if (!space) return false;
  // Don't allow removing the last start space, since in non-advanced mode you can't add it back.
  if (space.type === Space.START) return getSpacesOfType(Space.START, board).length > 1;
  return true;
}

/**
 * Attaches the editing behaviour to the editor page.
 * ed: { view, toBoard(clientX, clientY) -> [x, y], redraw(), rc: { open(i), close(), isOpen(), update(i) },
 *       onTelescope(x, y), onPointer(x, y) }
 */
export class Interaction {
  constructor(ed) {
    this.ed = ed;
    this.down = false;
    this.spaceWasMouseDownedOn = false;
    this.startX = this.startY = this.lastX = this.lastY = -1;
    this.moved = new Set();           // indices moved by the current drag
    this.rotated = -1;                // index rotated by the current drag
    this.arrowTimer = null;
    this.arrowMoved = new Set();
    this.eraseBusy = false;

    const el = ed.view.input;
    el.addEventListener('pointerdown', e => this.onPointerDown(e));
    el.addEventListener('pointermove', e => this.onPointerMove(e));
    el.addEventListener('pointerup', e => this.onPointerUp(e));
    el.addEventListener('pointercancel', e => this.onPointerUp(e));
    el.addEventListener('pointerleave', () => this.ed.onPointer?.(null));
    el.addEventListener('dblclick', e => this.onDoubleClick(e));
    el.addEventListener('contextmenu', e => this.onRightClick(e));
    el.addEventListener('dragover', e => e.preventDefault());
    el.addEventListener('drop', e => this.onDrop(e));
    const tel = ed.view.telescope;
    tel.addEventListener('pointermove', e => {
      const [x, y] = ed.toBoard(e.clientX, e.clientY);
      ed.onTelescope?.(x, y);
    });
    tel.addEventListener('pointerleave', () => ed.onTelescope?.(null));
  }

  get board() {
    return store.board;
  }

  spaceRadius() {
    return this.board.game === 3 ? 14 : 8;
  }

  /** The last space under (x, y), or -1. (FIXME in the original: consider circular shape.) */
  getClickedSpace(x, y) {
    const r = this.spaceRadius();
    let idx = -1;
    this.board.spaces.forEach((space, i) => {
      if (space && Math.abs(space.x - x) <= r && Math.abs(space.y - y) <= r) idx = i;
    });
    return idx;
  }

  tempLineFrom(space, x, y) {
    store.tempConnections = [[space.x, space.y, x, y]];
    this.ed.redraw('lines');
  }

  clearTemp() {
    if (store.tempConnections) {
      store.tempConnections = null;
      this.ed.redraw('lines');
    }
  }

  setBox(box) {
    store.selectionBox = box;
    this.ed.redraw('box');
  }

  // Pointer down (mousedown / touchstart)
  onPointerDown(e) {
    if (!this.board) return;
    if (e.button === 2) {
      // Right button: select what was clicked, for the menu.
      const [x, y] = this.ed.toBoard(e.clientX, e.clientY);
      const idx = this.getClickedSpace(x, y);
      if (idx >= 0 && !store.isSelected(idx)) store.setSelection([idx]);
      return;
    }
    if (e.button !== 0) return;
    e.preventDefault();
    this.ed.view.input.focus({ preventScroll: true });
    this.ed.view.input.setPointerCapture?.(e.pointerId);
    this.down = true;
    const ctrlKey = e.ctrlKey || e.metaKey;
    const [clickX, clickY] = this.ed.toBoard(e.clientX, e.clientY);
    this.startX = this.lastX = clickX;
    this.startY = this.lastY = clickY;
    this.moved.clear();
    this.rotated = -1;
    if (store.highlighted) store.setHighlighted(null);

    const clickedSpaceIndex = this.getClickedSpace(clickX, clickY);
    const spaceWasClicked = clickedSpaceIndex !== -1;
    this.spaceWasMouseDownedOn = spaceWasClicked;
    const curAction = store.action;

    // ROM boards cannot be edited: only select, to look at the spaces.
    if (store.readonly) {
      if (spaceWasClicked) store.setSelection([clickedSpaceIndex]); else store.clearSelection();
      return;
    }

    if (curAction === Action.MOVE || ADD_ACTIONS.has(curAction) || SUBTYPE_ACTIONS.has(curAction)
      || curAction === Action.MARK_STAR) {
      if (spaceWasClicked) {
        if (ctrlKey) store.addSelected(clickedSpaceIndex);
        else if (!store.isSelected(clickedSpaceIndex)) store.setSelection([clickedSpaceIndex]);
      } else if (curAction === Action.MOVE || !ctrlKey) {
        store.clearSelection();
      }
    } else if (curAction === Action.LINE || curAction === Action.LINE_STICKY || curAction === Action.ROTATE) {
      if (spaceWasClicked) store.setSelection([clickedSpaceIndex]); else store.clearSelection();
    } else if (curAction === Action.ERASE) {
      store.clearSelection();
    }

    const selected = store.selectedSpaces();
    const clickedSpace = this.board.spaces[clickedSpaceIndex];

    switch (curAction) {
      case Action.LINE:
        if (selected.length === 1) {
          this.tempLineFrom(selected[0][1], clickX, clickY);
          if (this.ed.rc.isOpen()) this.ed.rc.close();
        }
        break;
      case Action.LINE_STICKY:
        if (selected.length === 1) {
          const [index, space] = selected[0];
          // Make a connection if we are in sticky mode and have reached a new space.
          if (clickedSpace && clickedSpace !== space) {
            store.op('addConnection', { startSpaceIndex: index, endSpaceIndex: clickedSpaceIndex }, 'Connect spaces');
            store.setSelection([clickedSpaceIndex]);
          } else {
            this.tempLineFrom(space, clickX, clickY);
          }
        }
        break;
      case Action.ERASE:
        this.erase(clickX, clickY, clickedSpaceIndex);
        break;
      case Action.MARK_STAR:
      case Action.MARK_GATE:
      case Action.ADD_TOAD_CHARACTER:
      case Action.ADD_BOWSER_CHARACTER:
      case Action.ADD_KOOPA_CHARACTER:
      case Action.ADD_BOO_CHARACTER:
      case Action.ADD_BANK_SUBTYPE:
      case Action.ADD_BANKCOIN_SUBTYPE:
      case Action.ADD_ITEMSHOP_SUBTYPE:
        if (clickedSpaceIndex === -1) this.addSpace(curAction, clickX, clickY, clickedSpaceIndex, false, ctrlKey);
        break;
      case Action.MOVE:
        if (this.ed.rc.isOpen()) this.ed.rc.update(store.selected[0] ?? -1);
        break;
      default:
        if (ADD_ACTIONS.has(curAction)) this.addSpace(curAction, clickX, clickY, clickedSpaceIndex, false, ctrlKey);
        break;
    }
  }

  erase(x, y, clickedSpaceIndex) {
    if (this.eraseBusy) return;
    const board = this.board;
    let p = null;
    if (clickedSpaceIndex !== -1 && canRemoveSpaceAtIndex(board, clickedSpaceIndex)) {
      p = store.op('removeSpace', { index: clickedSpaceIndex }, 'Erase space');
      store.clearSelection();
    } else if (lineAt(board, x, y)) {
      p = store.op('eraseConnections', { x, y }, 'Erase line'); // Try to slice some lines!
    }
    if (p) {
      this.eraseBusy = true;
      p.finally(() => { this.eraseBusy = false; });
    }
  }

  // Pointer move
  onPointerMove(e) {
    if (!this.board) return;
    const [clickX, clickY] = this.ed.toBoard(e.clientX, e.clientY);
    this.ed.onPointer?.(clickX, clickY);
    if (!this.down || !(e.buttons & 1)) return;
    if (store.readonly) return;

    const curAction = store.action;
    const selected = store.selectedSpaces();
    const clickedSpaceIndex = this.getClickedSpace(clickX, clickY);

    switch (curAction) {
      case Action.LINE:
        if (selected.length === 1) {
          this.tempLineFrom(selected[0][1], clickX, clickY);
          if (this.ed.rc.isOpen()) this.ed.rc.close();
        }
        break;
      case Action.LINE_STICKY:
        if (selected.length === 1) {
          const [index, space] = selected[0];
          const endSpace = this.board.spaces[clickedSpaceIndex];
          if (endSpace && endSpace !== space) {
            store.op('addConnection', { startSpaceIndex: index, endSpaceIndex: clickedSpaceIndex }, 'Connect spaces');
            store.setSelection([clickedSpaceIndex]);
            this.tempLineFrom(endSpace, clickX, clickY);
          } else {
            this.tempLineFrom(space, clickX, clickY);
          }
        }
        break;
      case Action.ROTATE:
        if (selected.length === 1) {
          const [index, space] = selected[0];
          if (space.type === Space.ARROW) {
            // Adjust rotation of the space.
            const angleXAxisRad = determineAngle(space.x, space.y, clickX, clickY);
            const angleYAxisRad = (Math.PI * 1.5 + angleXAxisRad) % (Math.PI * 2);
            const angleYAxisDeg = (angleYAxisRad * 180) / Math.PI;
            store.override(index, { rotation: Math.round(angleYAxisDeg) });
            this.rotated = index;
            this.ed.redraw('spaces');
            this.ed.onDragged?.();
          }
        }
        break;
      case Action.ERASE:
        this.erase(clickX, clickY, clickedSpaceIndex);
        break;
      case Action.TELESCOPE:
        break;
      default: {
        const doingSelectionBox = !this.spaceWasMouseDownedOn && curAction === Action.MOVE;
        if (!doingSelectionBox && selected.length) {
          // Move the space(s)
          const deltaX = clickX - this.lastX;
          const deltaY = clickY - this.lastY;
          if (deltaX || deltaY) {
            const { width, height } = this.board.bg;
            for (const [index, space] of selected) {
              const newX = Math.round(space.x) + deltaX;
              const newY = Math.round(space.y) + deltaY;
              store.override(index, {
                x: Math.max(0, Math.min(newX, width)),
                y: Math.max(0, Math.min(newY, height)),
              });
              this.moved.add(index);
            }
            this.ed.redraw('move');
            if (this.ed.rc.isOpen()) this.ed.rc.update(selected[0][0]);
            this.ed.onDragged?.();
          }
        }
        if (doingSelectionBox) this.updateSelectionAndBox(clickX, clickY);
        break;
      }
    }
    this.lastX = clickX;
    this.lastY = clickY;
  }

  updateSelectionAndBox(curX, curY) {
    if (this.startX === -1 || this.startY === -1) return;
    const indices = [];
    this.board.spaces.forEach((space, i) => {
      if (space && pointFallsWithin(space.x, space.y, this.startX, this.startY, curX, curY)) indices.push(i);
    });
    store.setSelection(indices);
    this.setBox([this.startX, this.startY, curX, curY]);
  }

  /** Sends the positions/rotation the drag changed. */
  commitDrag() {
    if (this.moved.size) {
      const spaceIndices = [...this.moved];
      const coords = spaceIndices.map(i => ({ x: this.board.spaces[i].x, y: this.board.spaces[i].y }));
      store.ops([{ op: 'setSpacePositions', args: { spaceIndices, coords } }],
        spaceIndices.length === 1 ? `Move space ${spaceIndices[0]}` : `Move ${spaceIndices.length} spaces`,
        { overrides: spaceIndices });
      this.moved.clear();
    }
    if (this.rotated >= 0) {
      const i = this.rotated;
      store.ops([{ op: 'setSpaceRotation', args: { spaceIndex: i, angleYAxisDeg: this.board.spaces[i].rotation } }],
        `Rotate space ${i}`, { overrides: [i] });
      this.rotated = -1;
    }
  }

  // Pointer up (mouseup / touchend), then what the original did on click.
  onPointerUp(e) {
    if (!this.down) return;
    this.down = false;
    if (!this.board || store.readonly) return;
    const [clickX, clickY] = this.ed.toBoard(e.clientX, e.clientY);
    const ctrlKey = e.ctrlKey || e.metaKey;
    const curAction = store.action;

    this.commitDrag();

    switch (curAction) {
      case Action.MOVE:
        if (!this.spaceWasMouseDownedOn) this.setBox(null); // Clear the selection we were drawing.
        break;
      case Action.LINE: {
        const endSpaceIdx = this.getClickedSpace(this.lastX, this.lastY);
        if (endSpaceIdx !== -1) {
          const list = store.selected.filter(i => i !== endSpaceIdx && this.board.spaces[i])
            .map(i => ({ op: 'addConnection', args: { startSpaceIndex: i, endSpaceIndex: endSpaceIdx } }));
          if (list.length) store.ops(list, 'Connect spaces');
        }
        this.clearTemp();
        break;
      }
      case Action.LINE_STICKY:
        this.clearTemp();
        break;
    }

    // The click (mouseup without much movement).
    const moved = Math.abs(this.startX - this.lastX) > 5 || Math.abs(this.startY - this.lastY) > 5;
    const movedAtAll = Math.abs(this.startX - this.lastX) > 0 || Math.abs(this.startY - this.lastY) > 0;
    this.startX = this.lastX = -1;
    this.startY = this.lastY = -1;
    const clickedSpaceIdx = this.getClickedSpace(clickX, clickY);
    const clickedSpace = clickedSpaceIdx === -1 ? null : this.board.spaces[clickedSpaceIdx];

    if (curAction === Action.MOVE || ADD_ACTIONS.has(curAction)) {
      if (!movedAtAll && !ctrlKey) {
        if (!clickedSpace) store.clearSelection(); else store.setSelection([clickedSpaceIdx]);
      }
    } else if (SUBTYPE_ACTIONS.has(curAction)) {
      // Toggle the subtype only at the moment of mouse up, if we didn't move.
      if (this.spaceWasMouseDownedOn) this.addSpace(curAction, clickX, clickY, clickedSpaceIdx, moved, ctrlKey);
      if (!movedAtAll && !ctrlKey) {
        if (!clickedSpace) store.clearSelection(); else store.setSelection([clickedSpaceIdx]);
      }
    } else if (curAction === Action.MARK_STAR) {
      if (!moved) this.toggleHostsStar(store.selected.filter(i => this.board.spaces[i]));
    }
    this.spaceWasMouseDownedOn = false;
  }

  addSpace(action, x, y, clickedSpaceIndex, moved, ctrlKey) {
    const board = this.board;
    const clickedSpace = board.spaces[clickedSpaceIndex];
    const spaceType = getSpaceTypeFromAction(action);
    const spaceSubType = getSpaceSubTypeFromAction(action);
    if (clickedSpace) {
      // If we are clicking a space, the only "add" action could be to toggle subtype.
      if (spaceSubType !== undefined && !moved) {
        if (clickedSpace.subtype === spaceSubType) {
          store.op('setSpaceSubtype', { spaceIndices: [clickedSpaceIndex] }, 'Remove character');
        } else if (canSetSubtypeOnSpaceType(clickedSpace.type, spaceSubType)) {
          store.op('setSpaceSubtype', { spaceIndices: [clickedSpaceIndex], subtype: spaceSubType }, 'Set character');
        }
        store.setSelection([clickedSpaceIndex]);
        return true;
      }
      return false;
    }
    const newIndex = board.spaces.length;
    const args = { x: Math.round(x), y: Math.round(y), type: spaceType };
    if (spaceSubType !== undefined) args.subtype = spaceSubType;
    const local = { x: args.x, y: args.y, z: 0, type: spaceType };
    if (spaceSubType !== undefined) local.subtype = spaceSubType;
    store.ops([{ op: 'addSpace', args }], `Add space ${newIndex}`, { optimistic: local });
    if (ctrlKey) store.addSelected(newIndex); else store.setSelection([newIndex]);
    return true;
  }

  toggleHostsStar(indices) {
    if (!indices.length) return;
    // If any space does not have star hosting, we add to all. Otherwise remove from all.
    const adding = indices.some(i => !this.board.spaces[i].star);
    store.op('setSpaceHostsStar', { spaceIndices: indices, hostsStar: adding }, adding ? 'Host star' : 'Stop hosting star');
  }

  onDoubleClick(e) {
    if (!this.board) return;
    const [x, y] = this.ed.toBoard(e.clientX, e.clientY);
    const idx = this.getClickedSpace(x, y);
    // Double-clicking a space opens its quick menu (coordinates and type).
    if (idx >= 0 && (store.action === Action.MOVE || store.readonly)) {
      store.setSelection([idx]);
      this.ed.rc.open(idx);
    }
  }

  onRightClick(e) {
    e.preventDefault();
    e.stopPropagation();
    const sel = store.selected.filter(i => this.board?.spaces[i]);
    if (sel.length === 1) this.ed.rc.open(sel[0]); else this.ed.rc.close();
  }

  onDrop(e) {
    e.preventDefault();
    if (!this.board || store.readonly) return;
    if (this.ed.rc.isOpen()) this.ed.rc.close();
    let data;
    try {
      data = JSON.parse(e.dataTransfer.getData('text'));
    } catch {
      return;
    }
    const [x, y] = this.ed.toBoard(e.clientX, e.clientY);
    const idx = this.getClickedSpace(x, y);
    if (data && typeof data === 'object') {
      if (data.action !== undefined) {
        store.clearSelection();
        this.addSpace(data.action, x, y, idx, false, false);
      } else if (data.isEventParamDrop && eventParamDropHandler) {
        const fn = eventParamDropHandler;
        eventParamDropHandler = null;
        fn(idx);
      }
    }
  }

  /** Keyboard editing; returns true if the key was handled. */
  onKeyDown(e) {
    if (!this.board) return false;
    const ctrl = e.ctrlKey || e.metaKey;
    const key = e.key;
    if (ctrl && (key === 'a' || key === 'A')) {
      store.setSelection(this.board.spaces.map((s, i) => (s ? i : -1)).filter(i => i >= 0));
      return true;
    }
    if (key === 'Escape') {
      this.ed.rc.close();
      this.clearTemp();
      store.clearSelection();
      store.setHighlighted(null);
      return true;
    }
    if (store.readonly) return false;
    const selected = store.selectedSpaces();
    if (!selected.length) return false;
    const { width, height } = this.board.bg;
    const step = e.shiftKey ? 10 : 1;
    let dx = 0;
    let dy = 0;
    switch (key) {
      case 'Up': case 'ArrowUp': dy = -step; break;
      case 'Down': case 'ArrowDown': dy = step; break;
      case 'Left': case 'ArrowLeft': dx = -step; break;
      case 'Right': case 'ArrowRight': dx = step; break;
      case 'Delete': case 'Backspace': this.deleteSelected(selected); return true;
      default: return false;
    }
    for (const [index, space] of selected) {
      store.override(index, {
        x: Math.max(0, Math.min(space.x + dx, width)),
        y: Math.max(0, Math.min(space.y + dy, height)),
      });
      this.arrowMoved.add(index);
    }
    this.ed.redraw('move');
    this.ed.onDragged?.();
    // Key repeats are sent as one edit.
    clearTimeout(this.arrowTimer);
    this.arrowTimer = setTimeout(() => {
      const spaceIndices = [...this.arrowMoved].filter(i => this.board.spaces[i]);
      this.arrowMoved.clear();
      if (!spaceIndices.length) return;
      const coords = spaceIndices.map(i => ({ x: this.board.spaces[i].x, y: this.board.spaces[i].y }));
      store.ops([{ op: 'setSpacePositions', args: { spaceIndices, coords } }], 'Nudge spaces', { overrides: spaceIndices });
    }, 350);
    return true;
  }

  deleteSelected(selected) {
    // If any characters are on the spaces, first press just deletes them.
    // If there are no characters, selected spaces are deleted.
    const indices = selected.map(([i]) => i);
    if (selected.some(([, s]) => s.subtype !== undefined && s.subtype !== null)) {
      store.op('setSpaceSubtype', { spaceIndices: indices }, 'Remove characters');
      return;
    }
    const removable = indices.filter(i => canRemoveSpaceAtIndex(this.board, i));
    if (removable.length) {
      store.op('removeSpaces', { spaceIndices: removable },
        removable.length === 1 ? `Delete space ${removable[0]}` : `Delete ${removable.length} spaces`);
    }
    store.clearSelection();
    this.ed.rc.close();
  }
}
