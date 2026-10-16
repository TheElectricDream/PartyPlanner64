// Read-only helpers over board JSON (ports of packages/lib/boards.ts and events.ts functions the
// editor's drawing and panels need). Edits are made by the server (POST /api/board/op).
import { Space, EventParameterType } from './constants.js';

const GAME_VERSION = {
  CLBE: 1, CLBJ: 1, NLBP: 1, NMWE: 2, NMWJ: 2, NMWP: 2, NMVE: 3, NMVJ: 3, NMVP: 3,
  MP1_USA: 1, MP1_JPN: 1, MP1_PAL: 1, MP2_USA: 2, MP2_JPN: 2, MP2_PAL: 2, MP3_USA: 3, MP3_JPN: 3, MP3_PAL: 3,
};

/** Space indices a space links to. */
export function getConnections(spaceIndex, board) {
  if (spaceIndex < 0) return null;
  if (!board.links) return [];
  const l = board.links[spaceIndex];
  if (Array.isArray(l)) return l.slice(0);
  if (typeof l === 'number') return [l];
  return [];
}

export function isConnectedTo(links, start, end) {
  const startLinks = links[start];
  if (Array.isArray(startLinks)) return startLinks.indexOf(parseInt(end, 10)) >= 0;
  return startLinks == end; // eslint-disable-line eqeqeq -- Can be string vs int.
}

export function hasConnection(startIdx, endIdx, board) {
  const l = board.links[startIdx];
  if (Array.isArray(l)) {
    if (endIdx === '*' || endIdx === undefined) return true;
    return l.indexOf(endIdx) >= 0;
  }
  if (l !== undefined && l !== null) {
    if (endIdx === '*' || endIdx === undefined) return true;
    return l === endIdx;
  }
  return false;
}

export function getStartSpaceIndex(board) {
  for (let i = 0; i < board.spaces.length; i++) {
    if (board.spaces[i] && board.spaces[i].type === Space.START) return i;
  }
  return -1;
}

export function getSpacesOfType(type, board) {
  const result = [];
  board.spaces.forEach((s, i) => { if (s && s.type === type) result.push(i); });
  return result;
}

/** Spaces where a path ends (boards.ts getDeadEnds). */
export function getDeadEnds(board) {
  const deadEnds = [];
  const seen = new Set();
  const links = board.links || {};

  function checkDeadEnd(spaceIndex) {
    if (seen.has(spaceIndex)) return false; // We have reached a previous space - no dead end.
    if (!Object.prototype.hasOwnProperty.call(links, spaceIndex)) {
      deadEnds.push(spaceIndex);
      return true;
    }
    seen.add(spaceIndex);
    const nextSpaces = links[spaceIndex];
    if (Array.isArray(nextSpaces)) {
      for (const next of nextSpaces) {
        if (checkDeadEnd(next)) return true;
      }
    } else if (checkDeadEnd(nextSpaces)) {
      return true;
    }
    return undefined;
  }

  // Build a reverse lookup of space to _pointing_ spaces.
  const pointingMap = {};
  board.spaces.forEach((s, i) => { if (s) pointingMap[i] = []; });
  for (const startIdx in links) {
    for (const end of getConnections(parseInt(startIdx, 10), board)) {
      if (pointingMap[end]) pointingMap[end].push(Number(startIdx));
    }
  }

  const startIdx = getStartSpaceIndex(board);
  if (startIdx >= 0) checkDeadEnd(startIdx);

  for (let s = 0; s < board.spaces.length; s++) {
    if (!board.spaces[s] || seen.has(s)) continue;
    // As the original: hasConnection(s, null) is never true, so only paths from the start
    // space are followed.
    if (!pointingMap[s].length && hasConnection(s, null, board)) checkDeadEnd(s);
  }
  return deadEnds;
}

/** Distance from (tx, ty) to the line through two points (utils/number.ts lineDistance). */
export function lineDistance(tx, ty, x1, y1, x2, y2) {
  return Math.abs((y2 - y1) * tx - (x2 - x1) * ty + x2 * y1 - y2 * x1)
    / Math.sqrt(Math.pow(y2 - y1, 2) + Math.pow(x2 - x1, 2));
}

function shouldEraseLine(a, b, x, y) {
  if (x > a.x && x > b.x) return false;
  if (x < a.x && x < b.x) return false;
  if (y > a.y && y > b.y) return false;
  if (y < a.y && y < b.y) return false;
  return lineDistance(x, y, a.x, a.y, b.x, b.y) <= 4;
}

/** True if eraseConnections at (x, y) would remove a line (so the op is worth sending). */
export function lineAt(board, x, y) {
  for (const start in board.links || {}) {
    const a = board.spaces[start];
    for (const end of getConnections(parseInt(start, 10), board)) {
      const b = board.spaces[end];
      if (a && b && shouldEraseLine(a, b, x, y)) return true;
    }
  }
  return false;
}

export function pointFallsWithin(x, y, xs, ys, xf, yf) {
  const [minX, maxX] = [Math.min(xs, xf), Math.max(xs, xf)];
  const [minY, maxY] = [Math.min(ys, yf), Math.max(ys, yf)];
  return x >= minX && x <= maxX && y >= minY && y <= maxY;
}

/** Radians counter-clockwise from the +x axis (utils/number.ts determineAngle). */
export function determineAngle(xOrigin, yOrigin, x, y) {
  const angleRadians = Math.atan2(y - yOrigin, x - xOrigin);
  if (angleRadians < 0) return Math.abs(angleRadians);
  return Math.abs(angleRadians - Math.PI) + Math.PI;
}

// Custom events kept in the board (board.events): read their header like customevents.ts.

function readDiscreteProperty(code, name) {
  const m = new RegExp('^\\s*[;\\/]+\\s*' + name + ':(.+)$', 'im').exec(code);
  return m ? m[1] : null;
}

function readDiscretePropertySet(code, name) {
  const regex = new RegExp('^\\s*[;\\/]+\\s*' + name + ':(.+)$', 'gim');
  const matches = [];
  let m;
  while ((m = regex.exec(code))) matches.push(m[1].trim());
  return matches;
}

const PARAM_TYPES = Object.values(EventParameterType);

/** The board's copy of a custom event: { language, code } (boards.ts getBoardEvent). */
export function getBoardEvent(board, eventId) {
  const e = board.events && board.events[eventId];
  if (typeof e === 'string') return { language: 0, code: e };
  return e || null;
}

/** An event object from custom event code (customevents.ts createCustomEvent, the header only). */
export function parseCustomEvent(language, code) {
  const name = (readDiscreteProperty(code, 'NAME') || '').trim();
  const games = (readDiscreteProperty(code, 'GAMES') || '').trim().split(',').map(s => s.trim()).filter(Boolean);
  const parameters = [];
  for (const entry of readDiscretePropertySet(code, 'PARAM')) {
    const pieces = entry.split('|');
    if (pieces.length !== 2) continue;
    const [type, pname] = pieces;
    if (PARAM_TYPES.includes(type) && /^[\w?!]*$/.test(pname) && pname) parameters.push({ name: pname, type });
  }
  return {
    id: name, name, custom: true, language, code,
    activationType: 3,
    executionType: (readDiscreteProperty(code, 'EXECUTION') || '').trim() === 'Process' ? 2 : 1,
    supportedGames: games, parameters,
  };
}

/**
 * The event for an instance: the board's own copy of a custom event first, then the library
 * (events.ts getEvent). library: { id: event }.
 */
export function getEvent(eventId, board, library) {
  const boardEvent = board && getBoardEvent(board, eventId);
  if (boardEvent) return parseCustomEvent(boardEvent.language, boardEvent.code);
  return library ? library[eventId] : undefined;
}

export function supportedGamesMatch(supportedGames, gameVersion) {
  return (supportedGames || []).some(g => (GAME_VERSION[g] || g) === gameVersion);
}

/** Library events usable on a board (events.ts getAvailableEvents). */
export function getAvailableEvents(board, library) {
  return Object.values(library || {}).filter(e =>
    supportedGamesMatch(e.supportedGames, board.game || 1) && !e.fakeEvent);
}

export function isArrayEventParameterType(type) {
  return String(type).endsWith('[]');
}

/** Calls fn(parameter, eventInstance, eventIndex, space, spaceIndex) (boards.ts forEachEventParameter). */
export function forEachEventParameter(board, library, fn) {
  const visit = (inst, i, space, s) => {
    const ev = getEvent(inst.id, board, library);
    if (ev && ev.parameters) for (const p of ev.parameters) fn(p, inst, i, space, s);
  };
  const be = board.boardevents || [];
  for (let i = be.length - 1; i >= 0; i--) visit(be[i], i);
  board.spaces.forEach((space, s) => {
    const evs = space && space.events;
    if (evs) for (let i = evs.length - 1; i >= 0; i--) visit(evs[i], i, space, s);
  });
}

/** An event instance as stored in a board (events.ts createEventInstance). */
export function createEventInstance(event, args = {}) {
  const inst = { id: event.id, activationType: event.activationType, executionType: event.executionType, ...args };
  if (event.custom) inst.custom = true;
  return inst;
}

/** The activation type a new space event gets (spaceproperties.tsx getDefaultActivationType). */
export function getDefaultActivationType(space) {
  switch (space.type) {
    // These spaces are not solid, so default to passing.
    case Space.OTHER:
    case Space.START:
    case Space.ARROW:
    case Space.STAR:
    case Space.BLACKSTAR:
      return 1;
  }
  return 3;
}

export function supportsAnimationBackgrounds(board) {
  return board.game === 2;
}

export function supportsAdditionalBackgrounds(board) {
  return board.game !== 2;
}

const kellyColors = [
  [166, 189, 215], [128, 62, 117], [255, 179, 0], [0, 83, 138], [255, 104, 0], [129, 112, 102],
  [193, 0, 32], [206, 162, 98], [0, 125, 52], [246, 118, 142], [255, 122, 92], [83, 55, 122],
  [255, 142, 0], [179, 40, 81], [244, 200, 0], [127, 24, 13], [147, 170, 0], [89, 51, 21],
  [241, 58, 19], [35, 44, 22],
];

/** Returns a somewhat distinct color based on index key (utils/colors.ts). */
export function getDistinctColor(index) {
  return kellyColors[index % kellyColors.length];
}

/** Strips the game's text formatting (<COLOR> tags and image characters) for plain display. */
export function plainText(text) {
  return String(text || '').replace(/<(DEFAULT|BLACK|WHITE|RED|GREEN|BLUE|PURPLE|YELLOW)>/g, '')
    .replace(/[　-〕]/g, '').replace(/\n/g, ' ');
}

export function hexstr(n) {
  return '0x' + (n >>> 0).toString(16).toUpperCase();
}
