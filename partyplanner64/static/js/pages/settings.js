// Settings: every editor setting, grouped as the original's settings view grouped them,
// saved on the server (POST /api/settings). The original's colour themes ("classic",
// "dark-gray") are gone: the page has a single dark design.
import { $, $$, api, act, esc, loadCss, toast, confirmDialog } from '../api.js';

/**
 * The settings, by group. advanced: shown only with Advanced Features on (as in the original).
 * Ids are the original's.
 */
const GROUPS = [
  {
    name: 'Interface',
    desc: 'How the editor behaves, and which of its tools it shows.',
    items: [
      { id: 'ui.advanced', name: 'Advanced Features',
        desc: 'Enables infrequently used, potentially complicated, and developer features: the Strings page, more settings, and more options on other pages.' },
      { id: 'ui.debug', name: 'Debug Features', advanced: true,
        desc: 'Enables debug output and the Debug page, which may aid development.' },
      { id: 'ui.skipvalidation', name: 'Skip Overwrite Validation', advanced: true,
        desc: 'Allow boards to be written to the ROM regardless of warnings.' },
      { id: 'ui.showromboards', name: 'Show ROM Boards',
        desc: 'Show the boards parsed from the ROM in the editor\'s board list.' },
      { id: 'ui.allowallroms', name: 'Allow All ROMs', advanced: true,
        desc: 'Allows more than just the officially supported ROMs to attempt to load.' },
    ],
  },
  {
    name: 'ROM',
    desc: 'How the ROM is written when you save it.',
    items: [
      { id: 'write.branding', name: 'Include Branding',
        desc: 'Adds the PartyPlanner64 logo to the game\'s boot splash screens.' },
      { id: 'write.decompressed', name: 'Leave ROM Decompressed', advanced: true,
        desc: 'Leaves all files decompressed when saving a ROM, resulting in a larger file.' },
    ],
  },
  {
    name: 'Model Viewer',
    desc: 'The 3D view of the Models page, and its exports.',
    items: [
      { id: 'models.limitfps', name: 'Limit FPS',
        desc: 'Reduce the refresh rate (30 frames per second) for better performance.' },
      { id: 'models.limitAnimations', name: 'Limit Animations',
        desc: 'Limit the animations offered for a model to those in the same directory as the model.' },
      { id: 'models.useGLB', name: 'Use GLB Container for glTF',
        desc: 'Create a binary GLB file, instead of a .gltf JSON file, when exporting models to glTF.' },
    ],
  },
];

let root = null;
let app = null;

export function init(container, theApp) {
  loadCss('settings');
  root = container;
  app = theApp;
  root.innerHTML = `<div class="scroll-page settings-page">
      <div class="page-head">
        <div>
          <h2>Settings</h2>
          <p class="hint">Changes apply at once and are kept on this computer, in the data folder, for every
            page that uses the editor.</p>
        </div>
        <div class="set-head-actions">
          <span class="pill" id="setAdvancedPill" title="Advanced settings are shown when Advanced Features is on"></span>
          <button type="button" class="btn btn-sm" id="setReset" title="Put every setting back to its default">Reset to Defaults</button>
        </div>
      </div>
      <div class="grid settings-grid"></div>
    </div>`;
  $('#setReset', root).addEventListener('click', async () => {
    if (!await confirmDialog('Put every setting back to its default?', { title: 'Reset Settings', yes: 'Reset' })) return;
    await act(async () => {
      await api('/api/settings/reset', {});
      await app.refresh();
      toast('The settings are back to their defaults.', 'success', 3000);
    });
  });
  app.on('state', () => render());
  render();
}

export function show() {
  render();
}

function render() {
  if (!root) return;
  const settings = app.state?.settings || {};
  const advanced = !!settings['ui.advanced'];
  const pill = $('#setAdvancedPill', root);
  pill.textContent = advanced ? 'Advanced On' : 'Advanced Off';
  pill.className = 'pill' + (advanced ? ' ok' : '');
  const grid = $('.settings-grid', root);
  grid.innerHTML = GROUPS.map(group => {
    const items = group.items.filter(item => advanced || !item.advanced);
    const hidden = group.items.length - items.length;
    return `<section class="card">
        <div class="card-head"><h2>${esc(group.name)}</h2>
          <span class="muted small">${items.length} setting${items.length === 1 ? '' : 's'}</span></div>
        <p class="hint set-group-desc">${esc(group.desc)}</p>
        <div class="set-list">${items.map(item => settingRow(item, settings[item.id])).join('')}</div>
        ${hidden ? `<p class="hint set-more">${hidden} more with Advanced Features on.</p>` : ''}
      </section>`;
  }).join('');
  for (const input of $$('input[data-setting]', grid)) {
    input.addEventListener('change', () => save(input.dataset.setting, input.checked, input));
  }
}

function settingRow(item, value) {
  const title = `${item.desc} (${item.id})`;
  return `<label class="set-row" title="${esc(title)}">
      <span class="set-text">
        <span class="set-name">${esc(item.name)}${item.advanced ? ' <span class="set-adv">Advanced</span>' : ''}</span>
        <span class="set-desc">${esc(item.desc)}</span>
      </span>
      <span class="toggle"><input type="checkbox" data-setting="${esc(item.id)}" ${value ? 'checked' : ''}><span></span></span>
    </label>`;
}

async function save(id, value, input) {
  input.disabled = true;
  const ok = await act(async () => {
    await api('/api/settings', { [id]: value });
    await app.refresh();
    return true;
  });
  input.disabled = false;
  if (!ok) {
    input.checked = !value;
    return;
  }
  const item = GROUPS.flatMap(g => g.items).find(i => i.id === id);
  toast(`${item ? item.name : id}: ${value ? 'on' : 'off'}.`, 'success', 2500);
}
