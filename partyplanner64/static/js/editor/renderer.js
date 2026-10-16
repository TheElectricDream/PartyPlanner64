// Draws the board (port of apps/partyplanner64/renderer.tsx): the background, the connections
// with their arrows, event parameter associations, selection glows and highlights, the spaces with
// their characters and badges, the selection box, and the telescope view.
import { Space, SpaceSubtype, BoardType, EventParameterType } from './constants.js';
import { spaces } from './spaces.js';
import { drawImg, getImage } from './images.js';
import {
  getConnections, isConnectedTo, getEvent, isArrayEventParameterType, forEachEventParameter,
  getDistinctColor, hexstr,
} from './board.js';

const degreesToRadians = d => (d * Math.PI) / 180;

/** Draws the connecting lines. */
export function renderConnections(ctx, board) {
  const links = board.links;
  if (!links) return;
  for (const startSpace in links) {
    const start = board.spaces[startSpace];
    if (!start) continue;
    const x1 = start.x;
    const y1 = start.y;
    for (const end of getConnections(parseInt(startSpace, 10), board)) {
      const endSpace = board.spaces[end];
      if (!endSpace) continue;
      const bidirectional = isConnectedTo(links, end, startSpace);
      if (bidirectional && parseInt(startSpace, 10) > end) continue;
      drawConnection(ctx, x1, y1, endSpace.x, endSpace.y, bidirectional);
    }
  }
}

export function drawConnection(ctx, x1, y1, x2, y2, bidirectional) {
  ctx.save();
  ctx.beginPath();
  ctx.strokeStyle = 'rgba(255, 185, 105, 0.75)';
  ctx.lineCap = 'round';
  ctx.lineWidth = 8;
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();

  // Draw the little triangle arrow on top at halfway.
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  ctx.translate(midX, midY);
  ctx.rotate(-Math.atan2(x1 - midX, y1 - midY) + Math.PI);
  ctx.fillStyle = '#A15000';
  const adjust = bidirectional ? 3 : 0;
  ctx.moveTo(-4, -2 + adjust);
  ctx.lineTo(0, 2 + adjust);
  ctx.lineTo(4, -2 + adjust);
  ctx.fill();
  if (bidirectional) {
    ctx.moveTo(-4, 2 - adjust);
    ctx.lineTo(0, -2 - adjust);
    ctx.lineTo(4, 2 - adjust);
    ctx.fill();
  }
  ctx.restore();
}

function drawAssociation(ctx, x1, y1, x2, y2, dotsColor) {
  for (const [color, width] of [['rgba(0, 0, 0, 0.5)', 6], [dotsColor, 4]]) {
    ctx.save();
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.setLineDash([1, 8]);
    ctx.lineCap = 'round';
    ctx.lineWidth = width;
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.restore();
  }
}

/** Dotted lines from the selected space to the spaces its event parameters name. */
export function renderAssociations(ctx, board, selected, library) {
  if (!selected || selected.length !== 1) return;
  const selectedSpaceIndex = selected[0];
  let lastEvent = null;
  let associationNum = 0;
  forEachEventParameter(board, library, (parameter, event, eventIndex, space, spaceIndex) => {
    if (selectedSpaceIndex !== spaceIndex) return; // Only draw associations for the selected space.
    // Reset coloring for each event.
    if (lastEvent !== event) associationNum = 0;
    lastEvent = event;
    let indices;
    const value = event.parameterValues && event.parameterValues[parameter.name];
    if (parameter.type === EventParameterType.Space) {
      if (typeof value === 'number') indices = [value];
    } else if (parameter.type === EventParameterType.SpaceArray) {
      indices = Array.isArray(value) ? value : undefined;
    }
    for (const i of indices || []) {
      const assoc = board.spaces[i];
      if (!assoc) continue;
      drawAssociation(ctx, space.x, space.y, assoc.x, assoc.y,
        `rgba(${getDistinctColor(associationNum).join(', ')}, 0.9)`);
      associationNum++;
    }
  });
}

/** Adds a glow around the selected spaces. */
export function renderSelectedSpaces(ctx, board, selected) {
  const radius = board.game === 3 ? 18 : 12;
  for (const index of selected || []) {
    const space = board.spaces[index];
    if (!space) continue;
    ctx.save();
    ctx.beginPath();
    ctx.arc(space.x, space.y, radius, 0, 2 * Math.PI);
    ctx.setLineDash([2, 2]);
    ctx.lineWidth = 2;
    ctx.fillStyle = 'rgba(47, 70, 95, 0.35)';
    ctx.strokeStyle = 'rgba(47, 70, 95, 1)';
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }
}

function highlightCircle(ctx, space, radius, fill) {
  ctx.save();
  ctx.beginPath();
  ctx.arc(space.x, space.y, radius, 0, 2 * Math.PI);
  ctx.shadowColor = 'rgba(225, 225, 225, 1)';
  ctx.shadowBlur = 2;
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.restore();
}

/** Does a strong red highlight around some spaces. */
export function highlightSpaces(ctx, board, indices) {
  const radius = board.game === 3 ? 18 : 12;
  for (const i of indices) {
    if (board.spaces[i]) highlightCircle(ctx, board.spaces[i], radius, 'rgba(255, 0, 0, 0.85)');
  }
}

/** Highlights the spaces a board event's parameters name. */
export function highlightBoardEventSpaces(ctx, board, eventInstance, library) {
  const radius = board.game === 3 ? 18 : 12;
  const event = getEvent(eventInstance.id, board, library);
  if (!event || !event.parameters) return;
  let associationNum = 0;
  for (const parameter of event.parameters) {
    const value = eventInstance.parameterValues?.[parameter.name];
    let indices;
    if (parameter.type === EventParameterType.Space && typeof value === 'number') indices = [value];
    else if (parameter.type === EventParameterType.SpaceArray && Array.isArray(value)) indices = value;
    for (const i of indices || []) {
      const space = board.spaces[i];
      if (!space) continue;
      highlightCircle(ctx, space, radius, `rgba(${getDistinctColor(associationNum).join(', ')}, 0.9)`);
      associationNum++;
    }
  }
}

function determineSpaceEventImg(space, board, library) {
  for (const spaceEvent of space.events || []) {
    const event = getEvent(spaceEvent.id, board, library);
    if (!event) return 'eventErrorImg';
    for (const parameter of event.parameters || []) {
      if (isArrayEventParameterType(parameter.type)) continue;
      if (!spaceEvent.parameterValues
        || !Object.prototype.hasOwnProperty.call(spaceEvent.parameterValues, parameter.name)) {
        return 'eventErrorImg';
      }
    }
  }
  return 'eventImg';
}

function drawCharacters(ctx, x, y, subtype, game) {
  switch (subtype) {
    case SpaceSubtype.TOAD: // the standing Toad (Millennium Star in MP3)
      if (game === 3) drawImg(ctx, 'mstarImg', x - 15, y - 22);
      else drawImg(ctx, 'toadImg', x - 9, y - 22);
      break;
    case SpaceSubtype.BOWSER:
      drawImg(ctx, 'bowserImg', x - 27, y - 45);
      break;
    case SpaceSubtype.KOOPA:
      drawImg(ctx, 'koopaImg', x - 12, y - 22);
      break;
    case SpaceSubtype.BOO:
      drawImg(ctx, 'booImg', x - 13, y - 17);
      break;
    case SpaceSubtype.GOOMBA:
      drawImg(ctx, 'goombaImg', x - 8, y - 12);
      break;
    case SpaceSubtype.BANK:
      if (game === 2) drawImg(ctx, 'bank2Img', x - 9, y - 10);
      else drawImg(ctx, 'bank3Img', x - 17, y - 20);
      break;
    case SpaceSubtype.BANKCOIN:
      drawImg(ctx, 'bankcoinImg', x - 10, y - 9);
      break;
    case SpaceSubtype.ITEMSHOP:
      if (game === 2) drawImg(ctx, 'itemShop2Img', x - 9, y - 10);
      else drawImg(ctx, 'itemShop3Img', x - 16, y - 20);
      break;
  }
}

/**
 * Draws one space.
 * opts: skipHiddenSpaces (start and invisible spaces), skipBadges (event, star and gate badges),
 * skipCharacters, debug (draw the space's index), library (for the event badges).
 */
export function drawSpace(ctx, board, space, spaceIndex, opts = {}) {
  const game = board.game || 1;
  const boardType = board.type || BoardType.NORMAL;
  const { x, y, rotation, type, subtype } = space;

  if (typeof rotation === 'number') {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(degreesToRadians(-rotation));
    ctx.translate(-x, -y);
  }

  switch (type) {
    case Space.OTHER:
      if (opts.skipHiddenSpaces) break;
      if (game === 3) spaces.drawOther3(ctx, x, y); else spaces.drawOther(ctx, x, y);
      break;
    case Space.BLUE:
      if (game === 3) spaces.drawBlue3(ctx, x, y); else spaces.drawBlue(ctx, x, y);
      break;
    case Space.RED:
      if (game === 3) spaces.drawRed3(ctx, x, y); else spaces.drawRed(ctx, x, y);
      break;
    case Space.MINIGAME:
      if (boardType === BoardType.DUEL) spaces.drawMiniGameDuel3(ctx, x, y); else spaces.drawMiniGame(ctx, x, y);
      break;
    case Space.HAPPENING:
      if (game === 3) {
        if (boardType === BoardType.DUEL) spaces.drawHappeningDuel3(ctx, x, y);
        else spaces.drawHappening3(ctx, x, y);
      } else spaces.drawHappening(ctx, x, y);
      break;
    case Space.STAR:
      if (game === 3) spaces.drawStar3(ctx, x, y); else spaces.drawStar(ctx, x, y);
      break;
    case Space.CHANCE:
      if (game === 3) spaces.drawChance3(ctx, x, y);
      else if (game === 2) spaces.drawChance2(ctx, x, y);
      else spaces.drawChance(ctx, x, y);
      break;
    case Space.START:
      if (opts.skipHiddenSpaces) break;
      if (game === 3) spaces.drawStart3(ctx, x, y); else spaces.drawStart(ctx, x, y);
      break;
    case Space.SHROOM:
      spaces.drawShroom(ctx, x, y);
      break;
    case Space.BOWSER:
      if (game === 3) spaces.drawBowser3(ctx, x, y); else spaces.drawBowser(ctx, x, y);
      break;
    case Space.ITEM:
      if (game === 3) spaces.drawItem3(ctx, x, y); else spaces.drawItem2(ctx, x, y);
      break;
    case Space.BATTLE:
      if (game === 3) spaces.drawBattle3(ctx, x, y); else spaces.drawBattle2(ctx, x, y);
      break;
    case Space.BANK:
      if (game === 3) spaces.drawBank3(ctx, x, y); else spaces.drawBank2(ctx, x, y);
      break;
    case Space.ARROW:
      spaces.drawArrow(ctx, x, y, game);
      break;
    case Space.BLACKSTAR:
      spaces.drawBlackStar2(ctx, x, y);
      break;
    case Space.GAMEGUY:
      if (boardType === BoardType.DUEL) spaces.drawGameGuyDuel3(ctx, x, y); else spaces.drawGameGuy3(ctx, x, y);
      break;
    case Space.DUEL_BASIC:
      spaces.drawDuelBasic(ctx, x, y);
      break;
    case Space.DUEL_START_BLUE:
      if (opts.skipHiddenSpaces) break;
      spaces.drawStartDuelBlue(ctx, x, y);
      break;
    case Space.DUEL_START_RED:
      if (opts.skipHiddenSpaces) break;
      spaces.drawStartDuelRed(ctx, x, y);
      break;
    case Space.DUEL_POWERUP:
      spaces.drawDuelPowerup(ctx, x, y);
      break;
    case Space.DUEL_REVERSE:
      spaces.drawDuelReverse(ctx, x, y);
      break;
    default:
      spaces.drawUnknown(ctx, x, y);
      break;
  }

  if (typeof rotation === 'number') ctx.restore();

  if (!opts.skipCharacters) drawCharacters(ctx, x, y, subtype, game);

  if (!opts.skipBadges) {
    const offset = game === 3 ? 5 : 2;
    const startOffset = game === 3 ? 16 : 12;
    if (space.events && space.events.length) {
      let iconY = y + offset;
      if (type === Space.START) iconY -= startOffset;
      drawImg(ctx, determineSpaceEventImg(space, board, opts.library), x + offset, iconY);
    }
    if (space.star) {
      let iconY = y + offset;
      if (type === Space.START) iconY -= startOffset;
      drawImg(ctx, 'starImg', x - offset - 9, iconY);
    }
    if (subtype === SpaceSubtype.GATE) {
      drawImg(ctx, 'gateImg', x - offset - 9, y + offset - 5);
    }
  }

  if (opts.debug) {
    // Draw the space's index.
    ctx.save();
    ctx.fillStyle = 'white';
    ctx.strokeStyle = 'black';
    ctx.lineWidth = 2;
    ctx.font = 'bold 6pt Courier New';
    ctx.textAlign = 'center';
    let text = String(spaceIndex);
    ctx.strokeText(text, x, y - 2);
    ctx.fillText(text, x, y - 2);
    text = hexstr(spaceIndex);
    ctx.strokeText(text, x, y + 8);
    ctx.fillText(text, x, y + 8);
    ctx.restore();
  }
}

export function renderSpaces(ctx, board, opts = {}) {
  board.spaces.forEach((space, index) => {
    if (space) drawSpace(ctx, board, space, index, opts);
  });
}

export function renderSelectionBox(ctx, box) {
  if (!box) return;
  const [xs, ys, xf, yf] = box;
  ctx.save();
  ctx.beginPath();
  ctx.fillStyle = 'rgba(47, 70, 95, 0.5)';
  ctx.strokeStyle = 'rgba(47, 70, 95, 1)';
  const args = [Math.min(xs, xf), Math.min(ys, yf), Math.abs(xs - xf), Math.abs(ys - yf)];
  ctx.fillRect(...args);
  ctx.strokeRect(...args);
  ctx.restore();
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('The background image could not be loaded.'));
    img.src = src;
  });
}

/**
 * Takes a screenshot of a board (screenshot.tsx takeScreeny): a canvas the size of the board.
 * opts: renderConnections, renderCharacters, renderHiddenSpaces, renderBadges, bgSrc, library.
 */
export async function takeScreeny(board, opts = {}) {
  const { width, height } = board.bg;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  // First fill black, to mimic the game and the editor's black background.
  ctx.fillStyle = 'black';
  ctx.fillRect(0, 0, width, height);
  const src = opts.bgSrc || board.bg.src;
  if (src && typeof src === 'string') {
    try {
      ctx.drawImage(await loadImage(src), 0, 0, width, height);
    } catch (e) {
      console.error(e);
    }
  }
  if (opts.renderConnections) renderConnections(ctx, board);
  renderSpaces(ctx, board, {
    skipCharacters: !opts.renderCharacters,
    skipHiddenSpaces: !opts.renderHiddenSpaces,
    skipBadges: !opts.renderBadges,
    library: opts.library,
  });
  return canvas;
}

// The telescope: how the board looks through the game's camera.

const N64_SCREEN_WIDTH = 320;
const N64_SCREEN_HEIGHT = 240;

function getZoomedN64SizeForTelescope(game) {
  let w = 1;
  let h = 1;
  if (game === 3) {
    w = 0.785;
    h = 0.805;
  }
  return { N64_WIDTH_ZOOMED: N64_SCREEN_WIDTH * w, N64_HEIGHT_ZOOMED: N64_SCREEN_HEIGHT * h };
}

export function addRecommendedBoundaryLine(board, canvas) {
  const ctx = canvas.getContext('2d');
  ctx.lineWidth = 1;
  ctx.strokeStyle = 'rgba(0, 0, 0, 0.5)';
  const { width, height } = board.bg;
  const { N64_WIDTH_ZOOMED, N64_HEIGHT_ZOOMED } = getZoomedN64SizeForTelescope(board.game);
  ctx.strokeRect(N64_WIDTH_ZOOMED / 2, N64_HEIGHT_ZOOMED / 2, width - N64_WIDTH_ZOOMED, height - N64_HEIGHT_ZOOMED);
}

/** Draws the telescope view for the pointer at (clickX, clickY) in board coordinates. */
export function drawTelescope(canvas, screenshot, board, clickX, clickY) {
  const ctx = canvas.getContext('2d');
  const { width, height } = board.bg;
  const { N64_WIDTH_ZOOMED, N64_HEIGHT_ZOOMED } = getZoomedN64SizeForTelescope(board.game);

  // The cutout from the board image, bounded like the game camera is.
  let sx = Math.max(0, clickX - N64_WIDTH_ZOOMED / 2);
  let sy = Math.max(0, clickY - N64_HEIGHT_ZOOMED / 2);
  if (width - sx < N64_WIDTH_ZOOMED) sx = width - N64_WIDTH_ZOOMED;
  if (height - sy < N64_HEIGHT_ZOOMED) sy = height - N64_HEIGHT_ZOOMED;
  ctx.drawImage(screenshot, sx, sy, N64_WIDTH_ZOOMED, N64_HEIGHT_ZOOMED, 0, 0, width, height);

  // Simulate the black bars the game has, which restrict the viewing area further.
  const horzBarHeight = 12 * (height / N64_SCREEN_HEIGHT);
  const vertBarWidth = 16 * (width / N64_SCREEN_WIDTH);
  ctx.fillStyle = 'black';
  ctx.fillRect(0, 0, width, horzBarHeight); // top
  ctx.fillRect(width - vertBarWidth, 0, vertBarWidth, height); // right
  ctx.fillRect(0, height - horzBarHeight, width, horzBarHeight); // bottom
  ctx.fillRect(0, 0, vertBarWidth, height); // left
  return [sx, sy];
}

/**
 * The layered view of a board: a black-backed image and canvases, all in board pixels inside
 * `stage` (which the editor scales for zoom).
 */
export class BoardView {
  constructor(stage) {
    this.stage = stage;
    this.bg = document.createElement('img');
    this.bg.className = 'editor-bg';
    this.bg.alt = '';
    this.bg.draggable = false;
    stage.append(this.bg);
    const layer = cls => {
      const c = document.createElement('canvas');
      c.className = 'editor-layer ' + cls;
      stage.append(c);
      return c;
    };
    this.lines = layer('editor-lines');
    this.assoc = layer('editor-assoc');
    this.select = layer('editor-select');
    this.spaces = layer('editor-spaces');
    this.box = layer('editor-box');
    this.telescope = layer('editor-telescope');
    this.telescope.hidden = true;
    this.width = 0;
    this.height = 0;
    this.screenshot = null;
  }

  /** The canvas that receives the pointer. */
  get input() {
    return this.box;
  }

  setSize(width, height) {
    if (width === this.width && height === this.height) return;
    this.width = width;
    this.height = height;
    this.stage.style.width = width + 'px';
    this.stage.style.height = height + 'px';
    for (const c of [this.lines, this.assoc, this.select, this.spaces, this.box, this.telescope]) {
      c.width = width;
      c.height = height;
    }
    this.bg.width = width;
    this.bg.height = height;
  }

  setBackground(src) {
    const s = typeof src === 'string' ? src : '';
    if (this.bg.getAttribute('src') !== s) {
      if (s) this.bg.setAttribute('src', s); else this.bg.removeAttribute('src');
    }
  }

  /** Draws everything for the state: { board, selected, library, debug, highlighted, ... }. */
  render(st) {
    const board = st.board;
    if (!board) return;
    this.setSize(board.bg.width, board.bg.height);
    this.setBackground(st.overrideBg || board.bg.src);
    this.renderLines(st);
    this.renderAssociations(st);
    this.renderSelection(st);
    this.renderSpaces(st);
    this.renderBox(st);
  }

  ctx(c) {
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    return ctx;
  }

  renderLines(st) {
    const ctx = this.ctx(this.lines);
    renderConnections(ctx, st.board);
    for (const [x1, y1, x2, y2] of st.tempConnections || []) drawConnection(ctx, x1, y1, x2, y2, false);
  }

  renderAssociations(st) {
    renderAssociations(this.ctx(this.assoc), st.board, st.selected, st.library);
  }

  renderSelection(st) {
    const ctx = this.ctx(this.select);
    renderSelectedSpaces(ctx, st.board, st.selected);
    if (st.highlighted) highlightSpaces(ctx, st.board, st.highlighted);
    if (st.hoveredBoardEvent >= 0) {
      const ev = st.board.boardevents?.[st.hoveredBoardEvent];
      if (ev) highlightBoardEventSpaces(ctx, st.board, ev, st.library);
    }
  }

  renderSpaces(st) {
    renderSpaces(this.ctx(this.spaces), st.board, { library: st.library, debug: st.debug });
  }

  renderBox(st) {
    renderSelectionBox(this.ctx(this.box), st.selectionBox);
  }

  /** Shows or hides the telescope view (a fresh screenshot of the board is taken). */
  async setTelescope(on, st) {
    this.telescope.hidden = !on;
    if (!on) return;
    const ctx = this.ctx(this.telescope);
    addRecommendedBoundaryLine(st.board, this.telescope);
    void ctx;
    const shot = await takeScreeny(st.board, {
      renderCharacters: true, bgSrc: st.overrideBg || st.board.bg.src, library: st.library,
    });
    addRecommendedBoundaryLine(st.board, shot);
    this.screenshot = shot;
  }

  telescopeAt(st, x, y) {
    if (!this.screenshot) return null;
    return drawTelescope(this.telescope, this.screenshot, st.board, x, y);
  }

  telescopeLeave(st) {
    this.ctx(this.telescope);
    addRecommendedBoundaryLine(st.board, this.telescope);
  }
}

export { getImage };
