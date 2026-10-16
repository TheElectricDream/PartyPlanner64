// Mario Party text: the game's formatting as the ROM's strings carry it (colour tags such as
// <RED>, "\n", and private-use characters for the button, coin and star images), as the
// original's rich text editor (apps/partyplanner64/texteditor.tsx) showed it.
//
// toHtml(text)        the text drawn as the game would (colours, images);
// toEditable(text)    the text with each image character as a [TOKEN], for a <textarea>;
// fromEditable(text)  back to the game's characters;
// toPlain(text)       one line of plain text (lists, search results).
import { esc } from '../api.js';

/** Font colours: tag -> CSS colour (texteditor.tsx's colorStyleMap). */
export const COLORS = {
  DEFAULT: '#200E71', BLACK: '#000000', WHITE: '#FFFFFF', RED: '#E70014',
  GREEN: '#00AB29', BLUE: '#003EF9', PURPLE: '#E847CD', YELLOW: '#FFEA38',
};

const IMG = '/static/img/richtext/';

/** The image characters. token: how a <textarea> shows them. */
export const IMAGES = [
  { token: 'A', char: '　', img: 'A.png', desc: 'A button' },
  { token: 'B', char: '、', img: 'B.png', desc: 'B button' },
  { token: 'S', char: '【', img: 'S.png', desc: 'Start button' },
  { token: 'CUP', char: '。', img: 'Cup.png', desc: 'C-up button' },
  { token: 'CDOWN', char: '々', img: 'Cdown.png', desc: 'C-down button' },
  { token: 'CLEFT', char: '〄', img: 'Cleft.png', desc: 'C-left button' },
  { token: 'CRIGHT', char: '〃', img: 'Cright.png', desc: 'C-right button' },
  { token: 'Z', char: '〆', img: 'Z.png', desc: 'Z button' },
  { token: 'R', char: '】', img: 'R.png', desc: 'R button' },
  { token: 'ANALOG', char: '〇', img: 'analog.png', desc: 'Analog stick' },
  { token: 'COIN', char: '〈', img: 'coin.png', desc: 'Coin' },
  { token: 'STAR', char: '〉', img: 'star.png', desc: 'Star' },
  { token: 'HCOIN', char: '〒', glyph: '◌', desc: 'Hollow coin' },
  { token: 'HSTAR', char: '〓', glyph: '☆', desc: 'Hollow star' },
  { token: 'FEED', char: '〔', img: 'feed.png', desc: 'Feed a new page (the next text starts a new box)', advanced: true },
  { token: 'PAUSE', char: '〕', img: 'pause.png', desc: 'Pause until the player presses A', advanced: true },
];
const BY_CHAR = new Map(IMAGES.map(i => [i.char, i]));
const BY_TOKEN = new Map(IMAGES.map(i => [i.token, i]));
const PLAIN = {
  '　': 'Ⓐ', '、': 'Ⓑ', '。': '▲', '〃': '►', '〄': '◄', '々': '▼',
  '〆': 'Ⓩ', '〇': '🕹', '〈': '✪', '〉': '★', '【': 'Ⓢ', '】': 'Ⓡ',
  '〒': '◌', '〓': '☆', '〔': ' ⏎ ', '〕': ' ⏸ ',
};

/** The image for an image character, as HTML. */
export function imageHtml(info) {
  return info.img
    ? `<img class="mp-img" src="${IMG}${info.img}" alt="${esc(info.token)}" title="${esc(info.desc)}">`
    : `<span class="mp-glyph" title="${esc(info.desc)}">${info.glyph}</span>`;
}

/** The URL of an image's icon (for toolbars). */
export function imageUrl(info) {
  return info.img ? IMG + info.img : null;
}

/**
 * Draws game text as HTML: colours start at their tag and last until the next one.
 * @param {string} text
 * @param {{defaultColor?: string}=} opts
 */
export function toHtml(text, opts = {}) {
  let html = '';
  let open = false;
  const re = /<([A-Z]+)>|\{(\d+)\}|[　-〕]|\n|[^<{　-〕\n]+|[<{]/g;
  let m;
  while ((m = re.exec(text || ''))) {
    const tok = m[0];
    if (m[1] !== undefined) {
      const name = m[1];
      if (COLORS[name] || name === 'SEIZURE') {
        if (open) html += '</span>';
        html += name === 'SEIZURE'
          ? '<span class="mp-seizure" title="&lt;SEIZURE&gt;: flashing text">'
          : `<span style="color:${COLORS[name]}" data-color="${name}">`;
        open = true;
      } else {
        html += `<span class="mp-tag">${esc(tok)}</span>`;
      }
    } else if (m[2] !== undefined) {
      html += `<span class="mp-param" title="Filled in by the game (a name, a number…)">${esc(tok)}</span>`;
    } else if (BY_CHAR.has(tok)) {
      const info = BY_CHAR.get(tok);
      html += tok === '〔' ? `${imageHtml(info)}<br>` : imageHtml(info);
    } else if (tok === '\n') {
      html += '<br>';
    } else {
      html += esc(tok);
    }
  }
  if (open) html += '</span>';
  return html;
}

/** Replaces image characters with [TOKEN]s. */
export function toEditable(text) {
  return (text || '').replace(/[　-〕]/g, c => (BY_CHAR.has(c) ? `[${BY_CHAR.get(c).token}]` : c));
}

/** Replaces [TOKEN]s with the game's image characters. */
export function fromEditable(text) {
  return (text || '').replace(/\[([A-Z]+)\]/g, (all, t) => (BY_TOKEN.has(t) ? BY_TOKEN.get(t).char : all));
}

/** Plain text on one line (mpFormatToPlainText). */
export function toPlain(text) {
  return (text || '')
    .replace(/<\w+>/g, '')
    .replace(/[　-〕]/g, c => PLAIN[c] ?? c)
    .replace(/\s*\n\s*/g, ' ⏎ ')
    .trim();
}
