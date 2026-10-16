// Audio: the ROM's songs and sound effects (views/audio.tsx). The server renders WAVs that
// play in an <audio> element; songs export as MIDI and can be replaced with another MIDI.
import { $, $$, api, act, esc, loadCss, toast, download, pickFile, promptDialog, busy } from '../api.js';

const PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>';
const STOP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 7h10v10H7z"/></svg>';

let root = null;
let app = null;
let data = null;          // GET /api/audio
let tab = 'songs';
let filter = '';
let playing = null;       // {kind, table, index, name}
let player = null;

const hex = n => '0x' + n.toString(16).toUpperCase();
const label = (item, kind) => item.name || (kind === 'songs' ? `Song ${item.index}` : `Sound ${item.index}`);

export function init(container, theApp) {
  loadCss('audio');
  root = container;
  app = theApp;
  root.innerHTML = `<div class="layout audio-page">
      <aside class="sidebar">
        <section class="card">
          <div class="card-head"><h2>Player</h2><span class="pill" id="audState">Idle</span></div>
          <div class="aud-now" id="audNow"><span class="muted">Nothing playing. Press ▶ on a song or a sound.</span></div>
          <audio id="audPlayer" controls preload="none" title="The track playing"></audio>
          <div class="aud-player-row">
            <label class="toggle" title="Play the track again when it ends"><input type="checkbox" id="audLoop"><span></span>Loop</label>
            <button type="button" class="btn btn-sm" id="audStop" title="Stop playing" disabled>${STOP}<span>Stop</span></button>
          </div>
        </section>
        <section class="card">
          <div class="card-head"><h2>Find</h2></div>
          <input id="audFilter" class="input" placeholder="Name or number…" spellcheck="false" title="Show only tracks whose name or number contains this text">
          <label class="toggle aud-opt" title="Show each track's number (decimal and hexadecimal) beside its name"><input type="checkbox" id="audIdx"><span></span>Show Track Numbers</label>
        </section>
        <section class="card">
          <div class="card-head"><h2>About Audio</h2></div>
          <p class="hint aud-first">An experimental audio player. Songs are MIDI sequences played with the game's
            soundbanks; sound effects are samples. Replacing a song, or its soundbank, is written to the ROM
            when you save it.</p>
        </section>
      </aside>
      <main class="main">
        <div class="aud-head">
          <div class="tabs" role="tablist">
            <button type="button" data-tab="songs" class="active" title="Music: the game's MIDI sequences">Songs <span class="count" id="audSongCount">0</span></button>
            <button type="button" data-tab="sounds" title="Sound effects: the game's samples">Sound Effects <span class="count" id="audSoundCount">0</span></button>
          </div>
        </div>
        <div class="aud-scroll" id="audScroll"></div>
      </main>
    </div>`;
  player = $('#audPlayer', root);
  player.addEventListener('ended', () => setPlaying(null));
  player.addEventListener('playing', () => setState('Playing', 'live'));
  player.addEventListener('pause', () => { if (playing && !player.ended) setState('Paused', ''); });
  player.addEventListener('error', () => {
    if (!playing) return;
    const what = playing;
    const src = player.currentSrc || player.src;
    setPlaying(null);
    // The server's message (e.g. songs can't be rendered here).
    fetch(src).then(r => r.json()).then(d => toast(d.error || `Couldn't play ${what.name}.`, 'error', 9000))
      .catch(() => toast(`Couldn't play ${what.name}.`, 'error'));
  });
  $('#audLoop', root).addEventListener('change', e => { player.loop = e.target.checked; });
  $('#audStop', root).addEventListener('click', () => setPlaying(null));
  $('#audFilter', root).addEventListener('input', e => {
    filter = e.target.value.trim().toLowerCase();
    render();
  });
  $('#audIdx', root).addEventListener('change', render);
  for (const b of $$('[data-tab]', root)) {
    b.addEventListener('click', () => {
      tab = b.dataset.tab;
      for (const o of $$('[data-tab]', root)) o.classList.toggle('active', o === b);
      render();
    });
  }
  $('#audScroll', root).addEventListener('click', onClick);
  app.on('rom', () => {
    data = null;
    setPlaying(null);
    if (app.page === 'audio') load();
  });
  $('#audIdx', root).checked = !!app.setting('ui.advanced');
}

export function show() {
  if (!data) load();
}

export function hide() {
  setPlaying(null);
}

async function load() {
  if (!app.state?.rom) {
    data = null;
    render();
    return;
  }
  $('#audScroll', root).innerHTML = '<div class="empty-state aud-empty"><b>Reading the Audio…</b></div>';
  data = await act(() => api('/api/audio')) || null;
  render();
}

function setState(text, kind) {
  const pill = $('#audState', root);
  pill.textContent = text;
  pill.className = 'pill' + (kind ? ` ${kind}` : '');
}

function setPlaying(item) {
  playing = item;
  if (!item) {
    player.pause();
    player.removeAttribute('src');
    player.load();
    setState('Idle', '');
    $('#audNow', root).innerHTML = '<span class="muted">Nothing playing. Press ▶ on a song or a sound.</span>';
  } else {
    $('#audNow', root).innerHTML = `<b>${esc(item.name)}</b>
      <span class="muted small">${item.kind === 'songs' ? 'Song' : 'Sound effect'} · table ${item.table} · ${item.index} (${hex(item.index)})</span>`;
    setState(item.kind === 'songs' ? 'Rendering…' : 'Loading…', 'warn');
    player.src = `/api/audio/${item.kind === 'songs' ? 'song' : 'sound'}/${item.table}/${item.index}.wav`;
    player.play().catch(() => {});
  }
  updatePlayButtons();
}

/** Shows ■ on the track playing, ▶ on the others. */
function updatePlayButtons() {
  const item = playing;
  $('#audStop', root).disabled = !item;
  for (const b of $$('[data-play]', root)) {
    const on = !!item && b.dataset.play === `${item.kind}/${item.table}/${item.index}`;
    b.innerHTML = on ? STOP : PLAY;
    b.classList.toggle('playing', on);
    b.title = on ? 'Stop' : b.dataset.title;
  }
}

function render() {
  const box = $('#audScroll', root);
  $('#audSongCount', root).textContent = data ? data.songs.reduce((n, t) => n + t.items.length, 0) : 0;
  $('#audSoundCount', root).textContent = data ? data.sounds.reduce((n, t) => n + t.items.length, 0) : 0;
  if (!app.state?.rom) {
    box.innerHTML = '<div class="empty-state aud-empty"><b>No ROM Open</b><span>Open a ROM to hear its songs and sound effects.</span></div>';
    return;
  }
  if (!data) {
    box.innerHTML = '<div class="empty-state aud-empty"><b>Audio Unavailable</b><span>The ROM\'s audio couldn\'t be read.</span></div>';
    return;
  }
  const tables = tab === 'songs' ? data.songs : data.sounds;
  const showIdx = $('#audIdx', root).checked;
  let html = '';
  let shownTotal = 0;
  for (const table of tables) {
    const items = table.items.filter(it => !filter
      || label(it, tab).toLowerCase().includes(filter) || `${it.index}` === filter || hex(it.index).toLowerCase() === filter);
    if (!items.length) continue;
    shownTotal += items.length;
    html += `<section class="card aud-table">
      <div class="card-head"><h2>${tab === 'songs' ? 'Song' : 'Sound'} Table ${table.table}</h2>
        <span class="muted small">${table.items.length} ${tab === 'songs' ? 'songs' : 'sounds'}${tab === 'songs' ? ` · ${table.soundbankCount} soundbanks` : ''}</span></div>
      <table class="table"><thead><tr><th></th><th>Name</th>${showIdx ? '<th class="num">Number</th>' : ''}
        ${tab === 'songs' ? '<th class="num" title="Which of the table\'s soundbanks (instruments) the song plays with">Soundbank</th>' : '<th class="num" title="The sample rate">Rate</th>'}
        <th></th></tr></thead><tbody>
      ${items.map(it => row(table, it, showIdx)).join('')}
      </tbody></table></section>`;
  }
  box.innerHTML = html || (filter
    ? `<div class="empty-state aud-empty"><b>No Matches</b><span>No track matches “${esc(filter)}”.</span></div>`
    : '<div class="empty-state aud-empty"><b>Nothing Here</b><span>This ROM has no tracks of this kind.</span></div>');
  updatePlayButtons();
}

function row(table, it, showIdx) {
  const name = label(it, tab);
  const id = `${tab}/${table.table}/${it.index}`;
  const playTitle = `Play ${name}`;
  const songActions = `
      <button type="button" class="btn btn-ghost btn-sm" data-act="midi" title="Download the song as a standard MIDI file">MIDI</button>
      <button type="button" class="btn btn-ghost btn-sm" data-act="replace" title="Replace the song with a MIDI file of your own (written when you save the ROM)">Replace…</button>`;
  const soundActions = `
      <button type="button" class="btn btn-ghost btn-sm" data-act="wav" title="Download the sound as a .wav file">WAV</button>`;
  return `<tr data-id="${id}" data-name="${esc(name)}" data-table="${table.table}" data-index="${it.index}">
      <td class="aud-play-cell"><button type="button" class="btn btn-sm btn-icon aud-play" data-play="${id}" data-title="${esc(playTitle)}" title="${esc(playTitle)}">${PLAY}</button></td>
      <td><span class="${it.name ? '' : 'muted'}" title="${it.index}, ${hex(it.index)}">${esc(name)}</span></td>
      ${showIdx ? `<td class="num">${it.index} <span class="muted">${hex(it.index)}</span></td>` : ''}
      ${tab === 'songs'
        ? `<td class="num"><button type="button" class="btn btn-ghost btn-sm aud-bank" data-act="bank" title="Change the soundbank the song plays with">${it.soundbankIndex ?? '?'}</button></td>`
        : `<td class="num muted">${it.sampleRate ? `${(it.sampleRate / 1000).toFixed(it.sampleRate % 1000 ? 2 : 0)} kHz` : ''}</td>`}
      <td class="aud-actions">${tab === 'songs' ? songActions : soundActions}</td>
    </tr>`;
}

async function onClick(e) {
  const tr = e.target.closest('tr[data-id]');
  if (!tr) return;
  const t = +tr.dataset.table;
  const i = +tr.dataset.index;
  const name = tr.dataset.name;
  if (e.target.closest('[data-play]')) {
    const same = playing && `${playing.kind}/${playing.table}/${playing.index}` === tr.dataset.id;
    setPlaying(same ? null : { kind: tab, table: t, index: i, name });
    return;
  }
  const btn = e.target.closest('[data-act]');
  if (!btn) return;
  switch (btn.dataset.act) {
    case 'midi':
      await act(async () => toast(`Saved ${await download(`/api/audio/song/${t}/${i}.mid`, undefined, 'music.mid')}.`, 'success', 3000));
      break;
    case 'wav':
      await act(async () => toast(`Saved ${await download(`/api/audio/sound/${t}/${i}.wav?download=1`, undefined, 'sound.wav')}.`, 'success', 3000));
      break;
    case 'replace': {
      const file = await pickFile('.mid,.midi,audio/midi');
      if (!file) return;
      await busy(`Converting ${file.name}…`, async () => {
        await api(`/api/audio/song/${t}/${i}/replace`, file);
        if (playing?.kind === 'songs' && playing.table === t && playing.index === i) setPlaying(null);
        toast(`Replaced ${name} with ${file.name}. Save the ROM to keep it.`, 'success');
      });
      break;
    }
    case 'bank': {
      const table = data.songs.find(s => s.table === t);
      const item = table.items.find(it => it.index === i);
      const value = await promptDialog(`The soundbank ${name} plays with: 0 through ${table.soundbankCount - 1}.`,
        { title: 'Change Soundbank', value: String(item.soundbankIndex ?? 0) });
      if (value === null) return;
      await act(async () => {
        const res = await api(`/api/audio/song/${t}/${i}/soundbank`, { soundbankIndex: Number(value) });
        item.soundbankIndex = res.soundbankIndex;
        render();
        toast(`${name} now plays with soundbank ${res.soundbankIndex}.`, 'success');
      });
      break;
    }
    default:
  }
}
