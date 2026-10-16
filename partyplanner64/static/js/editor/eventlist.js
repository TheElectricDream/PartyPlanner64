// A list of event instances with their activation type and parameters, and a picker to add
// events (port of components/EventList.tsx). Used for space events and board events.
import { esc, promptDialog, toast } from '../api.js';
import { EditorEventActivationType as A, EventParameterType, IMG } from './constants.js';
import {
  getEvent, getAvailableEvents, getBoardEvent, parseCustomEvent, getDistinctColor, isArrayEventParameterType,
} from './board.js';
import { setEventParamDropHandler } from './interaction.js';
import { getImage } from './images.js';

const ActivationTypeImages = {
  [A.WALKOVER]: `${IMG}/toolbar/eventpassing.png`,
  [A.LANDON]: `${IMG}/toolbar/eventstanding.png`,
  [A.BEFORE_TURN]: `${IMG}/editor/boardproperties/eventperturn.png`,
  [A.AFTER_TURN]: `${IMG}/editor/boardproperties/eventafterturn.png`,
  [A.BEFORE_PLAYER_TURN]: `${IMG}/editor/boardproperties/eventbeforeplayerturn.png`,
  [A.BEFORE_DICE_ROLL]: `${IMG}/editor/boardproperties/eventbeforediceroll.png`,
};

const ActivationTypeText = {
  [A.WALKOVER]: 'Passing Event',
  [A.LANDON]: 'Land-On Event',
  [A.BEFORE_TURN]: 'Before Turn',
  [A.AFTER_TURN]: 'After Turn',
  [A.BEFORE_PLAYER_TURN]: 'Before Player Turn',
  [A.BEFORE_DICE_ROLL]: 'Before Dice Roll',
};

const ActivationTypeTitles = {
  [A.WALKOVER]: 'Occurs when passing over the space',
  [A.LANDON]: 'Occurs when landing on the space',
  [A.BEFORE_TURN]: 'Occurs once per turn, prior to seeing "PLAYER START" for the first player',
  [A.AFTER_TURN]: 'Occurs once per turn, prior to the Mini-Game selection list appearing',
  [A.BEFORE_PLAYER_TURN]: 'Occurs for each player prior to seeing "PLAYER START" on their turn',
  [A.BEFORE_DICE_ROLL]: 'Occurs for each player prior to the dice roll',
};

function eventsForAddList(board, library) {
  const boardEvents = [];
  for (const name in board.events || {}) {
    const be = getBoardEvent(board, name);
    if (be) boardEvents.push(parseCustomEvent(be.language, be.code));
  }
  // Don't show library events that are also in the board events list. Force the user to
  // conscientiously go to Events to "upgrade" the version of an event in use.
  const libraryEvents = getAvailableEvents(board, library).filter(e => !(e.name in (board.events || {})));
  const sort = (a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
  return { boardEvents: boardEvents.sort(sort), libraryEvents: libraryEvents.sort(sort) };
}

/**
 * Renders the list into `el`.
 * opts: { events, board, library, readonly, onAdd(event), onDelete(i), onToggleActivation(inst, i),
 *         onSetParam(i, name, value), onHover(i or -1), emptyText }
 */
export function renderEventList(el, opts) {
  const { board, library, readonly } = opts;
  const events = opts.events || [];
  el.classList.add('event-list');
  const entries = events.map((inst, i) => {
    const event = getEvent(inst.id, board, library);
    const name = event ? (event.name || inst.id) : inst.id;
    const act = inst.activationType;
    const params = event ? paramChips(event, inst, readonly) : '<span class="ev-missing">This event is not in the library.</span>';
    return `<div class="ev-entry${event ? '' : ' ev-error'}" data-i="${i}">
      <div class="ev-head"><span class="ev-name" title="${esc(name)}">${esc(name)}</span>
        ${readonly ? '' : `<button type="button" class="btn btn-ghost btn-sm btn-icon ev-del" title="Remove this event">✕</button>`}</div>
      <div class="ev-opts">
        <button type="button" class="ev-chip ev-act" title="${esc(ActivationTypeTitles[act] || '')}${readonly ? '' : ' (click to change)'}" ${readonly ? 'disabled' : ''}>
          ${ActivationTypeImages[act] ? `<img src="${ActivationTypeImages[act]}" alt="">` : ''}<span>${esc(ActivationTypeText[act] || `Activation ${act}`)}</span></button>
        ${params}
      </div></div>`;
  }).join('');

  let addHtml = '';
  if (!readonly) {
    const { boardEvents, libraryEvents } = eventsForAddList(board, library);
    if (boardEvents.length || libraryEvents.length) {
      const opt = (list, key) => list.map((e, i) => `<option value="${key},${i}">${esc(e.name)}</option>`).join('');
      addHtml = `<select class="input ev-add" title="Add an event: it runs when the space is passed or landed on (or at the time chosen for board events)">
        <option value="" selected disabled>Add Event…</option>
        ${boardEvents.length ? `<optgroup label="Board Events">${opt(boardEvents, 'b')}</optgroup>` : ''}
        <optgroup label="Library Events">${opt(libraryEvents, 'l')}</optgroup></select>`;
      el._addLists = { b: boardEvents, l: libraryEvents };
    } else {
      addHtml = `<p class="hint">${Object.keys(library || {}).length ? 'No events are available for this game.' : 'Loading the event library…'}</p>`;
    }
  }
  el.innerHTML = (entries || (opts.emptyText ? `<p class="hint ev-empty">${esc(opts.emptyText)}</p>` : '')) + addHtml;

  // Wire up.
  el.querySelector('.ev-add')?.addEventListener('change', e => {
    const [key, i] = e.target.value.split(',');
    const event = el._addLists[key][+i];
    e.target.value = '';
    if (event) opts.onAdd(event);
  });
  for (const entry of el.querySelectorAll('.ev-entry')) {
    const i = +entry.dataset.i;
    const inst = events[i];
    entry.addEventListener('mouseenter', () => opts.onHover?.(i));
    entry.addEventListener('mouseleave', () => opts.onHover?.(-1));
    entry.querySelector('.ev-del')?.addEventListener('click', () => {
      opts.onHover?.(-1);
      opts.onDelete(i);
    });
    entry.querySelector('.ev-act').addEventListener('click', () => {
      if (!readonly) opts.onToggleActivation(inst, i);
    });
    for (const chip of entry.querySelectorAll('[data-param]')) wireParam(chip, inst, i, opts);
  }
}

function paramChips(event, inst, readonly) {
  let colorIndex = 0;
  const nextColor = () => `rgb(${getDistinctColor(colorIndex++).join(', ')})`;
  const values = inst.parameterValues || {};
  return (event.parameters || []).map(p => {
    const v = values[p.name];
    const set = v !== undefined && v !== null;
    const name = esc(p.name);
    switch (p.type) {
      case EventParameterType.Boolean:
        return `<button type="button" class="ev-chip" data-param="${name}" data-kind="bool" ${readonly ? 'disabled' : ''}
          title="(Boolean) ${name}: ${set ? esc(v) : 'null'}${readonly ? '' : ' (click to toggle)'}"><b>${name}:</b> ${set ? esc(String(v)) : '<i class="unset">null</i>'}</button>`;
      case EventParameterType.Number:
      case EventParameterType.PositiveNumber:
        return `<button type="button" class="ev-chip" data-param="${name}" data-kind="${p.type === '+Number' ? 'pos' : 'num'}" ${readonly ? 'disabled' : ''}
          title="(Number) ${name}: ${set ? esc(v) : 'null'}${readonly ? '' : ' (click to enter a value)'}"><b>${name}:</b> ${set ? esc(String(v)) : '<i class="unset">null</i>'}</button>`;
      case EventParameterType.Space:
        return spaceChip(p, name, set, null, nextColor, readonly);
      case EventParameterType.SpaceArray: {
        const arr = Array.isArray(v) ? v : [];
        const chips = arr.map((sv, ai) => spaceChip(p, name, sv !== undefined && sv !== null, ai, nextColor, readonly));
        if (!readonly) chips.push(spaceChip(p, name, false, arr.length, nextColor, readonly));
        return chips.join('');
      }
      default:
        return '';
    }
  }).join('');
}

function spaceChip(p, name, set, arrayIndex, nextColor, readonly) {
  const isArray = arrayIndex !== null;
  const display = isArray ? `${name}[${arrayIndex}]` : name;
  const title = `(Space) ${name}: ${set ? 'set' : 'null'}${readonly ? '' : '\nDrag to a space to associate it'}`;
  let value;
  if (set) value = `<i class="swatch" style="background:${nextColor()}"></i>set`;
  else if (isArray) value = '—';
  else value = '<i class="unset">null</i>';
  return `<span class="ev-chip ev-space${isArray && !set ? ' hypothetical' : ''}" data-param="${name}" data-kind="space"
      data-ai="${isArray ? arrayIndex : ''}" draggable="${readonly ? 'false' : 'true'}" title="${esc(title)}">
      <img src="${IMG}/events/target.png" alt=""><b>${display}:</b> ${value}
      ${isArray && set && !readonly ? '<button type="button" class="ev-arr-del" title="Remove this array entry">✕</button>' : ''}</span>`;
}

function wireParam(chip, inst, i, opts) {
  const name = chip.dataset.param;
  const kind = chip.dataset.kind;
  const values = inst.parameterValues || {};
  if (opts.readonly) return;
  if (kind === 'bool') {
    chip.addEventListener('click', () => opts.onSetParam(i, name, !values[name]));
  } else if (kind === 'num' || kind === 'pos') {
    chip.addEventListener('click', async () => {
      const positiveOnly = kind === 'pos';
      const userValue = await promptDialog(
        `Enter a${positiveOnly ? ' positive ' : ' '}numeric value for the ${name} parameter:`,
        { title: 'Event Parameter', value: values[name] ?? '' });
      if (!userValue) return; // Enter nothing, ignore response.
      const value = parseInt(userValue, 10);
      if (isNaN(value)) {
        toast('The value entered could not be parsed into a number.', 'warn');
        return;
      }
      if (positiveOnly && value <= 0) {
        toast('The value entered must be a positive number.', 'warn');
        return;
      }
      opts.onSetParam(i, name, value);
    });
  } else if (kind === 'space') {
    const arrayIndex = chip.dataset.ai === '' ? null : +chip.dataset.ai;
    chip.addEventListener('dragstart', e => {
      setEventParamDropHandler(spaceIndex => {
        if (spaceIndex < 0) return;
        if (arrayIndex !== null) {
          const newArr = [...(values[name] || [])];
          newArr[arrayIndex] = spaceIndex;
          opts.onSetParam(i, name, newArr);
        } else {
          opts.onSetParam(i, name, spaceIndex);
        }
      });
      const img = getImage('targetImg');
      if (img) e.dataTransfer.setDragImage(img, 3, 0);
      e.dataTransfer.setData('text', JSON.stringify({ isEventParamDrop: true }));
    });
    chip.addEventListener('click', e => {
      if (e.target.closest('.ev-arr-del')) return;
      toast('To associate a space with this event parameter, drag from this entry and release over the target space.');
    });
    chip.querySelector('.ev-arr-del')?.addEventListener('click', e => {
      e.stopPropagation();
      const newArr = [...(values[name] || [])];
      if (newArr.length) {
        newArr.splice(arrayIndex, 1);
        opts.onSetParam(i, name, newArr);
      }
    });
  }
}

export { isArrayEventParameterType };
