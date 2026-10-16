// The game's enums and the editor's tool lists, as in packages/lib/types.ts, toolbar.tsx,
// spaceproperties.tsx and rightclick.tsx.

export const Space = {
  OTHER: 0, BLUE: 1, RED: 2, MINIGAME: 3, HAPPENING: 4, STAR: 5, CHANCE: 6, START: 7, SHROOM: 8,
  BOWSER: 9, ITEM: 10, BATTLE: 11, BANK: 12, ARROW: 13, BLACKSTAR: 14, GAMEGUY: 15,
  DUEL_BASIC: 16, DUEL_START_BLUE: 17, DUEL_START_RED: 18, DUEL_POWERUP: 19, DUEL_REVERSE: 20,
};

export const SpaceSubtype = {
  TOAD: 0, BOWSER: 1, KOOPA: 2, BOO: 3, GOOMBA: 4, BANK: 5, BANKCOIN: 6, ITEMSHOP: 7, GATE: 8,
};

export const BoardType = { NORMAL: 'NORMAL', DUEL: 'DUEL' };

export const BoardAudioType = { InGame: 0, Custom: 1 };

export const CostumeType = { NORMAL: 0, WESTERN: 1, PIRATE: 2, HORROR: 3, SPACE: 4, MYSTERY: 5 };

export const EventCodeLanguage = { MIPS: 0, C: 1 };

export const EditorEventActivationType = {
  WALKOVER: 1, LANDON: 3, BEFORE_DICE_ROLL: -5, BEFORE_PLAYER_TURN: -4, AFTER_TURN: -3,
  BEFORE_TURN: -2, BEGINORWALKOVER: 8,
};

export const EventParameterType = {
  Boolean: 'Boolean', Number: 'Number', PositiveNumber: '+Number', NumberArray: 'Number[]',
  Space: 'Space', SpaceArray: 'Space[]',
};

/** The editor's tools (Action in types.ts). */
export const Action = {
  MOVE: 0, LINE: 1, LINE_STICKY: 2, ROTATE: 3, ERASE: 4,
  ADD_OTHER: 16, ADD_BLUE: 17, ADD_RED: 18, ADD_MINIGAME: 19, ADD_HAPPENING: 20, ADD_STAR: 21,
  ADD_BLACKSTAR: 21.2, ADD_START: 21.3, ADD_CHANCE: 22, ADD_SHROOM: 23, ADD_BOWSER: 24,
  ADD_TOAD_CHARACTER: 25, ADD_BOWSER_CHARACTER: 26, ADD_KOOPA_CHARACTER: 27, ADD_BOO_CHARACTER: 28,
  ADD_ITEM: 29, ADD_BATTLE: 30, ADD_BANK: 31, ADD_GAMEGUY: 32, ADD_ARROW: 32.2, MARK_STAR: 33,
  MARK_GATE: 33.1, ADD_BANK_SUBTYPE: 34, ADD_BANKCOIN_SUBTYPE: 35, ADD_ITEMSHOP_SUBTYPE: 36,
  ADD_DUEL_BASIC: 37, ADD_DUEL_REVERSE: 38, ADD_DUEL_POWERUP: 39, ADD_DUEL_START_BLUE: 40,
  ADD_DUEL_START_RED: 41, TELESCOPE: 42,
};

export const IMG = '/static/img';
const tb = name => `${IMG}/toolbar/${name}.png`;

/** Toolbar icons by name (img/toolbar). */
export const ToolbarImages = new Proxy({}, { get: (_, name) => tb(String(name)) });

/** The editing tools shown in the viewer toolbar, by game (rotate only in MP2 and MP3 normal boards). */
export function getEditTools(game, boardType) {
  const tools = [
    { name: 'Move', title: 'Move spaces: drag spaces to move them, or drag on the board to select several (M)', icon: tb('move'), type: Action.MOVE, key: 'm' },
    { name: 'Line', title: 'Connect spaces: drag from one space to another to link them (L)', icon: tb('line'), type: Action.LINE, key: 'l' },
    { name: 'Sticky Line', title: 'Connect multiple spaces in one click: drag across spaces to link each to the next (K)', icon: tb('stickyline'), type: Action.LINE_STICKY, key: 'k' },
    { name: 'Erase', title: 'Erase spaces and lines: click or drag over them (E)', icon: tb('eraser'), type: Action.ERASE, key: 'e' },
    { name: 'Rotate', title: 'Rotate arrow spaces: drag from an arrow space toward where it should point (R)', icon: tb('rotate'), type: Action.ROTATE, key: 'r' },
    { name: 'Telescope', title: 'Telescope tool: move your cursor over the map to visualize how it will look during gameplay (T)', icon: tb('telescope'), type: Action.TELESCOPE, key: 't' },
  ];
  const rotate = game !== 1 && !(game === 3 && boardType === BoardType.DUEL);
  return tools.filter(t => t.type !== Action.ROTATE || rotate);
}

// The space palette (toolbar.tsx, after the editing tools). group: 'space' or 'character'.
const S = (name, icon, type, opts = {}) => ({ name, icon: tb(icon), type, group: 'space', draggable: true, ...opts });
const C = (name, icon, type, opts = {}) => ({ name, icon: tb(icon), type, group: 'character', draggable: true, ...opts });

const mp1Palette = [
  S('Add blue space', 'blue', Action.ADD_BLUE),
  S('Add red space', 'red', Action.ADD_RED),
  S('Add happening space', 'happening', Action.ADD_HAPPENING),
  S('Add chance time space', 'chance', Action.ADD_CHANCE),
  S('Add Bowser space', 'bowser', Action.ADD_BOWSER),
  S('Add Mini-Game space', 'minigame', Action.ADD_MINIGAME),
  S('Add shroom space', 'shroom', Action.ADD_SHROOM),
  S('Add invisible space', 'other', Action.ADD_OTHER),
  S('Add star space (decoration)', 'star', Action.ADD_STAR, { advanced: true }),
  S('Add start space', 'start', Action.ADD_START, { advanced: true }),
  C('Add Toad', 'toad', Action.ADD_TOAD_CHARACTER),
  C('Add Boo', 'boo', Action.ADD_BOO_CHARACTER),
  C('Add Bowser', 'bowsercharacter', Action.ADD_BOWSER_CHARACTER),
  C('Add Koopa Troopa', 'koopa', Action.ADD_KOOPA_CHARACTER),
  C('Mark space as hosting star', 'markstar', Action.MARK_STAR, { draggable: false }),
];

const mp2Palette = [
  S('Add blue space', 'blue', Action.ADD_BLUE),
  S('Add red space', 'red', Action.ADD_RED),
  S('Add happening space', 'happening', Action.ADD_HAPPENING),
  S('Add chance time space', 'chance2', Action.ADD_CHANCE),
  S('Add Bowser space', 'bowser', Action.ADD_BOWSER),
  S('Add item space', 'item', Action.ADD_ITEM),
  S('Add battle space', 'battle', Action.ADD_BATTLE),
  S('Add bank space', 'bank', Action.ADD_BANK),
  S('Add invisible space', 'other', Action.ADD_OTHER),
  S('Add star space (decoration)', 'star', Action.ADD_STAR, { advanced: true }),
  S('Add black star space (decoration)', 'blackstar', Action.ADD_BLACKSTAR, { advanced: true }),
  S('Add start space', 'start', Action.ADD_START, { advanced: true }),
  S('Add arrow space', 'arrow', Action.ADD_ARROW),
  C('Add Toad', 'toad', Action.ADD_TOAD_CHARACTER),
  C('Add Boo', 'boo', Action.ADD_BOO_CHARACTER),
  C('Add bank', 'banksubtype2', Action.ADD_BANK_SUBTYPE),
  C('Add bank coin stack', 'bankcoinsubtype', Action.ADD_BANKCOIN_SUBTYPE),
  C('Add item shop', 'itemshopsubtype2', Action.ADD_ITEMSHOP_SUBTYPE),
  C('Mark space as hosting star', 'markstar', Action.MARK_STAR, { draggable: false }),
];

const mp3Palette = [
  S('Add blue space', 'blue3', Action.ADD_BLUE),
  S('Add red space', 'red3', Action.ADD_RED),
  S('Add happening space', 'happening3', Action.ADD_HAPPENING),
  S('Add chance time space', 'chance3', Action.ADD_CHANCE),
  S('Add Bowser space', 'bowser3', Action.ADD_BOWSER),
  S('Add item space', 'item3', Action.ADD_ITEM),
  S('Add battle space', 'battle3', Action.ADD_BATTLE),
  S('Add bank space', 'bank3', Action.ADD_BANK),
  S('Add Game Guy space', 'gameguy', Action.ADD_GAMEGUY),
  S('Add invisible space', 'other', Action.ADD_OTHER),
  S('Add star space (decoration)', 'star', Action.ADD_STAR, { advanced: true }),
  S('Add start space', 'start', Action.ADD_START, { advanced: true }),
  S('Add arrow space', 'arrow', Action.ADD_ARROW),
  C('Add Millennium Star', 'mstar', Action.ADD_TOAD_CHARACTER),
  C('Add Boo', 'boo', Action.ADD_BOO_CHARACTER),
  C('Add bank', 'banksubtype', Action.ADD_BANK_SUBTYPE),
  C('Add bank coin stack', 'bankcoinsubtype', Action.ADD_BANKCOIN_SUBTYPE),
  C('Add item shop', 'itemshopsubtype', Action.ADD_ITEMSHOP_SUBTYPE),
  C('Mark space as hosting star', 'markstar', Action.MARK_STAR, { draggable: false }),
  C('Mark space as Skeleton Key gate', 'markgate', Action.MARK_GATE, { draggable: false }),
];

const mp3DuelPalette = [
  S('Add basic space', 'basic3', Action.ADD_DUEL_BASIC),
  S('Add Mini-Game space', 'minigameduel3', Action.ADD_MINIGAME),
  S('Add reverse space', 'reverse3', Action.ADD_DUEL_REVERSE),
  S('Add happening space', 'happeningduel3', Action.ADD_HAPPENING),
  S('Add Game Guy space', 'gameguyduel', Action.ADD_GAMEGUY),
  S('Add power-up space', 'powerup', Action.ADD_DUEL_POWERUP),
  S('Add invisible space', 'other', Action.ADD_OTHER),
  S('Add blue start space', 'startblue', Action.ADD_DUEL_START_BLUE, { advanced: true }),
  S('Add red start space', 'startred', Action.ADD_DUEL_START_RED, { advanced: true }),
];

/** The space palette for a game and board type; advanced items only with ui.advanced. */
export function getPalette(game, boardType, advanced) {
  let items;
  switch (game) {
    case 1: items = mp1Palette; break;
    case 2: items = mp2Palette; break;
    default: items = boardType === BoardType.DUEL ? mp3DuelPalette : mp3Palette; break;
  }
  return advanced ? items : items.filter(i => !i.advanced);
}

// The type and subtype toggles of the space properties and the right-click menu.
const T = (name, icon, type, opts = {}) => ({ name, icon: tb(icon), type, ...opts });
const ST = (name, icon, subtype) => ({ name, icon: tb(icon), subtype });

const types1 = [
  T('Change to blue space', 'blue', Space.BLUE),
  T('Change to red space', 'red', Space.RED),
  T('Change to happening space', 'happening', Space.HAPPENING),
  T('Change to chance time space', 'chance', Space.CHANCE),
  T('Change to Mini-Game space', 'minigame', Space.MINIGAME),
  T('Change to shroom space', 'shroom', Space.SHROOM),
  T('Change to Bowser space', 'bowser', Space.BOWSER),
  T('Change to invisible space', 'other', Space.OTHER),
  T('Change to star space', 'star', Space.STAR, { advanced: true }),
  T('Change to start space', 'start', Space.START, { advanced: true }),
];
const subtypes1 = [
  ST('Show Toad', 'toad', SpaceSubtype.TOAD),
  ST('Show Boo', 'boo', SpaceSubtype.BOO),
  ST('Show Bowser', 'bowsercharacter', SpaceSubtype.BOWSER),
  ST('Show Koopa Troopa', 'koopa', SpaceSubtype.KOOPA),
];
const types2 = [
  T('Change to blue space', 'blue', Space.BLUE),
  T('Change to red space', 'red', Space.RED),
  T('Change to happening space', 'happening', Space.HAPPENING),
  T('Change to chance time space', 'chance2', Space.CHANCE),
  T('Change to Bowser space', 'bowser', Space.BOWSER),
  T('Change to item space', 'item', Space.ITEM),
  T('Change to battle space', 'battle', Space.BATTLE),
  T('Change to bank space', 'bank', Space.BANK),
  T('Change to invisible space', 'other', Space.OTHER),
  T('Change to star space', 'star', Space.STAR, { advanced: true }),
  T('Change to black star space', 'blackstar', Space.BLACKSTAR, { advanced: true }),
  T('Change to start space', 'start', Space.START, { advanced: true }),
  T('Change to arrow space', 'arrow', Space.ARROW),
];
const subtypes2 = [
  ST('Show Toad', 'toad', SpaceSubtype.TOAD),
  ST('Show Boo', 'boo', SpaceSubtype.BOO),
  ST('Show bank', 'banksubtype2', SpaceSubtype.BANK),
  ST('Show bank coin stack', 'bankcoinsubtype', SpaceSubtype.BANKCOIN),
  ST('Show item shop', 'itemshopsubtype2', SpaceSubtype.ITEMSHOP),
];
const types3 = [
  T('Change to blue space', 'blue3', Space.BLUE),
  T('Change to red space', 'red3', Space.RED),
  T('Change to happening space', 'happening3', Space.HAPPENING),
  T('Change to chance time space', 'chance3', Space.CHANCE),
  T('Change to Bowser space', 'bowser3', Space.BOWSER),
  T('Change to item space', 'item3', Space.ITEM),
  T('Change to battle space', 'battle3', Space.BATTLE),
  T('Change to bank space', 'bank3', Space.BANK),
  T('Change to Game Guy space', 'gameguy', Space.GAMEGUY),
  T('Change to invisible space', 'other', Space.OTHER),
  T('Change to star space', 'star', Space.STAR, { advanced: true }),
  T('Change to start space', 'start', Space.START, { advanced: true }),
  T('Change to arrow space', 'arrow', Space.ARROW),
];
const subtypes3 = [
  ST('Show Millennium Star', 'mstar', SpaceSubtype.TOAD),
  ST('Show Boo', 'boo', SpaceSubtype.BOO),
  ST('Show bank', 'banksubtype', SpaceSubtype.BANK),
  ST('Show bank coin stack', 'bankcoinsubtype', SpaceSubtype.BANKCOIN),
  ST('Show item shop', 'itemshopsubtype', SpaceSubtype.ITEMSHOP),
];
const types3Duel = [
  T('Change to basic space', 'basic3', Space.DUEL_BASIC),
  T('Change to Mini-Game space', 'minigameduel3', Space.MINIGAME),
  T('Change to reverse space', 'reverse3', Space.DUEL_REVERSE),
  T('Change to happening space', 'happeningduel3', Space.HAPPENING),
  T('Change to Game Guy space', 'gameguyduel', Space.GAMEGUY),
  T('Change to power-up space', 'powerup', Space.DUEL_POWERUP),
  T('Change to invisible space', 'other', Space.OTHER),
  T('Change to blue start space', 'startblue', Space.DUEL_START_BLUE, { advanced: true }),
  T('Change to red start space', 'startred', Space.DUEL_START_RED, { advanced: true }),
];

export function getTypeToggles(game, boardType, advanced) {
  const items = game === 1 ? types1 : game === 2 ? types2 : boardType === BoardType.DUEL ? types3Duel : types3;
  return advanced ? items : items.filter(i => !i.advanced);
}

export function getSubtypeToggles(game, boardType) {
  return game === 1 ? subtypes1 : game === 2 ? subtypes2 : boardType === BoardType.DUEL ? [] : subtypes3;
}

/** Names of the space types, for titles and counts. */
export const SpaceNames = {
  [Space.OTHER]: 'Invisible', [Space.BLUE]: 'Blue', [Space.RED]: 'Red', [Space.MINIGAME]: 'Mini-Game',
  [Space.HAPPENING]: 'Happening', [Space.STAR]: 'Star', [Space.CHANCE]: 'Chance Time', [Space.START]: 'Start',
  [Space.SHROOM]: 'Mushroom', [Space.BOWSER]: 'Bowser', [Space.ITEM]: 'Item', [Space.BATTLE]: 'Battle',
  [Space.BANK]: 'Bank', [Space.ARROW]: 'Arrow', [Space.BLACKSTAR]: 'Black Star', [Space.GAMEGUY]: 'Game Guy',
  [Space.DUEL_BASIC]: 'Basic', [Space.DUEL_START_BLUE]: 'Blue Start', [Space.DUEL_START_RED]: 'Red Start',
  [Space.DUEL_POWERUP]: 'Power-Up', [Space.DUEL_REVERSE]: 'Reverse',
};

export const SubtypeNames = {
  [SpaceSubtype.TOAD]: 'Toad', [SpaceSubtype.BOWSER]: 'Bowser', [SpaceSubtype.KOOPA]: 'Koopa Troopa',
  [SpaceSubtype.BOO]: 'Boo', [SpaceSubtype.GOOMBA]: 'Goomba', [SpaceSubtype.BANK]: 'Bank',
  [SpaceSubtype.BANKCOIN]: 'Bank Coin Stack', [SpaceSubtype.ITEMSHOP]: 'Item Shop', [SpaceSubtype.GATE]: 'Gate',
};

/** The main background's size by game (boardproperties.tsx BGSelect). */
export function mainBgSize(game, boardType) {
  if (game === 1) return [960, 720];
  return boardType === BoardType.DUEL ? [896, 672] : [1152, 864];
}

export const GameNames = { 1: 'Mario Party 1', 2: 'Mario Party 2', 3: 'Mario Party 3' };
