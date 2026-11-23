// Test Play: builds a ROM that boots straight into the current board, in the middle of a
// game, and starts it in an emulator (POST /api/playtest). The options (the players, their
// coins and stars, the turn, and the emulator) are kept by the server.
import { $, $$, api, esc, toast, act, busy, dialog, download } from '../api.js';
import { plainText } from './board.js';
import { store } from './store.js';

/** Escapes a message, keeping the links of validation messages (they were HTML). */
function messageHtml(text) {
  return esc(text)
    .replace(/&lt;a href=&quot;(https?:\/\/[^&"]+)&quot;[^&]*?&gt;(.*?)&lt;\/a&gt;/g,
      '<a href="$1" target="_blank" rel="noopener">$2</a>')
    .replace(/&lt;br\s*\/?&gt;/g, '\n');
}

/** Builds the test ROM of the current board and starts the emulator with it. */
export async function playTest(app) {
  let failed = null;
  let res = null;
  $('#busyText').textContent = 'Building the test ROM…';
  $('#busy').hidden = false;
  try {
    res = await api('/api/playtest', {});
  } catch (e) {
    failed = e;
  } finally {
    $('#busy').hidden = true;
  }
  if (failed) {
    console.error(failed);
    // Without an emulator, the options are where to set one.
    if (/emulator/i.test(failed.message) && !/problems to fix/.test(failed.message)) {
      toast(failed.message.split('\n')[0], 'error', 9000);
      return playTestOptions(app);
    }
    await dialog({
      title: 'Test Play',
      body: `<div class="pt-error">${messageHtml(failed.message)}</div>`,
      buttons: [{ label: 'Close', value: false }],
    });
    return;
  }
  const board = plainText(res.boardName) || 'the board';
  const over = plainText(res.romBoardName) || `ROM board ${res.romBoardIndex}`;
  const where = res.boardName === res.romBoardName ? '' : ` (in place of ${over})`;
  toast(`Testing ${board}${where}: the emulator is starting.`, 'success', 7000);
  store.addLog?.(`Test play: ${board}${where}`);
}

function option(value, name, selected) {
  return `<option value="${esc(value)}"${selected ? ' selected' : ''}>${esc(name)}</option>`;
}

function playerRow(info, player, n) {
  const g = info.game;
  const items = [];
  for (let slot = 0; slot < g.itemSlots; slot++) {
    const held = player.items[slot];
    items.push(`<select class="input" data-item title="Item ${slot + 1} of player ${n + 1}">
        ${option('', 'No item', held === undefined)}
        ${g.items.map(i => option(i.id, i.name, held === i.id)).join('')}</select>`);
  }
  return `<tr data-player="${n}">
      <th scope="row">P${n + 1}</th>
      <td><select class="input" data-character title="Player ${n + 1}'s character">
        ${g.characters.map(c => option(c.id, c.name, c.id === player.character)).join('')}</select></td>
      <td><select class="input" data-control title="Who plays player ${n + 1}. Players can share a controller: give them all Controller 1 to take every turn yourself.">
        ${g.controls.map(c => option(c.id, c.name, c.id === player.control)).join('')}</select></td>
      <td><select class="input" data-difficulty title="How well the computer plays player ${n + 1}">
        ${g.difficulties.map(d => option(d.id, d.name, d.id === player.difficulty)).join('')}</select></td>
      <td class="pt-items">${items.join('')}</td></tr>`;
}

/** Reads the options form. */
function readOptions(el, info) {
  const num = name => Number($(`[data-opt="${name}"]`, el).value);
  return {
    players: $$('tr[data-player]', el).map(row => ({
      character: Number($('[data-character]', row).value),
      control: $('[data-control]', row).value,
      difficulty: Number($('[data-difficulty]', row).value),
      items: $$('[data-item]', row).map(s => s.value).filter(v => v !== '').map(Number),
    })),
    coins: num('coins'),
    stars: num('stars'),
    turns: num('turns'),
    turn: num('turn'),
  };
}

/** The Test Play options: the players, what they start with, the turn, and the emulator.
 * forEvent: opened from an event's test, where there is no board to test or download. */
export async function playTestOptions(app, { forEvent = false } = {}) {
  let info;
  try {
    info = await api('/api/playtest');
  } catch (e) {
    toast(e.message, 'error', 9000);
    return;
  }
  const emu = info.emulator || {};
  const detected = emu.detected;
  const g = info.game;
  const o = info.options;
  const body = document.createElement('div');
  body.className = 'pt-options';
  body.innerHTML = `
    <p class="hint">${forEvent
    ? 'Event tests use the same players, coins, turn and emulator as board tests.'
    : `Test Play writes the current board into a copy of the ROM that boots straight into it, in the
      middle of a game: no title screen, menus or opening scenes. The ROM you have open is not changed, and
      nothing is saved by the game.`}</p>
    ${info.reason ? `<div class="notice warn">${esc(info.reason)}</div>` : ''}
    <label class="field"><span class="field-label">Emulator command</span>
      <input class="input mono" data-opt="emulator" value="${esc(emu.command || '')}" spellcheck="false"
        placeholder="${esc(detected ? `Automatic: ${detected.command}` : 'e.g. /path/to/RMG %f')}"
        title="The command that starts your Nintendo 64 emulator. %f is replaced by the test ROM's file (it is added at the end if left out). Leave empty to use an installed emulator."></label>
    <p class="hint">${detected
    ? `Left empty, ${esc(detected.name)} is used (found among your applications).`
    : 'No emulator was found among your applications: enter the command that starts yours.'}
      Mario Party needs the Expansion Pak (8 MB of memory) turned on in the emulator.</p>
    ${g ? `
    <table class="pt-players" aria-label="Players">
      <thead><tr><th></th><th>Character</th><th>Played by</th><th>Computer skill</th><th>Items</th></tr></thead>
      <tbody>${o.players.map((p, n) => playerRow(info, p, n)).join('')}</tbody>
    </table>
    <p class="hint">The players take their turns in this order.</p>
    <div class="pt-numbers">
      <label class="field"><span class="field-label">Coins each</span>
        <input class="input" type="number" data-opt="coins" min="0" max="${g.maxCoins}" value="${o.coins}"></label>
      <label class="field"><span class="field-label">Stars each</span>
        <input class="input" type="number" data-opt="stars" min="0" max="${g.maxStars}" value="${o.stars}"></label>
      <label class="field"><span class="field-label">Turns in the game</span>
        <input class="input" type="number" data-opt="turns" min="1" max="${g.maxTurns}" value="${o.turns}"></label>
      <label class="field"><span class="field-label">Starts on turn</span>
        <input class="input" type="number" data-opt="turn" min="1" max="${g.maxTurns}" value="${o.turn}"></label>
    </div>` : ''}`;
  const syncRows = () => {
    for (const row of $$('tr[data-player]', body)) {
      $('[data-difficulty]', row).disabled = $('[data-control]', row).value !== 'cpu';
    }
  };
  body.addEventListener('change', syncRows);
  syncRows();

  // From an event's test, the board's notices and buttons don't apply.
  if (forEvent) $('.notice', body)?.remove();
  const boardTest = info.supported && !forEvent;
  const buttons = [{ label: 'Cancel', value: false }];
  if (g) {
    buttons.push({ label: 'Defaults', value: 'defaults' });
    if (boardTest) buttons.push({ label: 'Download Test ROM', value: 'download' });
  }
  buttons.push({ label: 'Save', value: 'save', kind: forEvent ? 'primary' : undefined });
  if (boardTest) buttons.push({ label: 'Save & Test', value: 'test', kind: 'primary' });
  const r = await dialog({ title: 'Test Play Options', body, wide: true, buttons });
  if (!r) return;
  if (r === 'defaults') {
    await act(async () => {
      await api('/api/playtest/options', { options: g.defaults });
      toast('The test options are back to their defaults.', 'success', 3000);
    });
    return playTestOptions(app, { forEvent });
  }
  const payload = { emulator: $('[data-opt="emulator"]', body).value };
  if (g) payload.options = readOptions(body, info);
  let saved = false;
  await act(async () => {
    await api('/api/playtest/options', payload);
    saved = true;
  });
  if (!saved) return playTestOptions(app, { forEvent });
  if (r === 'test') return playTest(app);
  if (r === 'download') {
    await busy('Building the test ROM…', async () => {
      const name = await download('/api/playtest/rom', {}, 'PartyPlanner64 Test.z64');
      toast(`Saved ${name}.`, 'success');
    });
    return;
  }
  toast('Saved the test options.', 'success', 3000);
}
