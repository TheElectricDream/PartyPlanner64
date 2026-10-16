// Screenshot of the board (screenshot.tsx): options, then a preview to save as a .png.
import { $, dialog, saveBlob, toast, act } from '../api.js';
import { store } from './store.js';
import { takeScreeny } from './renderer.js';
import { plainText } from './board.js';

const options = {
  renderConnections: true,
  renderCharacters: true,
  renderHiddenSpaces: true,
  renderBadges: true,
};

const labels = {
  renderConnections: ['Connections', 'Draw the lines between spaces'],
  renderCharacters: ['Characters', 'Draw Toad, Boo, Koopa, banks, item shops and other characters standing on spaces'],
  renderHiddenSpaces: ['Hidden Spaces', 'Draw the invisible spaces and the start space'],
  renderBadges: ['Badges', 'Draw the event, star and gate markers on spaces'],
};

export async function screenshotDialog() {
  const board = store.board;
  if (!board) return;
  let canvas = null;
  const body = document.createElement('div');
  body.className = 'shot';
  body.innerHTML = `<div class="shot-opts">${Object.entries(labels).map(([id, [text, title]]) =>
    `<label class="toggle" title="${title}"><input type="checkbox" data-opt="${id}" ${options[id] ? 'checked' : ''}><span></span>${text}</label>`).join('')}</div>
    <div class="shot-preview"><span class="muted">Rendering…</span></div>`;
  const render = async () => {
    canvas = await takeScreeny(board, { ...options, bgSrc: store.overrideBg || board.bg.src, library: store.library });
    const prev = $('.shot-preview', body);
    prev.innerHTML = '';
    canvas.className = 'shot-canvas';
    prev.append(canvas);
  };
  const r = await dialog({
    title: 'Screenshot', body, wide: true,
    buttons: [{ label: 'Close', value: false }, { label: 'Save PNG', value: true, kind: 'primary' }],
    onOpen: el => {
      for (const input of el.querySelectorAll('[data-opt]')) {
        input.addEventListener('change', () => {
          options[input.dataset.opt] = input.checked;
          render();
        });
      }
      render();
    },
  });
  if (r !== true || !canvas) return;
  await act(async () => {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    const name = `${plainText(board.name).trim() || 'Board'} Screenshot.png`;
    saveBlob(blob, name);
    toast(`Saved ${name}.`, 'success');
  });
}
