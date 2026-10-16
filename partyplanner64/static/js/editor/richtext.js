// The essentials of the original's rich text editor for game text (texteditor.tsx, MPEditor):
// the text with its button/coin/star image characters (shown as [TOKENS] while editing), a
// toolbar to insert them, a line limit, and a preview drawn as the game shows it.
import { esc } from '../api.js';
import { IMAGES, toHtml, toEditable, fromEditable, imageUrl } from '../lib/mptext.js';

// The images of the original's toolbar ("Insert image"): not the hollow coin/star or the
// advanced page feed / pause, which the board details left out (itemBlacklist ADVANCED).
const TOOLBAR = ['A', 'B', 'S', 'CUP', 'CDOWN', 'CLEFT', 'CRIGHT', 'Z', 'R', 'ANALOG', 'COIN', 'STAR'];

/**
 * Creates the editor in `el`.
 * opts: { value, maxlines, readonly, label, title, onChange(value) } (onChange on blur / Enter).
 * Returns { setValue(value), focus() }.
 */
export function createRichText(el, opts) {
  const tools = TOOLBAR.map(t => IMAGES.find(i => i.token === t)).filter(Boolean);
  el.classList.add('rt');
  el.innerHTML = `
    ${opts.readonly ? '' : `<div class="rt-toolbar" role="toolbar" aria-label="Insert image">${tools.map(i =>
      `<button type="button" class="rt-btn" data-token="${i.token}" title="Insert the ${esc(i.desc)} image">
        <img src="${imageUrl(i)}" alt="${esc(i.token)}"></button>`).join('')}</div>`}
    <textarea class="input rt-input" rows="${opts.maxlines || 2}" spellcheck="false" ${opts.readonly ? 'readonly' : ''}
      title="${esc(opts.title || '')}"></textarea>
    <div class="rt-preview" title="How the game shows it"></div>`;
  const ta = el.querySelector('textarea');
  const preview = el.querySelector('.rt-preview');
  let committed = opts.value || '';

  const update = () => {
    preview.innerHTML = toHtml(fromEditable(ta.value)) || '<span class="rt-empty">(empty)</span>';
  };
  const setValue = value => {
    committed = value || '';
    if (document.activeElement !== ta) ta.value = toEditable(committed);
    update();
  };
  const commit = () => {
    const v = fromEditable(ta.value);
    if (v !== committed) {
      committed = v;
      opts.onChange?.(v);
    }
  };
  setValue(opts.value);

  ta.addEventListener('input', update);
  ta.addEventListener('blur', commit);
  ta.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    // Return would create an additional line.
    if (opts.maxlines && ta.value.split('\n').length >= opts.maxlines) {
      e.preventDefault();
      commit();
    }
  });
  for (const btn of el.querySelectorAll('.rt-btn')) {
    btn.addEventListener('mousedown', e => e.preventDefault()); // keep the caret in the text
    btn.addEventListener('click', () => {
      const ins = `[${btn.dataset.token}]`;
      const s = ta.selectionStart ?? ta.value.length;
      const t = ta.selectionEnd ?? s;
      ta.value = ta.value.slice(0, s) + ins + ta.value.slice(t);
      ta.focus();
      ta.setSelectionRange(s + ins.length, s + ins.length);
      update();
      commit();
    });
  }
  return { setValue, focus: () => ta.focus(), get textarea() { return ta; } };
}
