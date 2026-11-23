// Test Play of one event: a test ROM of a small board whose spaces run it, started in the
// emulator (POST /api/playtest/event). The player starts on the start space; whatever the dice
// show, the move ends on (Land On) or passes (Walk Over) a space with the event. The players,
// coins and emulator are the board's Test Play options; the server keeps each event's settings.
import { $, $$, api, esc, toast, dialog } from '../../api.js';
import { playTestOptions } from '../../editor/playtest.js';

function option(value, name, selected) {
  return `<option value="${esc(value)}"${selected ? ' selected' : ''}>${esc(name)}</option>`;
}

/** One parameter's field. */
function paramField(param, value, spaces) {
  const name = esc(param.name);
  const label = `<span class="field-label"><span class="mono">${name}</span>
    <span class="muted">${esc(param.type)}</span></span>`;
  switch (param.type) {
    case 'Boolean':
      return `<label class="toggle ev-pt-bool" title="The value of ${name}">
        <input type="checkbox" data-param="${name}" data-kind="bool"${value ? ' checked' : ''}><span></span>
        <span class="mono">${name}</span></label>`;
    case 'Number':
    case '+Number':
      return `<label class="field">${label}
        <input class="input" type="number" step="1" data-param="${name}" data-kind="num"
          ${param.type === '+Number' ? 'min="1"' : ''} value="${esc(value)}"></label>`;
    case 'Space':
      return `<label class="field">${label}
        <select class="input" data-param="${name}" data-kind="space">
          ${spaces.map(s => option(s.index, s.name, s.index === value)).join('')}</select></label>`;
    case 'Space[]':
      return `<div class="field">${label}
        <div class="ev-pt-spaces" data-param="${name}" data-kind="spaces">
          ${spaces.map(s => `<label class="ev-pt-space" title="${esc(s.name)}">
            <input type="checkbox" value="${s.index}"${(value || []).includes(s.index) ? ' checked' : ''}>
            ${esc(s.index === 0 ? 'Start' : s.index === 1 ? 'Invisible' : s.name.replace('Loop space ', ''))}</label>`).join('')}
        </div></div>`;
    default:     // Number[]: a list
      return `<label class="field">${label}
        <input class="input mono" data-param="${name}" data-kind="list" value="${esc((value || []).join(', '))}"
          placeholder="e.g. 1, 2, 3" spellcheck="false"></label>`;
  }
}

/** Reads the dialog into settings; null (with a toast) for a bad value. */
function readSettings(body) {
  const settings = {
    activation: Number($('[data-set="activation"]', body).value),
    spaceType: Number($('[data-set="spaceType"]', body).value),
    parameterValues: {},
  };
  for (const el of $$('[data-param]', body)) {
    const name = el.dataset.param;
    switch (el.dataset.kind) {
      case 'bool': settings.parameterValues[name] = el.checked; break;
      case 'num':
      case 'space': {
        const n = Number(el.value);
        if (el.value.trim() === '' || !Number.isInteger(n)) {
          toast(`${name} must be a whole number.`, 'warn');
          return null;
        }
        settings.parameterValues[name] = n;
        break;
      }
      case 'spaces':
        settings.parameterValues[name] = $$('input:checked', el).map(i => Number(i.value));
        break;
      default: {
        const parts = el.value.split(',').map(s => s.trim()).filter(Boolean);
        if (parts.some(p => !Number.isInteger(Number(p)))) {
          toast(`${name} is a list of whole numbers.`, 'warn');
          return null;
        }
        settings.parameterValues[name] = parts.map(Number);
      }
    }
  }
  return settings;
}

/** Starts the emulator on a test of the event; its code is as given (saved or not).
 *  settings: what to use instead of the event's saved settings (after the dialog). */
async function launch(code, language, settings) {
  $('#busyText').textContent = 'Building the event\'s test ROM…';
  $('#busy').hidden = false;
  let res = null;
  let failed = null;
  try {
    res = await api('/api/playtest/event', { code, language, settings });
  } catch (e) {
    failed = e;
  } finally {
    $('#busy').hidden = true;
  }
  if (failed) {
    console.error(failed);
    await dialog({
      title: 'Test Play',
      body: `<div class="pt-error">${esc(failed.message)}</div>`,
      buttons: [{ label: 'Close', value: false }],
    });
    return false;
  }
  const how = res.settings.activation === 1 ? 'pass the event\'s space' : 'land on an event space';
  toast(`Testing ${res.event}: roll the dice to ${how}. The emulator is starting.`, 'success', 9000);
  return true;
}

/** The Test Play dialog of an event: how it is run, its parameters, then the test.
 *  pending: settings chosen before going to the Test Play options, shown again. */
export async function testPlayEvent(app, code, language, pending = null) {
  let info;
  try {
    info = await api('/api/playtest/event/info', { code, language });
  } catch (e) {
    toast(e.message, 'error', 9000);
    return;
  }
  const t = info.test;
  const s = pending || info.settings;
  const body = document.createElement('div');
  body.className = 'pt-options ev-pt';
  body.innerHTML = `
    <p class="hint">Starts the emulator on a small test board: a start space, then a loop of ${t.loopSpaces}
      spaces. The first player starts at the start space; whatever the dice show, the move ends on a space that
      runs <b>${esc(info.event.name)}</b> (or, for Walk Over, passes one).</p>
    ${info.reason ? `<div class="notice warn">${esc(info.reason)}</div>` : ''}
    <div class="ev-pt-row">
      <label class="field"><span class="field-label">Runs when the player…</span>
        <select class="input" data-set="activation"
          title="Land On: every loop space runs the event. Walk Over: the invisible space after the start runs it.">
          ${t.activations.map(a => option(a.id, a.name, a.id === s.activation)).join('')}</select></label>
      <label class="field"><span class="field-label">On spaces of type</span>
        <select class="input" data-set="spaceType" title="The type of the loop's spaces, which run the event">
          ${t.spaceTypes.map(x => option(x.id, x.name, x.id === s.spaceType)).join('')}</select></label>
    </div>
    ${t.parameters.length ? `<span class="field-label ev-pt-head">Parameters</span>
      <div class="ev-pt-params">${t.parameters.map(p => paramField(p, s.parameterValues[p.name], t.spaces)).join('')}</div>
      <p class="hint">Space parameters name the test board's spaces: the loop's spaces are numbered from the
        start, 1 to ${t.loopSpaces}.</p>` : ''}
    <p class="hint">The players, their coins and the emulator are the Test Play options.</p>`;
  const sync = () => {
    const walk = Number($('[data-set="activation"]', body).value) === 1;
    const type = $('[data-set="spaceType"]', body);
    type.disabled = walk;
    type.title = walk ? 'With Walk Over, the loop is blue spaces and the invisible space runs the event'
      : 'The type of the loop\'s spaces, which run the event';
  };
  body.addEventListener('change', sync);
  sync();

  const buttons = [{ label: 'Cancel', value: false }, { label: 'Players & Emulator…', value: 'options' }];
  if (info.supported) buttons.push({ label: 'Test Play', value: 'test', kind: 'primary' });
  const r = await dialog({ title: `Test Play: ${info.event.name}`, body, wide: true, buttons });
  if (!r) return;
  const settings = readSettings(body);
  if (!settings) return testPlayEvent(app, code, language, pending);
  if (r === 'options') {
    // Then back here, with what was chosen.
    await playTestOptions(app, { forEvent: true });
    return testPlayEvent(app, code, language, settings);
  }
  await launch(code, language, settings);
}
