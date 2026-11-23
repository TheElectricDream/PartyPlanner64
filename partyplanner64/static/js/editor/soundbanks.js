// A board's own soundbanks (lib/audio/custom_bank.py): the Details page's Soundbanks card,
// the soundbank choice of a custom song, and the soundbank editor.
//
// A soundbank is {name, instruments: [{name, volume, pan, attack, decay, sustain, release,
// source}]}; an instrument's program number in the MIDI is its position. Sources: pulse
// (duty), wave (32 hex digits of Game Boy wave RAM), noise (short), sample (a recording).
import { $, $$, api, esc, toast, confirmDialog, dialog, pickFile, saveBlob } from '../api.js';
import { store } from './store.js';

const SOURCES = [
  ['pulse:0.125', 'Pulse 12.5%'], ['pulse:0.25', 'Pulse 25%'], ['pulse:0.5', 'Pulse 50%'], ['pulse:0.75', 'Pulse 75%'],
  ['wave', 'Wave'], ['noise:0', 'Noise'], ['noise:1', 'Noise (Short)'], ['sample', 'Recording'],
];
const TRIANGLE = '0123456789ABCDEFFEDCBA9876543210';
const sizeCache = new Map();    // JSON of a bank -> {bytes, budget, problem}

function sourceKey(src) {
  if (src.type === 'pulse') return `pulse:${src.duty}`;
  if (src.type === 'noise') return `noise:${src.short ? 1 : 0}`;
  return src.type;
}

function sourceFromKey(key, old) {
  const [type, arg] = key.split(':');
  if (type === 'pulse') return { type, duty: +arg };
  if (type === 'noise') return { type, short: arg === '1' };
  if (type === 'wave') return { type, pattern: old?.type === 'wave' ? old.pattern : TRIANGLE };
  return old?.type === 'sample' ? old : null;
}

function newInstrument(name, source) {
  return { name, volume: 110, pan: 64, attack: 0, decay: 1, sustain: 127, release: 20, source };
}

async function bankInfo(bank) {
  const key = JSON.stringify(bank);
  if (!sizeCache.has(key)) {
    sizeCache.set(key, api('/api/soundbanks/info', { soundbank: bank }).catch(e => ({ error: e.message })));
  }
  return sizeCache.get(key);
}

function infoText(info) {
  if (!info) return '…';
  if (info.error) return esc(info.error);
  const used = `${info.bytes.toLocaleString()}${info.budget ? ` of ~${info.budget.toLocaleString()}` : ''} bytes of audio memory`;
  return info.problem ? `<span class="warn-text">${esc(info.problem)}</span>` : used;
}

/** What a custom song plays with: "Game Soundbank 20" or the board soundbank's name. */
export function soundbankLabel(board, entry) {
  const custom = entry.customSoundbank;
  if (Number.isInteger(custom) && board.soundbanks?.[custom]) return `<b>${esc(board.soundbanks[custom].name || 'Soundbank')}</b> (board)`;
  return `Game Soundbank <b>${entry.soundbankIndex || 0}</b>`;
}

/** Lets the user choose a game soundbank or one of the board's for custom song i. */
export async function chooseSoundbank(board, i, gameBankCount) {
  const entry = board.audioData?.[i] || {};
  const banks = board.soundbanks || [];
  const custom = Number.isInteger(entry.customSoundbank) && banks[entry.customSoundbank];
  const body = document.createElement('div');
  body.className = 'sb-choose';
  body.innerHTML = `
    <label class="sb-choice"><input type="radio" name="sbk" value="game" ${custom ? '' : 'checked'}>
      <span>Game soundbank</span>
      <input class="input mono sb-num" type="number" min="0" ${gameBankCount ? `max="${gameBankCount - 1}"` : ''} value="${entry.soundbankIndex || 0}">
      <span class="muted small">${gameBankCount ? `0 through ${gameBankCount - 1}` : 'Open a ROM to see how many there are'}</span></label>
    <label class="sb-choice"><input type="radio" name="sbk" value="custom" ${custom ? 'checked' : ''} ${banks.length ? '' : 'disabled'}>
      <span>Board soundbank</span>
      <select class="input sb-pick" ${banks.length ? '' : 'disabled'}>${banks.map((b, k) =>
        `<option value="${k}" ${k === entry.customSoundbank ? 'selected' : ''}>${esc(b.name || `Soundbank ${k}`)}</option>`).join('')}</select>
      ${banks.length ? '' : '<span class="muted small">Make one in the Soundbanks card</span>'}</label>`;
  const ok = await dialog({
    title: 'Soundbank', body,
    buttons: [{ label: 'Cancel', value: false }, { label: 'OK', value: true, kind: 'primary' }],
    onOpen: el => {
      $('.sb-num', el).addEventListener('focus', () => { $('[value="game"]', el).checked = true; });
      $('.sb-pick', el)?.addEventListener('focus', () => { $('[value="custom"]', el).checked = true; });
    },
  });
  if (!ok) return;
  if ($('[value="custom"]', body).checked) {
    await store.op('setBoardAudio', { audioChanges: { customAudioIndex: i, customSoundbank: +$('.sb-pick', body).value } }, 'Use board soundbank');
    return;
  }
  const idx = parseInt($('.sb-num', body).value, 10);
  if (isNaN(idx) || idx < 0 || (gameBankCount && idx >= gameBankCount)) {
    toast('Invalid soundbank index.', 'warn');
    return;
  }
  await store.op('setBoardAudio', { audioChanges: { customAudioIndex: i, soundbankIndex: idx } }, 'Change soundbank');
}

// ---------- the card ----------

/** Fills the Soundbanks card's body. */
export function renderSoundbanks(body, board, ro) {
  const banks = board.soundbanks || [];
  const mp3 = board.game === 3;
  body.innerHTML = `
    <p class="hint">Instruments of your own for your custom songs. A song plays one soundbank; its MIDI program numbers pick the instruments, from 0.${mp3 ? '' : ' <span class="warn-text">Custom soundbanks work with Mario Party 3 so far.</span>'}</p>
    <div class="sb-list">${banks.map((b, k) => `
      <div class="sb-item" data-k="${k}">
        <img src="/static/img/details/audio.png" class="audio-icon" alt="">
        <div class="audio-text"><div class="audio-name">${esc(b.name || `Soundbank ${k}`)}</div>
          <div class="muted small"><span>${b.instruments.length} instrument${b.instruments.length === 1 ? '' : 's'}</span> · <span data-bytes>…</span></div></div>
        ${ro ? '' : `<button type="button" class="btn btn-sm" data-edit title="Change the instruments">Edit</button>`}
        <button type="button" class="btn btn-sm" data-export title="Save this soundbank as a file, to use on other boards">Export</button>
        ${ro ? '' : '<button type="button" class="btn btn-ghost btn-sm btn-icon" data-del title="Delete this soundbank">✕</button>'}
      </div>`).join('') || '<p class="muted small">No soundbanks yet.</p>'}</div>
    ${ro ? '' : `<div class="sb-actions">
      <button type="button" class="btn btn-sm" data-gb title="The Game Boy's sound chip: pulse, wave and noise channels">New Game Boy Soundbank</button>
      <button type="button" class="btn btn-sm" data-import title="Add a soundbank exported from another board">Import…</button></div>`}`;
  for (const row of $$('.sb-item', body)) {
    const k = +row.dataset.k;
    bankInfo(banks[k]).then(info => { $('[data-bytes]', row).innerHTML = infoText(info); });
    $('[data-edit]', row)?.addEventListener('click', () => editSoundbank(k));
    $('[data-export]', row).addEventListener('click', () => {
      const b = banks[k];
      saveBlob(new Blob([JSON.stringify(b, null, 1)], { type: 'application/json' }), `${(b.name || 'soundbank').replace(/[^\w -]+/g, '')}.soundbank.json`);
    });
    $('[data-del]', row)?.addEventListener('click', async () => {
      if (!await confirmDialog(`Delete the soundbank "${banks[k].name}"? Songs that play it go back to a game soundbank.`,
        { title: 'Delete Soundbank', yes: 'Delete', danger: true })) return;
      store.op('setBoardSoundbank', { index: k, delete: true }, 'Delete soundbank');
    });
  }
  $('[data-gb]', body)?.addEventListener('click', async () => {
    const bank = await api('/api/soundbanks/gameboy');
    await store.op('setBoardSoundbank', { index: banks.length, soundbank: bank }, 'Add Game Boy soundbank');
  });
  $('[data-import]', body)?.addEventListener('click', async () => {
    const file = await pickFile('.json,application/json');
    if (!file) return;
    let bank;
    try {
      bank = JSON.parse(await file.text());
    } catch {
      toast('That file is not a soundbank.', 'warn');
      return;
    }
    if (!Array.isArray(bank?.instruments)) {
      toast('That file is not a soundbank.', 'warn');
      return;
    }
    await store.op('setBoardSoundbank', { index: banks.length, soundbank: bank }, 'Import soundbank');
  });
}

// ---------- the editor ----------

let audioEl = null;

async function play(path, body) {
  try {
    const res = await api(path, body, { raw: true });
    const url = URL.createObjectURL(await res.blob());
    if (!audioEl) audioEl = new Audio();
    audioEl.pause();
    audioEl.src = url;
    await audioEl.play();
  } catch (e) {
    toast(e.message, 'error');
  }
}

/** Opens the editor for the board's soundbank k. */
export async function editSoundbank(k) {
  const board = store.board;
  const bank = structuredClone(board.soundbanks[k]);
  const songs = (board.audioData || []).filter(a => a.data);
  const body = document.createElement('div');
  body.className = 'sb-editor';

  const row = (inst, i) => {
    const src = inst.source;
    let extra = '';
    if (src.type === 'wave') {
      extra = `<input class="input mono sb-pattern" data-f="pattern" maxlength="32" value="${esc(src.pattern)}" title="The Game Boy wave channel's 32 steps, one hex digit (0-F) each">`;
    } else if (src.type === 'sample') {
      extra = `<span class="sb-sample"><span class="muted small">Plays as key</span>
        <input class="input mono sb-tiny" type="number" min="0" max="127" data-f="key" value="${src.key ?? 60}" title="The MIDI note the recording sounds as (60 = middle C)">
        <span class="muted small">${src.loopEnd ? 'loops' : 'plays once'}</span></span>`;
    }
    const opts = SOURCES.filter(([key]) => key !== 'sample' || src.type === 'sample')
      .map(([key, label]) => `<option value="${key}" ${key === sourceKey(src) ? 'selected' : ''}>${label}</option>`).join('');
    const num = (f, v, max, tip) => `<input class="input mono sb-tiny" type="number" min="0" max="${max}" data-f="${f}" value="${v}" title="${tip}">`;
    return `<tr data-row="${i}">
      <td class="num">${i}</td>
      <td><input class="input sb-iname" data-f="name" value="${esc(inst.name || '')}"></td>
      <td><div class="sb-src"><select class="input" data-f="type">${opts}</select>${extra}</div></td>
      <td>${num('volume', inst.volume ?? 110, 127, 'Volume, 0-127')}</td>
      <td class="sb-env">${num('attack', inst.attack ?? 0, 60000, 'Attack: milliseconds to full volume')}${num('decay', inst.decay ?? 1, 60000, 'Decay: milliseconds to the sustain level')}${num('sustain', inst.sustain ?? 127, 127, 'Sustain level, 0-127')}${num('release', inst.release ?? 20, 60000, 'Release: milliseconds to fade after the note ends')}</td>
      <td class="sb-row-btns"><button type="button" class="btn btn-ghost btn-sm btn-icon" data-play title="Play middle C (or the recording's key)">▶</button>
        <button type="button" class="btn btn-ghost btn-sm btn-icon" data-up title="Move up (lower program number)" ${i ? '' : 'disabled'}>↑</button>
        <button type="button" class="btn btn-ghost btn-sm btn-icon" data-down title="Move down" ${i < bank.instruments.length - 1 ? '' : 'disabled'}>↓</button>
        <button type="button" class="btn btn-ghost btn-sm btn-icon" data-x title="Remove" ${bank.instruments.length > 1 ? '' : 'disabled'}>✕</button></td></tr>`;
  };

  const paint = () => {
    body.innerHTML = `
      <div class="field"><span class="field-label">Name</span><input class="input sb-bankname" value="${esc(bank.name || '')}"></div>
      <div class="sb-table-wrap"><table class="table sb-table"><thead><tr><th class="num" title="Program number">#</th><th>Instrument</th><th>Sound</th>
        <th title="Volume">Vol</th><th title="Attack (ms), decay (ms), sustain (0-127), release (ms)">Attack · Decay · Sustain · Release</th><th></th></tr></thead>
        <tbody>${bank.instruments.map(row).join('')}</tbody></table></div>
      <div class="sb-actions">
        <button type="button" class="btn btn-sm" data-add="pulse:0.5">+ Pulse</button>
        <button type="button" class="btn btn-sm" data-add="wave">+ Wave</button>
        <button type="button" class="btn btn-sm" data-add="noise:0">+ Noise</button>
        <button type="button" class="btn btn-sm" data-wav title="A .wav recording; loop points in the file are kept">+ From WAV File…</button>
        <span class="sb-size muted small" data-size>…</span>
      </div>
      <div class="sb-preview">${songs.length ? `<select class="input sb-song">${songs.map((a, j) => `<option value="${j}">${esc(a.name)}</option>`).join('')}</select>
        <button type="button" class="btn btn-sm" data-song title="Play the song with these instruments (as the game will)">▶ Preview Song</button>
        <button type="button" class="btn btn-sm" data-stop title="Stop">■</button>`
        : '<span class="muted small">Add a custom song (MIDI) to preview it with these instruments.</span>'}</div>`;
    refreshSize();
  };

  let sizeTimer = null;
  const refreshSize = () => {
    clearTimeout(sizeTimer);
    sizeTimer = setTimeout(async () => {
      const el = $('[data-size]', body);
      if (el) el.innerHTML = infoText(await bankInfo(bank));
    }, 250);
  };

  body.addEventListener('input', e => {
    const f = e.target.dataset.f;
    if (e.target.classList.contains('sb-bankname')) { bank.name = e.target.value; return; }
    const tr = e.target.closest('tr[data-row]');
    if (!tr || !f || f === 'type') return;
    const inst = bank.instruments[+tr.dataset.row];
    if (f === 'name') inst.name = e.target.value;
    else if (f === 'pattern') {
      const v = e.target.value.toUpperCase();
      e.target.classList.toggle('bad', !/^[0-9A-F]{32}$/.test(v));
      if (/^[0-9A-F]{32}$/.test(v)) { inst.source = { ...inst.source, pattern: v }; refreshSize(); }
    } else if (f === 'key') {
      const v = parseInt(e.target.value, 10);
      if (v >= 0 && v <= 127) inst.source = { ...inst.source, key: v };
    } else {
      const v = Number(e.target.value);
      if (!isNaN(v) && e.target.value !== '') inst[f] = v;
    }
  });
  body.addEventListener('change', e => {
    if (e.target.dataset.f !== 'type') return;
    const inst = bank.instruments[+e.target.closest('tr').dataset.row];
    const src = sourceFromKey(e.target.value, inst.source);
    if (src) inst.source = src;
    paint();
  });
  body.addEventListener('click', async e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const tr = btn.closest('tr[data-row]');
    const i = tr ? +tr.dataset.row : -1;
    const list = bank.instruments;
    if (btn.dataset.play !== undefined) {
      const inst = list[i];
      play('/api/soundbanks/note', { instrument: inst, key: inst.source.type === 'sample' ? (inst.source.key ?? 60) : 60, seconds: 1 });
    } else if (btn.dataset.up !== undefined && i > 0) {
      [list[i - 1], list[i]] = [list[i], list[i - 1]]; paint();
    } else if (btn.dataset.down !== undefined && i < list.length - 1) {
      [list[i + 1], list[i]] = [list[i], list[i + 1]]; paint();
    } else if (btn.dataset.x !== undefined && list.length > 1) {
      list.splice(i, 1); paint();
    } else if (btn.dataset.add) {
      const src = sourceFromKey(btn.dataset.add);
      list.push(newInstrument(SOURCES.find(([key]) => key === btn.dataset.add)?.[1] || 'Instrument', src));
      paint();
    } else if (btn.dataset.wav !== undefined) {
      const file = await pickFile('.wav,audio/wav,audio/x-wav');
      if (!file) return;
      const key = 60;
      try {
        const res = await api(`/api/soundbanks/import-wav?name=${encodeURIComponent(file.name)}&key=${key}`, file);
        list.push(res.instrument);
        paint();
      } catch (err) {
        toast(err.message, 'error');
      }
    } else if (btn.dataset.song !== undefined) {
      play('/api/soundbanks/preview', { soundbank: bank, midi: songs[+$('.sb-song', body).value].data });
    } else if (btn.dataset.stop !== undefined) {
      audioEl?.pause();
    }
  });

  paint();
  const ok = await dialog({
    title: 'Edit Soundbank', body, wide: true,
    buttons: [{ label: 'Cancel', value: false }, { label: 'Save', value: true, kind: 'primary' }],
  });
  audioEl?.pause();
  if (!ok) return;
  await store.op('setBoardSoundbank', { index: k, soundbank: bank }, 'Edit soundbank');
}
