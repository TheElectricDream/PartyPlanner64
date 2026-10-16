// About: the version, where to learn more and get help, credits, the command line.
import { $, esc, loadCss, toast } from '../api.js';

const GITHUB = 'https://github.com/PartyPlanner64/PartyPlanner64';

const link = (href, text, title) =>
  `<a href="${href}" target="_blank" rel="noopener noreferrer" title="${esc(title || href)}">${esc(text)}</a>`;

let app = null;
let root = null;

export function init(container, theApp) {
  loadCss('about');
  app = theApp;
  root = container;
  container.innerHTML = `<div class="scroll-page about-page">
      <section class="about-hero">
        <img src="/static/img/logoloading.png" alt="PartyPlanner64" class="about-logo">
        <div class="about-hero-text">
          <h2>PartyPlanner64</h2>
          <p class="about-tagline">A Mario Party N64 board editor: create boards and play them in a Mario Party ROM,
            on an emulator or on real hardware.</p>
          <div class="about-meta">
            <span class="pill" id="aboutVersion" title="The version of this PartyPlanner64 (the Python package)">Version …</span>
            <span class="pill" id="aboutRom" title="The ROM open in the editor"></span>
            <span class="pill" title="PartyPlanner64 is in the public domain">Public Domain</span>
          </div>
        </div>
      </section>

      <div class="grid about-grid">
        <section class="card">
          <div class="card-head"><h2>Want More PartyPlanner64?</h2></div>
          <ul class="about-list">
            <li>Read the ${link(`${GITHUB}/wiki/Creating-a-Board`, 'usage tutorial', 'Creating a board: common mistakes to avoid (the wiki)')}
              before making a board, and the ${link(`${GITHUB}/wiki`, 'documentation', 'The wiki: the editor, and technical notes on the games')}.</li>
            <li>${link(GITHUB, 'Contribute', 'The source code on GitHub')} to development on GitHub.</li>
            <li>Write or view ${link(`${GITHUB}/issues`, 'bugs and enhancement requests', 'The issue tracker on GitHub')}.</li>
            <li>See how to ${link(`${GITHUB}/wiki/Emulator-Setup`, 'set up an emulator', 'Emulators must use 8 MB of RAM (the Expansion Pak)')}:
              the games need the Expansion Pak (8 MB of RAM).</li>
            <li>Follow ${link('https://twitter.com/PartyPlanner64', '@PartyPlanner64', 'PartyPlanner64 on Twitter')} on Twitter.</li>
          </ul>
        </section>

        <section class="card">
          <div class="card-head"><h2>Community</h2></div>
          <a class="about-mpl" href="http://mariopartylegacy.com/" target="_blank" rel="noopener noreferrer" title="Mario Party Legacy: the Mario Party community">
            <img src="/static/img/mpllogo.png" alt="Mario Party Legacy">
          </a>
          <ul class="about-list">
            <li>Check out the discussion in the ${link('https://discord.gg/BQMuUpM', 'Discord chat', 'The Mario Party Legacy Discord')}.</li>
            <li>Post your creations to the ${link('http://www.mariopartylegacy.com/forum/index.php?action=downloads', 'downloads page', 'Mario Party Legacy downloads')}.</li>
          </ul>
          <a class="about-shirt" href="https://teespring.com/stores/partyplanner64" target="_blank" rel="noopener" title="Official PartyPlanner64 merchandise">
            <img src="/static/img/about/shirt.png" alt=""><span>Official Merchandise</span></a>
        </section>

        <section class="card">
          <div class="card-head"><h2>Supported ROMs</h2></div>
          <p class="hint about-first">A ROM isn't needed to create and edit boards; to play them, open one of the
            NTSC USA ROMs (edited ROMs can be re-opened):</p>
          <table class="table about-roms">
            <thead><tr><th>Game</th><th title="The MD5 checksum of the original ROM file">MD5</th></tr></thead>
            <tbody>
              <tr><td>Mario Party (U)</td><td class="mono">8BC2712139FBF0C56C8EA835802C52DC</td></tr>
              <tr><td>Mario Party 2 (U)</td><td class="mono">04840612A35ECE222AFDB2DFBF926409</td></tr>
              <tr><td>Mario Party 3 (U)</td><td class="mono">76A8BBC81BC2060EC99C9645867237CC</td></tr>
            </tbody>
          </table>
          <p class="hint">Reported to work: Project64 2.3, Mupen64plus, Nemu64. Project64 1.6 has issues.</p>
        </section>

        <section class="card">
          <div class="card-head"><h2>Command Line</h2>
            <button type="button" class="btn btn-sm" id="aboutCopyCli" title="Copy the command that lists the commands">Copy</button></div>
          <p class="hint about-first">This PartyPlanner64 is a Python program: the editor runs on your computer, and this
            page talks to it. The same program works on ROMs and boards without the page:</p>
          <pre class="about-cli"><span class="muted"># the web app (this page)</span>
python -m partyplanner64
<span class="muted"># every command and option</span>
python -m partyplanner64 --help</pre>
          <p class="hint">Your boards, events and settings are kept in the data folder
            (<span class="mono">~/.partyplanner64</span> unless <span class="mono">--data-dir</span> says otherwise).</p>
        </section>

        <section class="card">
          <div class="card-head"><h2>Credits</h2></div>
          <ul class="about-list">
            <li>PartyPlanner64 and its ${link(`${GITHUB}/graphs/contributors`, 'contributors', 'Everyone who contributed to PartyPlanner64')},
              who wrote the original TypeScript editor and worked out the games' formats.</li>
            <li>The Python port keeps the original's ROM work and board files: boards made with the
              web editor open here, and the other way round.</li>
            <li>Built with ${link('https://threejs.org/', 'three.js', 'The 3D model viewer')},
              ${link('https://codemirror.net/', 'CodeMirror', 'The event code editor')},
              ${link('https://python-pillow.org/', 'Pillow', 'Images')} and the
              ${link('https://github.com/alexfru/SmallerC', 'Smaller C', 'The compiler for events written in C')} compiler.</li>
          </ul>
          <p class="about-disclaimer">PartyPlanner64 is not affiliated with Nintendo or Hudson.<br>
            Mario Party is a registered trademark of Nintendo.</p>
        </section>
      </div>
    </div>`;
  $('#aboutCopyCli', root).addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText('python -m partyplanner64 --help');
      toast('Copied: python -m partyplanner64 --help', 'success', 2500);
    } catch {
      toast('Copying is blocked by the browser.', 'warn');
    }
  });
  app.on('state', render);
  render();
}

export function show() {
  render();
}

function render() {
  const s = app.state;
  $('#aboutVersion', root).textContent = `Version ${s?.version || 'unknown'}`;
  const rom = s?.rom;
  const pill = $('#aboutRom', root);
  pill.textContent = rom ? (rom.title || rom.gameName) : 'No ROM Open';
  pill.className = 'pill' + (rom ? ' ok' : '');
}
