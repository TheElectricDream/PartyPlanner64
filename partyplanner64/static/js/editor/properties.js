// The properties card: the selected space(s) (spaceproperties.tsx) or, with nothing selected, the
// board (boardproperties.tsx).
import { esc, toast, pickFile, readDataURL, promptDialog } from '../api.js';
import {
  Space, BoardType, EditorEventActivationType as A, getTypeToggles, getSubtypeToggles, SpaceNames,
  SubtypeNames, mainBgSize, IMG,
} from './constants.js';
import { store } from './store.js';
import { renderEventList } from './eventlist.js';
import {
  createEventInstance, getDefaultActivationType, getDeadEnds, supportsAnimationBackgrounds,
  supportsAdditionalBackgrounds,
} from './board.js';
import { showDecisionTree } from './aitree.js';

function getAvailableBoardActivationTypes(board) {
  if (board.game === 3) return [A.BEFORE_TURN, A.AFTER_TURN, A.BEFORE_PLAYER_TURN, A.BEFORE_DICE_ROLL];
  // AFTER_TURN is not confirmed in other games besides 3.
  return [A.BEFORE_TURN, A.BEFORE_PLAYER_TURN, A.BEFORE_DICE_ROLL];
}

// Animation backgrounds playing on the board (renderer.tsx playAnimation).
let animInterval = null;
let currentFrame = -1;

export function animationPlaying() {
  return !!animInterval;
}

export function playAnimation() {
  if (!animInterval) {
    animInterval = setInterval(animationStep, 800);
    store.setOverrideBg(null);
  }
}

export function stopAnimation() {
  if (animInterval) clearInterval(animInterval);
  animInterval = null;
  currentFrame = -1;
  store.setOverrideBg(null);
}

function animationStep() {
  const board = store.board;
  const animbgs = board?.animbg;
  if (!animbgs || !animbgs.length) {
    stopAnimation();
    return;
  } else if (currentFrame >= 0 && currentFrame < animbgs.length) {
    store.setOverrideBg(animbgs[currentFrame]);
    currentFrame++;
  } else {
    currentFrame = -1;
  }
  if (currentFrame === -1) {
    store.setOverrideBg(board.bg.src);
    currentFrame++;
  }
}

export class PropertiesCard {
  /** card: the .card element; app: the app; opts.showPage(name, section) */
  constructor(card, app, opts = {}) {
    this.card = card;
    this.app = app;
    this.opts = opts;
    // Events added to several selected spaces at once: [{ eventListIndices }] (MultipleSpacesEventList).
    this.multiKey = '';
    this.addedEvents = [];
    this.title = card.querySelector('.card-head h2');
    this.pill = card.querySelector('.card-head .pill');
    this.body = card.querySelector('.props-body');
    store.on('board', () => this.render());
    store.on('selection', () => this.render());
    store.on('library', () => this.render());
    store.on('overridebg', () => this.render());
  }

  render() {
    const board = store.board;
    if (!board) {
      this.title.textContent = 'Properties';
      this.pill.hidden = true;
      this.body.innerHTML = '<p class="hint">Loading the board…</p>';
      return;
    }
    const selected = store.selectedSpaces();
    // Keep the focused input (typing a coordinate) from being rebuilt under the cursor.
    const focused = document.activeElement;
    if (focused && this.body.contains(focused) && focused.matches('input[type=number]')) {
      this.syncCoords(selected);
      return;
    }
    if (selected.length) this.renderSpaces(board, selected);
    else this.renderBoard(board);
  }

  /** Only refreshes the coordinate fields (while dragging). */
  syncCoords(selected = store.selectedSpaces()) {
    if (selected.length !== 1) return;
    const [, space] = selected[0];
    for (const input of this.body.querySelectorAll('[data-coord]')) {
      if (document.activeElement === input) continue;
      const v = space[input.dataset.coord];
      input.value = v ?? '';
    }
  }

  // ---------- spaces ----------

  renderSpaces(board, selected) {
    const ro = store.readonly;
    const advanced = !!this.app.setting('ui.advanced');
    const multiple = selected.length > 1;
    const [curIndex, curSpace] = selected[0];
    const isDuel = board.type === BoardType.DUEL;

    let currentType = curSpace.type;
    let currentSubtype = curSpace.subtype;
    const hostsStar = !!curSpace.star;
    let hostsStarMixed = false;
    // Only show a type as selected if all spaces are the same.
    for (const [, s] of selected) {
      if (s.type !== currentType) currentType = undefined;
      if (s.subtype !== currentSubtype) currentSubtype = undefined;
      if (!!s.star !== hostsStar) hostsStarMixed = true;
    }

    this.title.textContent = multiple ? `${selected.length} Spaces` : `Space ${curIndex}`;
    this.pill.hidden = false;
    this.pill.className = 'pill';
    this.pill.textContent = multiple ? 'Selection' : (SpaceNames[curSpace.type] || `Type ${curSpace.type}`);
    this.pill.title = multiple ? 'Several spaces are selected: changes apply to all of them' : 'The space\'s type';

    const showTypes = !(currentType === Space.START && !advanced); // Can't switch start space type
    const toggles = (items, isSub) => items.map(item => {
      const selectedBtn = isSub
        ? item.subtype !== undefined && currentSubtype !== undefined && currentSubtype === item.subtype
        : item.type !== undefined && currentType === item.type;
      return `<button type="button" class="type-btn${selectedBtn ? ' active' : ''}${isSub ? ' sub' : ''}" ${ro ? 'disabled' : ''}
        data-type="${item.type ?? ''}" data-subtype="${item.subtype ?? ''}" title="${esc(item.name)}"><img src="${item.icon}" alt=""></button>`;
    }).join('');
    const subs = getSubtypeToggles(board.game, board.type);
    const isArrow = !multiple && curSpace.type === Space.ARROW;

    this.body.innerHTML = `
      ${!multiple ? `<div class="coord-row">
        <label class="coord" title="The space's X coordinate, in pixels from the left of the background (arrow keys nudge the selection)">
          <span>X</span><input class="input mono" type="number" data-coord="x" min="0" max="${board.bg.width}" value="${curSpace.x}" ${ro ? 'disabled' : ''}></label>
        <label class="coord" title="The space's Y coordinate, in pixels from the top of the background (arrow keys nudge the selection)">
          <span>Y</span><input class="input mono" type="number" data-coord="y" min="0" max="${board.bg.height}" value="${curSpace.y}" ${ro ? 'disabled' : ''}></label>
        ${isArrow ? `<label class="coord" title="Which way the arrow points, in degrees counter-clockwise from up (or drag it with the Rotate tool)">
          <span>Rot.</span><input class="input mono" type="number" data-coord="rotation" min="0" max="359" value="${curSpace.rotation ?? 0}" ${ro ? 'disabled' : ''}></label>` : ''}
      </div>` : `<p class="hint props-multi">Changes apply to all ${selected.length} selected spaces.</p>`}
      ${showTypes ? `<span class="field-label">Type</span><div class="type-grid">${toggles(getTypeToggles(board.game, board.type, advanced), false)}</div>` : ''}
      ${showTypes && subs.length ? `<span class="field-label">Character</span><div class="type-grid subs">${toggles(subs, true)}</div>` : ''}
      ${!multiple && curSpace.subtype !== undefined && !subs.some(s => s.subtype === curSpace.subtype)
        ? `<p class="hint">Shows: ${esc(SubtypeNames[curSpace.subtype] || curSpace.subtype)}</p>` : ''}
      <div class="props-toggles">
        ${!isDuel ? `<label class="toggle${hostsStarMixed ? ' mixed' : ''}" title="The star can appear at this space (the game picks among the spaces hosting a star)${hostsStarMixed ? '. Some of the selected spaces host a star and some do not.' : ''}">
          <input type="checkbox" data-star ${hostsStar && !hostsStarMixed ? 'checked' : ''} ${ro ? 'disabled' : ''}><span></span>Hosts Star${hostsStarMixed ? ' (Mixed)' : ''}</label>` : ''}
        ${curSpace.aiTree ? '<button type="button" class="btn btn-sm" data-aitree title="Show how the computer players decide which way to go at this space">AI Decision Tree</button>' : ''}
      </div>
      <div class="section">
        <div class="section-head"><h3>Events</h3>${multiple ? '<span class="hint">New events only</span>' : ''}</div>
        ${multiple ? '<p class="hint">Multiple spaces selected: you may add and edit new events only.</p>' : ''}
        <div class="props-events"></div>
      </div>`;

    // Coordinates
    for (const input of this.body.querySelectorAll('[data-coord]')) {
      const commit = () => {
        const which = input.dataset.coord;
        const v = parseInt(input.value, 10);
        const space = store.board.spaces[curIndex];
        if (!space || isNaN(v)) return;
        if (which === 'rotation') {
          if (v < 0 || v > 360 || v === (space.rotation ?? 0)) return;
          store.op('setSpaceRotation', { spaceIndex: curIndex, angleYAxisDeg: v }, `Rotate space ${curIndex}`);
          return;
        }
        const max = which === 'x' ? store.board.bg.width : store.board.bg.height;
        if (v < 0 || v > max || v === space[which]) return;
        store.op('setSpacePositions', { spaceIndices: [curIndex], coords: [{ [which]: v }] }, `Move space ${curIndex}`);
      };
      input.addEventListener('change', commit);
      input.addEventListener('keyup', e => { if (e.key === 'Enter') input.blur(); });
    }
    // Types
    for (const btn of this.body.querySelectorAll('.type-btn')) {
      btn.addEventListener('click', () => {
        const spaceIndices = selected.map(([i]) => i);
        const isSub = btn.classList.contains('sub');
        const args = { spaceIndices };
        if (!isSub) args.type = Number(btn.dataset.type);
        else if (!btn.classList.contains('active')) args.subtype = Number(btn.dataset.subtype);
        store.op('setSpaceType', args, isSub ? 'Change character' : 'Change space type');
      });
    }
    this.body.querySelector('[data-star]')?.addEventListener('change', e => {
      store.op('setSpaceHostsStar', { spaceIndices: selected.map(([i]) => i), hostsStar: e.target.checked },
        e.target.checked ? 'Host star' : 'Stop hosting star');
    });
    this.body.querySelector('[data-aitree]')?.addEventListener('click', () => showDecisionTree(curSpace.aiTree, curIndex));

    // Events
    const evEl = this.body.querySelector('.props-events');
    if (!multiple) this.renderSpaceEvents(evEl, board, curIndex, curSpace);
    else this.renderMultipleSpaceEvents(evEl, board, selected);
  }

  renderSpaceEvents(el, board, spaceIndex, space) {
    const ro = store.readonly;
    renderEventList(el, {
      events: space.events, board, library: store.library, readonly: ro,
      emptyText: ro ? 'No events.' : '',
      onAdd: event => {
        const inst = createEventInstance(event, { activationType: getDefaultActivationType(space) });
        store.op('addEventToSpaces', { event: inst, spaceIndices: [spaceIndex] }, `Add event ${event.name}`);
      },
      onDelete: i => store.op('removeEventsFromSpaces', { eventIndices: [i], spaceIndices: [spaceIndex] }, 'Remove event'),
      onToggleActivation: (inst, i) => {
        const activationType = inst.activationType === A.WALKOVER ? A.LANDON : A.WALKOVER;
        store.op('setSpaceEventsActivationType', { spaceIndices: [spaceIndex], eventIndices: [i], activationType },
          'Change event activation');
      },
      onSetParam: (i, name, value) => store.op('setSpaceEventsEventParameter',
        { spaceIndices: [spaceIndex], eventIndices: [i], name, value }, `Set ${name}`),
    });
  }

  renderMultipleSpaceEvents(el, board, selected) {
    const spaceIndices = selected.map(([i]) => i);
    const key = spaceIndices.join(',');
    if (key !== this.multiKey) {
      this.multiKey = key;
      this.addedEvents = [];
    }
    // Since each selected space should have the same events added, gather them from the first
    // selected space for display.
    const first = selected[0][1];
    const added = this.addedEvents.filter(a => first.events?.[a.eventListIndices[0]]);
    const events = added.map(a => first.events[a.eventListIndices[0]]);
    renderEventList(el, {
      events, board, library: store.library, readonly: store.readonly,
      onAdd: async event => {
        const inst = createEventInstance(event, { activationType: getDefaultActivationType(first) });
        // Each space's event list gets the event at its end.
        const eventListIndices = spaceIndices.map(i => (store.board.spaces[i].events || []).length);
        this.addedEvents.push({ eventListIndices });
        const res = await store.op('addEventToSpaces', { event: inst, spaceIndices }, `Add event ${event.name} to ${spaceIndices.length} spaces`);
        if (!res) this.addedEvents.pop();
        this.render();
      },
      onDelete: async i => {
        const eventIndices = this.addedEvents[i].eventListIndices;
        // Event indices lists beyond the removed one need to have values decreased.
        for (let j = i + 1; j < this.addedEvents.length; j++) {
          this.addedEvents[j].eventListIndices = this.addedEvents[j].eventListIndices.map(x => x - 1);
        }
        this.addedEvents.splice(i, 1);
        await store.op('removeEventsFromSpaces', { eventIndices, spaceIndices }, 'Remove event');
      },
      onToggleActivation: (inst, i) => {
        const activationType = inst.activationType === A.WALKOVER ? A.LANDON : A.WALKOVER;
        store.op('setSpaceEventsActivationType',
          { eventIndices: this.addedEvents[i].eventListIndices, spaceIndices, activationType }, 'Change event activation');
      },
      onSetParam: (i, name, value) => store.op('setSpaceEventsEventParameter',
        { eventIndices: this.addedEvents[i].eventListIndices, spaceIndices, name, value }, `Set ${name}`),
    });
  }

  // ---------- board ----------

  renderBoard(board) {
    const ro = store.readonly;
    const debug = !!this.app.setting('ui.debug');
    const advanced = !!this.app.setting('ui.advanced');
    const [bw, bh] = mainBgSize(board.game, board.type);
    this.title.textContent = 'Board';
    this.pill.hidden = false;
    this.pill.className = ro ? 'pill warn' : 'pill';
    this.pill.textContent = ro ? 'ROM · Read-Only' : `MP${board.game}${board.type === BoardType.DUEL ? ' Duel' : ''}`;
    this.pill.title = ro ? 'This board is in the ROM: copy it to edit it' : 'The game this board is for';

    const animList = supportsAnimationBackgrounds(board);
    const hasAdd = supportsAdditionalBackgrounds(board)
      && (advanced || (board.additionalbg && board.additionalbg.length) || !!board.additionalbgcode);

    const bgRows = (list, kind) => (board[list] || []).map((bg, i) => {
      const showing = store.overrideBg === bg;
      return `<div class="bg-row" data-kind="${kind}" data-i="${i}">
        <img src="${esc(bg)}" alt="" class="bg-thumb">
        <span class="bg-name">Background ${i + 1}</span>
        <button type="button" class="btn btn-ghost btn-sm btn-icon eye${showing ? ' active' : ''}" data-eye title="Show this background on the board until dismissed">
          <svg viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="2" d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2"/></svg></button>
        ${ro ? '' : '<button type="button" class="btn btn-ghost btn-sm btn-icon" data-remove title="Remove this background">✕</button>'}
      </div>`;
    }).join('');

    this.body.innerHTML = `
      <p class="board-name-line" title="The board's name (edit it on the Details page)">${esc(plain(board.name))}</p>
      <div class="action-list">
        <button type="button" class="action-row" data-details title="${ro ? 'See' : 'Edit'} the board's name, description, difficulty, images and music">
          <img src="${IMG}/header/editdetails.png" alt=""><span>${ro ? 'View Board Details' : 'Edit Board Details'}</span></button>
        ${ro ? '' : `<button type="button" class="action-row" data-setbg title="Choose the board's main background image (${bw} × ${bh})">
          <img src="${IMG}/header/setbg.png" alt=""><span>Change Main Background</span><span class="muted small">${bw} × ${bh}</span></button>
        <button type="button" class="action-row" data-deadends title="Look for paths that end without connecting to another space: they are highlighted in red">
          <img src="${IMG}/editor/boardproperties/deadend.png" alt=""><span>Check for Dead Ends</span></button>`}
        ${debug ? `<button type="button" class="action-row" data-find title="Highlight a space by its index">
          <img src="${IMG}/header/board.png" alt=""><span>Find Space by Index</span></button>` : ''}
      </div>
      ${animList && (!ro || (board.animbg || []).length) ? `<div class="section">
        <div class="section-head"><h3 class="tip" title="Frames the game cycles through over the main background (MP2)">Animation Backgrounds</h3>
          ${(board.animbg || []).length ? `<button type="button" class="btn btn-sm" data-play title="${animationPlaying() ? 'Stop the animation' : 'Play the animation on the board'}">${animationPlaying() ? '▮▮ Stop' : '► Play'}</button>` : ''}</div>
        ${bgRows('animbg', 'anim') || '<p class="hint">No animation frames.</p>'}
        ${ro ? '' : `<button type="button" class="btn btn-sm" data-add="anim" title="Add an animation frame, the size of the main background (${bw} × ${bh})">
          <img src="${IMG}/toolbar/animadd.png" alt="">Add Background</button>`}
      </div>` : ''}
      ${hasAdd ? `<div class="section">
        <div class="section-head"><h3 class="tip" title="Other main backgrounds the board can switch to, chosen each turn by the additional background code">Additional Backgrounds</h3>
          <button type="button" class="btn btn-sm" data-bgcode title="Configure additional background usage: the code that picks the background each turn">⚙ Code</button></div>
        ${bgRows('additionalbg', 'add') || '<p class="hint">No additional backgrounds.</p>'}
        ${ro ? '' : `<button type="button" class="btn btn-sm" data-add="add" title="Add a background the board can switch to (${bw} × ${bh})">
          <img src="${IMG}/toolbar/animadd.png" alt="">Add Background</button>`}
      </div>` : ''}
      ${ro ? `<div class="notice info">Boards from the ROM are read-only. <button type="button" class="btn btn-sm btn-primary" data-copy title="Make an editable copy of this board">Copy to Edit</button></div>` : `<div class="section">
        <div class="section-head"><h3 class="tip" title="Events that run at set times of each turn rather than on a space">Board Events</h3></div>
        <div class="props-events"></div></div>`}`;

    const q = s => this.body.querySelector(s);
    q('[data-details]')?.addEventListener('click', () => this.opts.showPage?.('details'));
    q('[data-setbg]')?.addEventListener('click', async () => {
      const file = await pickFile('image/*');
      if (!file) return;
      const bg = await readDataURL(file);
      store.op('setBackground', { bg }, 'Change main background');
    });
    q('[data-deadends]')?.addEventListener('click', e => {
      const deadEnds = getDeadEnds(store.board);
      store.addLog(`Dead ends: ${deadEnds.length ? deadEnds.join(', ') : 'none'}`);
      if (deadEnds.length) {
        store.setHighlighted(deadEnds);
        toast(`${deadEnds.length} dead end${deadEnds.length === 1 ? '' : 's'} found (highlighted in red): space${deadEnds.length === 1 ? '' : 's'} ${deadEnds.join(', ')}.`, 'warn');
      } else {
        const span = e.currentTarget.querySelector('span');
        span.textContent = '✓ No Dead Ends';
        setTimeout(() => { span.textContent = 'Check for Dead Ends'; }, 1000);
      }
    });
    q('[data-find]')?.addEventListener('click', async () => {
      const value = await promptDialog('Enter a space index:', { title: 'Find Space' });
      const i = parseInt(value, 10);
      if (!isNaN(i)) store.setHighlighted([i]);
    });
    q('[data-play]')?.addEventListener('click', () => {
      if (animationPlaying()) stopAnimation(); else playAnimation();
      this.render();
    });
    q('[data-bgcode]')?.addEventListener('click', () => this.opts.showPage?.('details', 'additionalbg'));
    q('[data-copy]')?.addEventListener('click', () => this.opts.copyBoard?.());
    for (const btn of this.body.querySelectorAll('[data-add]')) {
      btn.addEventListener('click', async () => {
        const file = await pickFile('image/*');
        if (!file) return;
        const bg = await readDataURL(file);
        if (btn.dataset.add === 'anim') store.op('addAnimationBackground', { bg }, 'Add animation background');
        else store.op('addAdditionalBackground', { bg }, 'Add additional background');
      });
    }
    for (const row of this.body.querySelectorAll('.bg-row')) {
      const i = +row.dataset.i;
      const list = row.dataset.kind === 'anim' ? 'animbg' : 'additionalbg';
      const bg = board[list][i];
      row.querySelector('[data-eye]').addEventListener('click', () => {
        if (animationPlaying()) return;
        store.setOverrideBg(store.overrideBg === bg ? null : bg);
      });
      row.querySelector('[data-remove]')?.addEventListener('click', () => {
        if (store.overrideBg === bg) store.setOverrideBg(null);
        store.op(list === 'animbg' ? 'removeAnimationBackground' : 'removeAdditionalBackground', { index: i },
          'Remove background');
      });
    }

    const evEl = q('.props-events');
    if (evEl) {
      renderEventList(evEl, {
        events: board.boardevents, board, library: store.library, readonly: ro,
        onAdd: event => {
          const inst = createEventInstance(event, { activationType: A.BEFORE_PLAYER_TURN });
          store.op('addEventToBoard', { event: inst }, `Add board event ${event.name}`);
        },
        onDelete: i => store.op('removeEventFromBoard', { eventIndex: i }, 'Remove board event'),
        onToggleActivation: (inst, i) => {
          const types = getAvailableBoardActivationTypes(store.board);
          const cur = types.indexOf(inst.activationType);
          const activationType = types[(cur + 1) % types.length];
          store.op('setBoardEventActivationType', { eventIndex: i, activationType }, 'Change board event activation');
        },
        onSetParam: (i, name, value) => store.op('setBoardEventEventParameter', { eventIndex: i, name, value }, `Set ${name}`),
        onHover: i => store.setHoveredBoardEvent(i),
      });
    }
  }
}

function plain(text) {
  return String(text || '').replace(/<(DEFAULT|BLACK|WHITE|RED|GREEN|BLUE|PURPLE|YELLOW)>/g, '').replace(/\n/g, ' ');
}
