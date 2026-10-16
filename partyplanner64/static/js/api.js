// Shared helpers for every page: the server API, toasts, dialogs, files and the busy overlay.

export const $ = (sel, el = document) => el.querySelector(sel);
export const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

/** Escapes text for use in HTML. */
export function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/**
 * Calls the server: GET without a body; otherwise POST the body (JSON, or raw bytes for a
 * Blob/ArrayBuffer/Uint8Array).
 * @param {string} path e.g. '/api/state'
 * @param {*=} body
 * @param {{method?: string, raw?: boolean}=} opts raw: return the Response (for files).
 * @return {!Promise<*>} The JSON answer; throws an Error with the server's message if it failed.
 */
export async function api(path, body, opts = {}) {
  const init = { method: opts.method || (body === undefined ? 'GET' : 'POST'), headers: {} };
  if (body !== undefined) {
    if (body instanceof Blob || body instanceof ArrayBuffer || ArrayBuffer.isView(body)) {
      init.headers['Content-Type'] = 'application/octet-stream';
      init.body = body;
    } else {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
  }
  const res = await fetch(path, init);
  if (opts.raw && res.ok) return res;
  let data = {};
  try {
    data = await res.json();
  } catch {
    // Not JSON.
  }
  if (!res.ok) {
    const err = new Error(data.error || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/** Shows a message in the corner for ms milliseconds. kind: info, success, warn, error. */
export function toast(message, kind = 'info', ms = 6000) {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), ms);
}

/** Runs an action, reporting its error (if any) as a toast. Returns its result. */
export async function act(fn) {
  try {
    return await fn();
  } catch (e) {
    console.error(e);
    toast(e.message, 'error', 9000);
    return undefined;
  }
}

/** Runs a long action under the busy overlay ("Saving ROM…"), reporting errors as toasts. */
export async function busy(text, fn) {
  $('#busyText').textContent = text;
  $('#busy').hidden = false;
  try {
    return await act(fn);
  } finally {
    $('#busy').hidden = true;
  }
}

/**
 * Shows a modal dialog and resolves with the button pressed (its value), or null if closed.
 * @param {{title: string, body: (string|Node), buttons?: !Array<{label: string, value: *,
 *     kind?: string}>, wide?: boolean, onOpen?: function(!HTMLElement)}} opts body is HTML.
 */
export function dialog({ title, body, buttons, wide = false, onOpen }) {
  const dlg = $('#appDialog');
  buttons = buttons || [{ label: 'OK', value: true, kind: 'primary' }];
  dlg.className = 'dialog' + (wide ? ' wide' : '');
  dlg.innerHTML = `<form method="dialog" class="dialog-inner">
      <div class="dialog-head"><h2>${esc(title)}</h2>
        <button type="button" class="btn btn-ghost btn-sm" data-close aria-label="Close">✕</button></div>
      <div class="dialog-body"></div>
      <div class="dialog-foot"><div>${buttons.map((b, i) =>
        `<button type="button" class="btn ${b.kind ? 'btn-' + b.kind : ''}" data-i="${i}">${esc(b.label)}</button>`
      ).join('')}</div></div></form>`;
  const bodyEl = $('.dialog-body', dlg);
  if (typeof body === 'string') bodyEl.innerHTML = body; else if (body) bodyEl.append(body);
  return new Promise(resolve => {
    let result = null;
    $$('[data-i]', dlg).forEach(btn => btn.addEventListener('click', () => {
      result = buttons[+btn.dataset.i].value;
      dlg.close();
    }));
    $('[data-close]', dlg).addEventListener('click', () => dlg.close());
    dlg.addEventListener('close', () => resolve(result), { once: true });
    dlg.showModal();
    if (onOpen) onOpen(bodyEl);
  });
}

/** Asks a yes/no question; resolves true for yes. */
export async function confirmDialog(message, { title = 'Are You Sure?', yes = 'OK', danger = false } = {}) {
  const r = await dialog({
    title, body: `<p>${esc(message)}</p>`,
    buttons: [{ label: 'Cancel', value: false }, { label: yes, value: true, kind: danger ? 'stop' : 'primary' }],
  });
  return r === true;
}

/** Asks for a line of text; resolves with it, or null if cancelled. */
export async function promptDialog(message, { title = 'PartyPlanner64', value = '', placeholder = '' } = {}) {
  let input;
  const r = await dialog({
    title,
    body: `<p>${esc(message)}</p><input class="input" value="${esc(value)}" placeholder="${esc(placeholder)}">`,
    buttons: [{ label: 'Cancel', value: false }, { label: 'OK', value: true, kind: 'primary' }],
    onOpen: el => {
      input = $('input', el);
      input.focus();
      input.select();
      input.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); $('[data-i="1"]', el.closest('dialog')).click(); }
      });
    },
  });
  return r === true ? input.value : null;
}

/**
 * Lets the user pick a file; resolves with the File, or null.
 * @param {string=} accept e.g. '.z64,.n64,.v64' or 'image/*'
 */
export function pickFile(accept = '') {
  return new Promise(resolve => {
    const old = $('#filePicker');
    const input = old.cloneNode();       // a fresh input fires change even for the same file
    old.replaceWith(input);
    input.accept = accept;
    input.addEventListener('change', () => resolve(input.files[0] || null), { once: true });
    input.addEventListener('cancel', () => resolve(null), { once: true });
    input.click();
  });
}

/** Reads a File as a data URL (for images). */
export function readDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

/** Saves a Blob (or text) as a download. */
export function saveBlob(blob, filename) {
  if (!(blob instanceof Blob)) blob = new Blob([blob]);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

/**
 * Downloads what an API path answers (GET, or POST with a body), named as the server says.
 * @return {!Promise<string>} The file name.
 */
export async function download(path, body, fallbackName = 'download') {
  const res = await api(path, body, { raw: true });
  const cd = res.headers.get('Content-Disposition') || '';
  const m = /filename\*=UTF-8''([^;]+)/.exec(cd) || /filename="?([^";]+)"?/.exec(cd);
  const name = m ? decodeURIComponent(m[1]) : fallbackName;
  saveBlob(await res.blob(), name);
  return name;
}

/** Adds a page's stylesheet (css/<name>.css) once. */
export function loadCss(name) {
  const href = `/static/css/${name}.css`;
  if (!document.querySelector(`link[href="${href}"]`)) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.append(link);
  }
}
