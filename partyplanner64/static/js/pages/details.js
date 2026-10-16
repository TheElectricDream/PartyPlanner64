// The Details page: the board's name and description, difficulty, costumes, music, images,
// backgrounds, the code that picks backgrounds and music, and statistics
// (views/details.tsx, views/details/stats.tsx, views/basiccodeeditorview.tsx).
import { $, $$, api, esc, act, toast, dialog, confirmDialog, promptDialog, pickFile, readDataURL, loadCss } from '../api.js';
import {
  Space, BoardType, BoardAudioType, CostumeType, EventCodeLanguage, IMG, ToolbarImages as TI, mainBgSize,
  GameNames,
} from '../editor/constants.js';
import { store } from '../editor/store.js';
import { createRichText } from '../editor/richtext.js';
import { copyCurrentBoard } from '../editor/boards.js';
import { supportsAnimationBackgrounds, supportsAdditionalBackgrounds, plainText } from '../editor/board.js';

let app;
let root;
let visible = false;
const sigs = new Map();      // card id -> signature of what it shows (re-render only on change)
let nameEd = null;
let descEd = null;
const codeCards = {};        // kind -> code card state
let romSongs = null;         // { game, names: {index: name}, soundbankCount } from GET /api/audio

// The images of each game (details.tsx _details_mp1 ...): [otherbg key, label, width, height].
const IMAGES = {
  1: [['boardselect', 'Board Select Image', 128, 64], ['boardlogo', 'Board Logo', 250, 100],
    ['largescene', 'Large Scene Background', 320, 240], ['conversation', 'Conversation Background', 320, 240],
    ['splashscreen', 'Splashscreen Background', 320, 240]],
  2: [['boardselect', 'Board Select Image', 64, 48], ['boardselecticon', 'Board Select Icon', 32, 32],
    ['boardlogo', 'Board Logo', 260, 120], ['largescene', 'Large Scene Background', 320, 240]],
  3: [['boardselect', 'Board Select Image', 64, 64], ['boardlogo', 'Board Logo (Large)', 226, 120],
    ['boardlogotext', 'Board Logo Text', 226, 36], ['boardlogomedium', 'Board Logo (Medium)', 150, 50],
    ['boardlogosmall', 'Board Logo (Small)', 100, 46], ['largescene', 'Large Scene Background', 320, 240]],
  duel: [['boardselect', 'Board Select Image', 64, 64], ['boardlogo', 'Board Logo', 226, 120],
    ['boardlogotext', 'Board Logo Text', 226, 36]],
};

const IMAGE_TIPS = {
  boardselect: 'Shown on the board selection screen',
  boardselecticon: 'The small icon on the board selection screen',
  boardlogo: 'The board\'s title logo',
  boardlogotext: 'The board\'s name, as a logo',
  boardlogomedium: 'A medium-sized logo',
  boardlogosmall: 'A small logo',
  largescene: 'The background of scenes such as the opening and Bowser\'s visits',
  conversation: 'The background of conversations with Toad and others',
  splashscreen: 'The board\'s introduction screen',
};

const COSTUMES = [
  [CostumeType.NORMAL, 'Normal'], [CostumeType.WESTERN, 'Western'], [CostumeType.PIRATE, 'Pirate'],
  [CostumeType.HORROR, 'Horror'], [CostumeType.SPACE, 'Space'], [CostumeType.MYSTERY, 'Mystery'],
];

const CODE_KINDS = {
  additionalbg: {
    title: 'Additional Background Code',
    op: 'setAdditionalBackgroundCode',
    tip: 'Code that runs at the start of each turn and returns which background to show: DEFAULT_BG or ADDITIONAL_BG_1, ADDITIONAL_BG_2…',
  },
  audioselect: {
    title: 'Music Selection Code',
    op: 'setAudioSelectCode',
    tip: 'Code that runs when the board music starts and returns which song to play: MUSIC_TRACK_INDEX_1, MUSIC_TRACK_INDEX_2…',
  },
};

const TEMPLATE = `
<div class="scroll-page details-page">
  <div class="page-head">
    <div>
      <h2 class="details-title">Board Details</h2>
      <p class="hint details-sub"></p>
    </div>
    <div class="card-actions details-head-actions"></div>
  </div>
  <div class="details-empty viewer-empty" hidden></div>
  <div class="details-grid">
    <div class="details-cols">
      <div class="details-col">
        <section class="card" data-card="info"><div class="card-head"><h2>Basic Info</h2></div><div class="card-body"></div></section>
        <section class="card" data-card="music"><div class="card-head"><h2>Background Music</h2><div class="card-actions"></div></div><div class="card-body"></div></section>
      </div>
      <div class="details-col">
        <section class="card" data-card="bg"><div class="card-head"><h2>Main Background</h2><span class="pill"></span></div><div class="card-body"></div></section>
        <section class="card" data-card="morebg"><div class="card-head"><h2></h2></div><div class="card-body"></div></section>
      </div>
      <div class="details-col">
        <section class="card" data-card="images"><div class="card-head"><h2>Images</h2></div><div class="card-body"></div></section>
      </div>
    </div>
    <section class="card wide" data-card="stats"><div class="card-head"><h2>Stats</h2><span class="pill"></span></div><div class="card-body"></div></section>
    <section class="card wide code-card" data-card="code-additionalbg" hidden></section>
    <section class="card wide code-card" data-card="code-audioselect" hidden></section>
  </div>
</div>`;

function card(id) {
  return $(`[data-card="${id}"]`, root);
}

/** Renders a card if what it shows changed. */
function renderCard(id, sig, fn) {
  const key = JSON.stringify(sig);
  if (sigs.get(id) === key) return;
  sigs.set(id, key);
  fn(card(id));
}

function boardKey() {
  return `${store.index}:${store.rom}`;
}

// ---------- page ----------

function render() {
  const b = store.board;
  const empty = $('.details-empty', root);
  const grid = $('.details-grid', root);
  if (!b) {
    grid.hidden = true;
    empty.hidden = false;
    empty.innerHTML = '<strong>Loading the Board…</strong><span>One moment.</span>';
    return;
  }
  grid.hidden = false;
  empty.hidden = true;
  const ro = store.readonly;
  const isDuel = b.type === BoardType.DUEL;

  // Head
  $('.details-title', root).textContent = plainText(b.name) || 'Untitled';
  $('.details-sub', root).innerHTML = `${esc(GameNames[b.game] || 'MP' + b.game)}${isDuel ? ' · Duel board' : ''} · ${b.spaces.length} spaces${ro ? ' · <span class="warn-text">From the ROM: read-only</span>' : ''}`;
  const head = $('.details-head-actions', root);
  const headSig = `${ro}`;
  if (head.dataset.sig !== headSig) {
    head.dataset.sig = headSig;
    head.innerHTML = `${ro ? '<span class="pill warn" title="Boards in the ROM cannot be changed">Read-Only</span><button type="button" class="btn btn-sm btn-primary" data-copyedit title="Make an editable copy of this board and switch to it">Copy to Edit</button>' : ''}
      <button type="button" class="btn btn-sm" data-toeditor title="Back to laying out the board's spaces">Open in Editor</button>`;
    $('[data-copyedit]', head)?.addEventListener('click', () => copyCurrentBoard(app, true));
    $('[data-toeditor]', head).addEventListener('click', () => app.showPage('editor'));
  }

  renderInfo(b, ro);
  renderMusic(b, ro);
  renderBackground(b, ro);
  renderImages(b, ro);
  renderMoreBackgrounds(b, ro);
  renderStats(b);
  renderCodeCards(b, ro);
}

// ---------- basic info ----------

function renderInfo(b, ro) {
  renderCard('info', [boardKey(), ro, b.game, b.type], el => {
    const body = $('.card-body', el);
    body.innerHTML = `
      <div class="field"><span class="field-label tip" title="The board's name, as the game shows it (one line). Insert button images with the toolbar.">Board Name</span><div data-rt="name"></div></div>
      <div class="field"><span class="field-label tip" title="The text shown when choosing the board (two lines)">Board Description</span><div data-rt="desc"></div></div>
      <div class="field"><span class="field-label tip" title="How hard the board is, shown as stars when choosing it">Difficulty</span><div class="difficulty" role="radiogroup" aria-label="Difficulty"></div></div>
      ${b.game === 2 ? `<div class="field"><span class="field-label tip" title="The costumes the characters wear on this board (Mario Party 2)">Costume Theme</span>
        <div class="segmented costumes" role="group" aria-label="Costume theme">${COSTUMES.map(([v, n]) =>
          `<button type="button" data-costume="${v}" title="The ${n} costumes" ${ro ? 'disabled' : ''}>${n}</button>`).join('')}</div></div>` : ''}`;
    nameEd = createRichText($('[data-rt="name"]', body), {
      value: b.name, maxlines: 1, readonly: ro, title: 'The board\'s name',
      onChange: v => store.op('setBoardName', { name: v }, 'Rename board').then(() => app.refresh()),
    });
    descEd = createRichText($('[data-rt="desc"]', body), {
      value: b.description, maxlines: 2, readonly: ro, title: 'The board\'s description',
      onChange: v => store.op('setBoardDescription', { description: v }, 'Change description'),
    });
    const diff = $('.difficulty', body);
    diff.innerHTML = [1, 2, 3, 4, 5].map(l => `<button type="button" class="star" data-level="${l}" role="radio"
      title="Difficulty ${l} of 5" ${ro ? 'disabled' : ''}></button>`).join('');
    for (const s of $$('.star', diff)) {
      s.addEventListener('click', () => store.op('setBoardDifficulty', { difficulty: +s.dataset.level }, 'Change difficulty'));
      s.addEventListener('mouseenter', () => { if (!ro) diff.dataset.focus = s.dataset.level; paintStars(diff); });
      s.addEventListener('mouseleave', () => { delete diff.dataset.focus; paintStars(diff); });
    }
    for (const btn of $$('[data-costume]', body)) {
      btn.addEventListener('click', () => store.op('setBoardCostumeTypeIndex', { costumeType: +btn.dataset.costume }, 'Change costumes'));
    }
  });
  // Values (kept up to date without rebuilding the editors).
  nameEd?.setValue(b.name);
  descEd?.setValue(b.description);
  const diff = $('.difficulty', card('info'));
  if (diff) {
    diff.dataset.level = b.difficulty || 0;
    paintStars(diff);
  }
  for (const btn of $$('[data-costume]', card('info'))) {
    // An unset costume type is Normal.
    btn.classList.toggle('active', +btn.dataset.costume === (b.costumeTypeIndex ?? CostumeType.NORMAL));
  }
}

function paintStars(diff) {
  const level = +diff.dataset.level || 0;
  const focus = +diff.dataset.focus || 0;
  for (const s of $$('.star', diff)) {
    const l = +s.dataset.level;
    s.classList.toggle('on', l <= level);
    s.classList.toggle('focus', focus > 0 && l <= focus);
    s.setAttribute('aria-checked', l === level ? 'true' : 'false');
  }
}

// ---------- music ----------

async function loadRomSongs(game) {
  const rom = app.state?.rom;
  if (!rom || rom.gameVersion !== game) {
    romSongs = null;
    return;
  }
  if (romSongs && romSongs.game === game && romSongs.file === rom.fileName) return;
  try {
    const res = await api('/api/audio');
    const t0 = (res.songs || [])[0];
    const names = {};
    for (const it of t0?.items || []) if (it.name) names[it.index] = it.name;
    romSongs = { game, file: rom.fileName, names, soundbankCount: t0?.soundbankCount || 0 };
  } catch {
    romSongs = null;
  }
}

function renderMusic(b, ro) {
  const advanced = !!app.setting('ui.advanced');
  const romKey = app.state?.rom ? `${app.state.rom.gameVersion}:${app.state.rom.fileName}` : '';
  if (romSongs === null && app.state?.rom?.gameVersion === b.game) {
    loadRomSongs(b.game).then(() => { sigs.delete('music'); if (store.board) renderMusic(store.board, store.readonly); });
  }
  renderCard('music', [boardKey(), ro, advanced, b.game, b.audioType, b.audioIndex, b.audioData?.map(a => [a.name, a.soundbankIndex, !!a.data]),
    !!b.audioSelectCode, romKey, !!romSongs], el => {
    const actions = $('.card-actions', el);
    actions.innerHTML = advanced && !ro
      ? `<button type="button" class="btn btn-sm" data-code title="Add custom code for choosing the music to play each turn">
          <img src="${IMG}/details/audioconfig.png" alt="">Selection Code${b.audioSelectCode ? ' ●' : ''}</button>` : '';
    $('[data-code]', actions)?.addEventListener('click', () => openCode('audioselect'));
    const body = $('.card-body', el);
    const type = b.audioType ?? BoardAudioType.InGame;
    let input = '';
    if (type === BoardAudioType.InGame) {
      if (romSongs && Object.keys(romSongs.names).length) {
        const opts = Object.entries(romSongs.names).map(([i, n]) =>
          `<option value="${i}" ${+i === b.audioIndex ? 'selected' : ''}>${esc(n)}</option>`).join('');
        input = `<select class="input" data-song ${ro ? 'disabled' : ''} title="The game's song played on this board">${opts}</select>`;
      } else {
        input = `<div class="input-row"><input class="input mono" type="number" min="0" data-songnum value="${b.audioIndex ?? 0}" ${ro ? 'disabled' : ''}
            title="The index of the game's song played on this board"><span class="muted small nowrap">Song ${hex(b.audioIndex ?? 0)}</span></div>
          <p class="hint">Open a ${esc(GameNames[b.game])} ROM to choose the song by name.</p>`;
      }
    } else {
      const entries = (b.audioData || []).map((a, i) => audioEntry(a, i, true, ro)).join('');
      input = `<div class="audio-list">${entries}${ro ? '' : audioEntry({ name: '', data: '', soundbankIndex: 0 }, (b.audioData || []).length, false, ro)}</div>
        ${(b.audioData || []).length > 1 ? '<p class="hint">With several songs, the Music Selection Code chooses which plays.</p>' : ''}`;
    }
    body.innerHTML = `
      <div class="segmented audio-type" role="radiogroup" aria-label="Music source">
        <button type="button" data-atype="${BoardAudioType.InGame}" class="${type === BoardAudioType.InGame ? 'active' : ''}" ${ro ? 'disabled' : ''}
          title="Play one of the game's own songs">In-Game Music Track</button>
        <button type="button" data-atype="${BoardAudioType.Custom}" class="${type === BoardAudioType.Custom ? 'active' : ''}" ${ro ? 'disabled' : ''}
          title="Play MIDI files of your own">Custom Audio</button>
      </div>
      <div class="field">${input}</div>`;
    for (const btn of $$('[data-atype]', body)) {
      btn.addEventListener('click', () => {
        if (+btn.dataset.atype === type) return;
        setAudio({ audioType: +btn.dataset.atype });
      });
    }
    $('[data-song]', body)?.addEventListener('change', e => setAudio({ gameAudioIndex: parseInt(e.target.value, 10) }));
    $('[data-songnum]', body)?.addEventListener('change', e => {
      const v = parseInt(e.target.value, 10);
      if (!isNaN(v) && v >= 0) setAudio({ gameAudioIndex: v });
    });
    for (const row of $$('.audio-entry', body)) {
      const i = +row.dataset.i;
      $('[data-midi]', row)?.addEventListener('click', () => promptMidi(i));
      $('[data-bank]', row)?.addEventListener('click', () => promptSoundbank(i));
      $('[data-del]', row)?.addEventListener('click', () => setAudio({ customAudioIndex: i, delete: true }, 'Remove song'));
    }
  });
}

function audioEntry(a, i, canDelete, ro) {
  const name = a.name || '(select a midi file)';
  return `<div class="audio-entry${a.data ? '' : ' new'}" data-i="${i}">
    <img src="${IMG}/details/audio.png" class="audio-icon" alt="" title="Custom audio track">
    <div class="audio-text">
      <div class="audio-name">${esc(name)}</div>
      ${a.data ? `<div class="audio-bank muted small">Soundbank Index: <b>${a.soundbankIndex || 0}</b></div>` : ''}
    </div>
    ${ro ? '' : `<button type="button" class="btn btn-sm" data-midi title="Upload a MIDI file for this track">${a.data ? 'Replace' : 'Upload MIDI…'}</button>
      ${a.data ? '<button type="button" class="btn btn-sm" data-bank title="Change the soundbank (the instruments) the song plays with">Soundbank</button>' : ''}
      ${canDelete ? '<button type="button" class="btn btn-ghost btn-sm btn-icon" data-del title="Remove this audio track">✕</button>' : ''}`}
  </div>`;
}

function setAudio(audioChanges, label = 'Change music') {
  return store.op('setBoardAudio', { audioChanges }, label);
}

async function promptMidi(customAudioIndex) {
  const file = await pickFile('audio/midi,audio/x-midi,.mid,.midi');
  if (!file) return;
  const midiData = await readDataURL(file);
  setAudio({ customAudioIndex, midiName: file.name, midiData }, 'Set custom song');
}

async function promptSoundbank(customAudioIndex) {
  const b = store.board;
  const upperBound = romSongs && romSongs.game === b.game ? Math.max(0, romSongs.soundbankCount - 1) : 0;
  const value = await promptDialog(`Enter new soundbank index${upperBound ? ` (0 through ${upperBound})` : ''}:`,
    { title: 'Soundbank Index', value: String(b.audioData?.[customAudioIndex]?.soundbankIndex || 0) });
  if (!value) return;
  const idx = parseInt(value, 10);
  if (isNaN(idx) || idx < 0 || (upperBound && idx > upperBound)) {
    toast('Invalid soundbank index.', 'warn');
    return;
  }
  setAudio({ customAudioIndex, soundbankIndex: idx }, 'Change soundbank');
}

function hex(n) {
  return '0x' + Number(n).toString(16).toUpperCase();
}

// ---------- backgrounds ----------

function renderBackground(b, ro) {
  const [w, h] = mainBgSize(b.game, b.type);
  renderCard('bg', [boardKey(), ro, b.bg.src, b.bg.width, b.bg.height, w, h], el => {
    $('.card-head .pill', el).textContent = `${b.bg.width} × ${b.bg.height}`;
    $('.card-head .pill', el).title = 'The background\'s size, in pixels';
    $('.card-body', el).innerHTML = `
      <button type="button" class="img-pick main-bg" ${ro ? 'disabled' : ''} title="${ro ? 'The board\'s main background' : `Choose a new main background (${w} × ${h})`}">
        ${typeof b.bg.src === 'string' ? `<img src="${esc(b.bg.src)}" alt="Main background">` : '<span class="muted">No background</span>'}
        ${ro ? '' : `<span class="img-cover"><span>Choose a New Image</span><small>${w} × ${h}</small></span>`}
      </button>
      <p class="hint">The board itself: spaces are placed on it in the Editor.${ro ? '' : ` Images of another size are used as they are (the game expects ${w} × ${h}).`}</p>`;
    $('.main-bg', el).addEventListener('click', async () => {
      if (ro) return;
      const file = await pickFile('image/*');
      if (!file) return;
      store.op('setBackground', { bg: await readDataURL(file) }, 'Change main background');
    });
  });
}

function renderMoreBackgrounds(b, ro) {
  const anim = supportsAnimationBackgrounds(b);
  const advanced = !!app.setting('ui.advanced');
  const add = supportsAdditionalBackgrounds(b) && (advanced || (b.additionalbg || []).length || !!b.additionalbgcode);
  const el = card('morebg');
  el.hidden = !(anim || add);
  if (el.hidden) return;
  const list = anim ? 'animbg' : 'additionalbg';
  const [w, h] = mainBgSize(b.game, b.type);
  renderCard('morebg', [boardKey(), ro, list, b[list], !!b.additionalbgcode, w, h], () => {
    $('.card-head h2', el).textContent = anim ? 'Animation Backgrounds' : 'Additional Backgrounds';
    const items = (b[list] || []).map((src, i) => `<div class="bg-tile" data-i="${i}">
      <img src="${esc(src)}" alt="" title="Background ${i + 1}">
      <div class="bg-tile-foot"><span>Background ${i + 1}</span>
        ${ro ? '' : '<button type="button" class="btn btn-ghost btn-sm btn-icon" data-remove title="Remove this background">✕</button>'}</div></div>`).join('');
    $('.card-body', el).innerHTML = `
      <p class="hint">${anim
        ? 'Frames the game shows in turn over the main background, to animate it. Play them on the board from the Editor.'
        : 'Backgrounds the board can switch to. The Additional Background Code picks the one shown each turn.'}</p>
      <div class="bg-tiles">${items || `<p class="hint">No ${anim ? 'animation frames' : 'additional backgrounds'}.</p>`}</div>
      <div class="card-actions">
        ${ro ? '' : `<button type="button" class="btn btn-sm" data-add title="Add a background the size of the main one (${w} × ${h})"><img src="${IMG}/toolbar/animadd.png" alt="">Add Background…</button>`}
        ${!anim && !ro ? `<button type="button" class="btn btn-sm" data-code title="Configure additional background usage: the code that picks the background each turn">⚙ Background Code${b.additionalbgcode ? ' ●' : ''}</button>` : ''}
      </div>`;
    $('[data-add]', el)?.addEventListener('click', async () => {
      const file = await pickFile('image/*');
      if (!file) return;
      const bg = await readDataURL(file);
      store.op(anim ? 'addAnimationBackground' : 'addAdditionalBackground', { bg }, 'Add background');
    });
    $('[data-code]', el)?.addEventListener('click', () => openCode('additionalbg'));
    for (const tile of $$('.bg-tile', el)) {
      $('[data-remove]', tile)?.addEventListener('click', () => store.op(
        anim ? 'removeAnimationBackground' : 'removeAdditionalBackground', { index: +tile.dataset.i }, 'Remove background'));
    }
  });
}

// ---------- other images ----------

function renderImages(b, ro) {
  const list = b.type === BoardType.DUEL ? IMAGES.duel : IMAGES[b.game] || [];
  renderCard('images', [boardKey(), ro, list.map(([k]) => b.otherbg?.[k])], el => {
    const body = $('.card-body', el);
    body.innerHTML = `<div class="img-tiles">${list.map(([key, label, w, h]) => `
      <div class="img-tile" style="--w:${w}px">
        <span class="field-label tip" title="${esc(IMAGE_TIPS[key] || '')}">${esc(label)}</span>
        <button type="button" class="img-pick" data-key="${key}" data-w="${w}" data-h="${h}" ${ro ? 'disabled' : ''}
          style="aspect-ratio:${w}/${h}" title="${ro ? esc(label) : `Choose a new image (${w} × ${h}): it is resized to fit`}">
          ${b.otherbg?.[key] ? `<img src="${esc(b.otherbg[key])}" alt="${esc(label)}">` : '<span class="muted small">None</span>'}
          ${ro ? '' : `<span class="img-cover">${w > 100 && h > 50 ? '<span>Choose a New Image</span>' : ''}<small>${w} × ${h}</small></span>`}
        </button>
        <span class="muted small mono">${w} × ${h}</span>
      </div>`).join('')}</div>`;
    for (const btn of $$('.img-pick', body)) {
      btn.addEventListener('click', () => act(async () => {
        const file = await pickFile('image/*');
        if (!file) return;
        const value = await processImage(btn.dataset.key, await readDataURL(file), +btn.dataset.w, +btn.dataset.h);
        await store.op('setBoardOtherBg', { name: btn.dataset.key, value }, `Change ${btn.dataset.key}`);
      }));
    }
  });
}

/** Resizes an image to (w, h) as the game needs it, with the MP1 board select image's mask. */
async function processImage(key, src, width, height) {
  const img = await new Promise((resolve, reject) => {
    const i = new Image();
    i.onload = () => resolve(i);
    i.onerror = () => reject(new Error('The image could not be read.'));
    i.src = src;
  });
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, width, height);
  if (key === 'boardselect' && store.board.game === 1 && width === 128 && height === 64) {
    const data = ctx.getImageData(0, 0, width, height);
    maskMp1BoardSelect(new Uint32Array(data.data.buffer));
    ctx.putImageData(data, 0, 0);
  }
  return canvas.toDataURL('image/png');
}

/** The MP1 board select image's rounded corners and palette limit (details.tsx _processImage). */
function maskMp1BoardSelect(rgba32) {
  // Do the two full rows on each edge...
  for (let y = 0; y < 128; y++) {
    rgba32[y] = 0; // 1st row
    rgba32[y + 128] = 0; // 2nd row
    rgba32[y + 128 * 62] = 0; // 2nd to last row
    rgba32[y + 128 * 63] = 0; // last row
  }
  // Then round the corners
  const corner = (row, count, rightOffset) => {
    for (let y = 0; y < count; y++) {
      rgba32[y + 128 * row] = 0;
      rgba32[y + 128 * row + rightOffset] = 0;
    }
  };
  corner(2, 6, 122); corner(61, 6, 122);
  corner(3, 4, 124); corner(60, 4, 124);
  corner(4, 3, 125); corner(59, 3, 125);
  corner(5, 2, 126); corner(58, 2, 126); corner(6, 2, 126); corner(57, 2, 126);
  for (const row of [7, 56, 8, 55]) {
    rgba32[128 * row] = 0;
    rgba32[128 * row + 127] = 0;
  }
  // Validate that the image meets the color limits. Technically this is 256 colors when split into 4 tiles.
  const count = (y0, y1, x0, x1, extra) => {
    const set = new Set();
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) set.add(rgba32[y * 128 + extra + x]);
    return set.size;
  };
  if (count(0, 32, 0, 64, 0) > 256 || count(0, 32, 64, 128, 64) > 256
    || count(32, 64, 0, 64, 0) > 256 || count(32, 64, 64, 128, 64) > 256) {
    toast('Sorry, but the palette limit for this image is 256 unique colors. For now, the image has been reduced to 8-bit, but most image editors should be able to reduce the palette for you with higher quality.', 'warn', 12000);
    for (let i = 0; i < 128 * 64; i++) {
      let val = rgba32[i];
      val &= 0xc0c0c0c0;
      val |= val >>> 2;
      val |= val >>> 2;
      val |= val >>> 2;
      rgba32[i] = val;
    }
  }
}

// ---------- stats ----------

const STATS = {
  1: [['blue', Space.BLUE, 'Blue'], ['red', Space.RED, 'Red'], ['happening', Space.HAPPENING, 'Happening'],
    ['chance', Space.CHANCE, 'Chance'], ['minigame', Space.MINIGAME, 'Mini-Game'], ['shroom', Space.SHROOM, 'Mushroom'],
    ['bowser', Space.BOWSER, 'Bowser'], ['star', Space.STAR, 'Star'], ['start', Space.START, 'Start'], ['other', Space.OTHER, 'Invisible']],
  2: [['blue', Space.BLUE, 'Blue'], ['red', Space.RED, 'Red'], ['happening', Space.HAPPENING, 'Happening'],
    ['chance2', Space.CHANCE, 'Chance'], ['item', Space.ITEM, 'Item'], ['battle', Space.BATTLE, 'Battle'], ['bank', Space.BANK, 'Bank'],
    ['bowser', Space.BOWSER, 'Bowser'], ['star', Space.STAR, 'Star'], ['blackstar', Space.BLACKSTAR, 'Black Star'],
    ['arrow', Space.ARROW, 'Arrow'], ['start', Space.START, 'Start'], ['other', Space.OTHER, 'Invisible']],
  3: [['blue3', Space.BLUE, 'Blue'], ['red3', Space.RED, 'Red'], ['happening3', Space.HAPPENING, 'Happening'],
    ['chance3', Space.CHANCE, 'Chance'], ['item3', Space.ITEM, 'Item'], ['battle3', Space.BATTLE, 'Battle'], ['bank3', Space.BANK, 'Bank'],
    ['gameguy', Space.GAMEGUY, 'Game Guy'], ['bowser3', Space.BOWSER, 'Bowser'], ['star', Space.STAR, 'Star'],
    ['arrow', Space.ARROW, 'Arrow'], ['start', Space.START, 'Start'], ['other', Space.OTHER, 'Invisible']],
};
// The "solid" spaces (those a player lands on) of each game's stats.
const SOLID = {
  1: [Space.BLUE, Space.RED, Space.HAPPENING, Space.CHANCE, Space.MINIGAME, Space.SHROOM, Space.BOWSER],
  2: [Space.BLUE, Space.RED, Space.HAPPENING, Space.CHANCE, Space.ITEM, Space.BATTLE, Space.BANK, Space.BOWSER],
  3: [Space.BLUE, Space.RED, Space.HAPPENING, Space.CHANCE, Space.ITEM, Space.BATTLE, Space.BANK, Space.GAMEGUY, Space.BOWSER],
};

function renderStats(b) {
  const el = card('stats');
  // The original showed no stats for duel boards.
  el.hidden = b.type === BoardType.DUEL;
  if (el.hidden) return;
  const counts = new Map();
  for (const s of b.spaces) if (s) counts.set(s.type, (counts.get(s.type) || 0) + 1);
  const count = (...types) => (types.length
    ? types.reduce((n, t) => n + (counts.get(t) || 0), 0)
    : [...counts.values()].reduce((a, c) => a + c, 0));
  const rows = STATS[b.game] || [];
  renderCard('stats', [b.game, [...counts.entries()]], () => {
    const solid = count(...SOLID[b.game]);
    const total = count();
    $('.card-head .pill', el).textContent = `${total} spaces`;
    $('.card-head .pill', el).title = 'All the spaces on the board, invisible ones included';
    $('.card-body', el).innerHTML = `<div class="stat-tiles">
      ${rows.map(([icon, type, name]) => `<div class="stat-tile${count(type) ? '' : ' zero'}" title="${name} spaces">
        <img src="${TI[icon]}" alt=""><b>${count(type)}</b><span>${name}</span></div>`).join('')}
      <div class="stat-tile sum" title="Spaces a player can land on: ${SOLID[b.game].length} kinds"><b>${solid}</b><span>Solid</span></div>
      <div class="stat-tile sum" title="All the spaces"><b>${total}</b><span>Total</span></div>
    </div>`;
  });
}

// ---------- code (views/basiccodeeditorview.tsx) ----------

function renderCodeCards(b, ro) {
  const advanced = !!app.setting('ui.advanced');
  const showAdd = supportsAdditionalBackgrounds(b) && (advanced || (b.additionalbg || []).length || !!b.additionalbgcode);
  const showAudio = advanced && !ro;
  setCodeCardVisible('additionalbg', showAdd);
  setCodeCardVisible('audioselect', showAudio);
}

function setCodeCardVisible(kind, show) {
  const el = card(`code-${kind}`);
  el.hidden = !show;
  let c = codeCards[kind];
  if (!show) return;
  if (!c || c.boardKey !== boardKey()) {
    // A new board: start again (closed).
    c?.editor?.destroy?.();
    c = codeCards[kind] = { boardKey: boardKey(), open: false, editor: null, language: EventCodeLanguage.C, saved: null };
    const info = CODE_KINDS[kind];
    const hasCode = kind === 'additionalbg' ? !!store.board.additionalbgcode : !!store.board.audioSelectCode;
    el.innerHTML = `<div class="card-head"><h2 class="tip" title="${esc(info.tip)}">${info.title}</h2>
        <div class="card-actions"><span class="pill ${hasCode ? 'ok' : ''}" data-state>${hasCode ? 'Custom Code' : 'Default'}</span>
        <button type="button" class="btn btn-sm" data-open title="Show the code editor">Edit Code</button></div></div>
      <div class="code-body" hidden></div>`;
    $('[data-open]', el).addEventListener('click', () => openCode(kind));
  }
}

async function openCode(kind) {
  if (store.readonly && kind === 'audioselect') return;
  const el = card(`code-${kind}`);
  if (el.hidden) {
    // e.g. MP2 has no additional backgrounds.
    if (kind === 'additionalbg' && !supportsAdditionalBackgrounds(store.board)) return;
    el.hidden = false;
    setCodeCardVisible(kind, true);
  }
  const c = codeCards[kind];
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (c.open) {
    c.editor?.view?.focus();
    return;
  }
  c.open = true;
  $('[data-open]', el).hidden = true;
  const body = $('.code-body', el);
  body.hidden = false;
  const ro = store.readonly;
  body.innerHTML = `
    <div class="code-toolbar">
      <div class="segmented" data-lang role="radiogroup" aria-label="Language">
        <button type="button" data-l="${EventCodeLanguage.C}" title="Write the code in C" ${ro ? 'disabled' : ''}>C</button>
        <button type="button" data-l="${EventCodeLanguage.MIPS}" title="Write the code in MIPS assembly" ${ro ? 'disabled' : ''}>MIPS</button>
      </div>
      <span class="pill" data-dirty hidden>Unsaved</span>
      <span class="code-spacer"></span>
      ${ro ? '' : `<button type="button" class="btn btn-sm" data-test title="Compile the code for each game it could be written to, without saving">Test</button>
      <button type="button" class="btn btn-sm btn-ghost" data-reset title="Replace the code with the starting template">Reset to Default</button>
      <button type="button" class="btn btn-sm btn-primary" data-save title="Check the code and save it with the board (Ctrl+S)">Save</button>`}
      <button type="button" class="btn btn-sm btn-ghost" data-close title="Close the editor (unsaved changes are kept until you leave the board)">Close</button>
    </div>
    <div class="code-host"><span class="muted small">Loading the editor…</span></div>
    <div class="code-messages"></div>`;
  try {
    const existing = await api(`/api/board/code?kind=${kind}`);
    if (existing.code) {
      c.language = existing.language ?? EventCodeLanguage.C;
      c.saved = existing.code;
    } else {
      c.language = EventCodeLanguage.C;
      c.saved = null;
    }
    const code = existing.code || await defaultCode(kind, c.language);
    const { createCodeEditor } = await import('../lib/codeeditor.js');
    const host = $('.code-host', body);
    host.innerHTML = '';
    c.editor = await createCodeEditor(host, {
      language: c.language, value: code, readOnly: ro,
      onChange: () => markDirty(kind),
      onSave: () => saveCode(kind),
    });
    paintLang(kind);
  } catch (e) {
    $('.code-host', body).innerHTML = `<div class="notice err">${esc(e.message)}</div>`;
    return;
  }
  for (const btn of $$('[data-l]', body)) btn.addEventListener('click', () => switchLanguage(kind, +btn.dataset.l));
  $('[data-test]', body)?.addEventListener('click', () => testCode(kind));
  $('[data-save]', body)?.addEventListener('click', () => saveCode(kind));
  $('[data-reset]', body)?.addEventListener('click', async () => {
    if (!await confirmDialog('Replace the code with the starting template?', { title: 'Reset Code', yes: 'Reset' })) return;
    c.editor.setValue(await defaultCode(kind, c.language));
    markDirty(kind);
  });
  $('[data-close]', body).addEventListener('click', () => {
    c.open = false;
    body.hidden = true;
    $('[data-open]', el).hidden = false;
  });
}

const defaults = {};
async function defaultCode(kind, language) {
  const key = `${kind}:${language}`;
  if (!(key in defaults)) defaults[key] = (await api(`/api/board/code/default?kind=${kind}&language=${language}`)).code;
  return defaults[key];
}

function paintLang(kind) {
  const el = card(`code-${kind}`);
  for (const b of $$('[data-l]', el)) b.classList.toggle('active', +b.dataset.l === codeCards[kind].language);
}

async function markDirty(kind) {
  const c = codeCards[kind];
  const el = card(`code-${kind}`);
  const code = c.editor.getValue();
  const def = await defaultCode(kind, c.language);
  const dirty = c.saved !== null ? code !== c.saved : code !== def;
  $('[data-dirty]', el).hidden = !dirty;
}

async function switchLanguage(kind, language) {
  const c = codeCards[kind];
  if (language === c.language) return;
  const code = c.editor.getValue();
  const changed = code !== await defaultCode(kind, c.language);
  if (changed && !await confirmDialog('Are you sure you want to switch languages? The current code will not be kept.',
    { title: 'Switch Language', yes: 'Switch' })) return;
  c.language = language;
  c.editor.setLanguage(language);
  c.editor.setValue(await defaultCode(kind, language));
  paintLang(kind);
  markDirty(kind);
}

function showMessages(kind, html) {
  $('.code-messages', card(`code-${kind}`)).innerHTML = html;
}

async function testCode(kind) {
  const c = codeCards[kind];
  showMessages(kind, '<p class="hint">Compiling…</p>');
  await act(async () => {
    const res = await api('/api/board/code/test', { kind, code: c.editor.getValue(), language: c.language });
    showMessages(kind, res.ok
      ? '<div class="notice info">✓ The code compiles.</div>'
      : `<div class="notice err">${(res.messages || []).map(m => `<div>${esc(m)}</div>`).join('')}</div>`);
  });
}

async function saveCode(kind) {
  const c = codeCards[kind];
  if (store.readonly) return;
  let code = c.editor.getValue();
  const language = c.language;
  const op = CODE_KINDS[kind].op;
  await act(async () => {
    if (!code.trim()) {
      toast('No code was provided, any existing code will be removed.');
      await store.op(op, { code: '', language }, `Remove ${CODE_KINDS[kind].title.toLowerCase()}`);
      c.saved = null;
    } else {
      showMessages(kind, '<p class="hint">Checking the code…</p>');
      const res = await api('/api/board/code/test', { kind, code, language });
      if (!res.ok) {
        showMessages(kind, `<div class="notice err">${(res.messages || []).map(m => `<div>${esc(m)}</div>`).join('')}</div>`);
        toast('The code has errors: it was not saved.', 'error');
        return;
      }
      // The template is the same as no code.
      if (code === await defaultCode(kind, language)) code = '';
      const r = await store.op(op, { code, language }, `Save ${CODE_KINDS[kind].title.toLowerCase()}`);
      if (!r) return;
      c.saved = code || null;
      showMessages(kind, '');
      toast(code ? 'Saved the code with the board.' : 'The template is the default: the board uses no custom code.', 'success');
    }
    markDirty(kind);
    const pill = $('[data-state]', card(`code-${kind}`));
    pill.textContent = c.saved ? 'Custom Code' : 'Default';
    pill.className = 'pill' + (c.saved ? ' ok' : '');
  });
}

// ---------- page contract ----------

export async function init(container, appRef) {
  app = appRef;
  loadCss('details');
  root = container;
  root.innerHTML = TEMPLATE;
  store.init(app);
  store.on('board', () => { if (visible) render(); });
  app.on('settings', () => { if (visible) render(); });
  app.on('state', () => { if (visible) render(); });
  app.on('rom', () => {
    romSongs = null;
    sigs.delete('music');
  });
  if (!store.board) {
    render();
    await act(() => store.load());
    store.loadLibrary();
  }
}

export function show() {
  visible = true;
  render();
  const section = sessionStorage.getItem('pp64.details.section');
  if (section) {
    sessionStorage.removeItem('pp64.details.section');
    openCode(section);
  }
}

export function hide() {
  visible = false;
}

export { dialog };
