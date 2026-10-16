# Porting PartyPlanner64 to Python

PartyPlanner64 was a TypeScript/React app. It is being reworked so that everything that can be
Python is Python: the library that reads and writes Mario Party ROMs, the board editor's state,
the server, and the command line. Only the browser user interface stays JavaScript (plain ES
modules, no build step). This file sets the conventions the port follows, so that modules ported
separately fit together.

The original TypeScript is the reference: the last TypeScript commit is `980d043`
("Ensure image preload comes after canvas initialization"). Port behaviour faithfully,
including the original comments that explain the game's data. Don't "improve" ROM-writing
logic: a ROM written by the Python port should be byte-identical to one written by the
TypeScript for the same input, wherever the operation is deterministic.

## Layout

| TypeScript | Python |
|---|---|
| `packages/lib/**` | `partyplanner64/lib/**` |
| `packages/lib/img/**` (assets written into ROMs) | `partyplanner64/lib/img/**` |
| `packages/lib/lib/SmallerC/smlrc.wasm` | `partyplanner64/lib/vendor/smlrc.wasm` |
| npm `mips-inst`, `mips-assembler` (MIT, same author) | `partyplanner64/lib/mips/` |
| `apps/partyplanner64/boardState.ts`, `boards.ts`, ... (Redux) | `partyplanner64/editor/` |
| (none: the browser held the state) | `partyplanner64/state.py`, `partyplanner64/server/` |
| `apps/partyplanner64/**/*.tsx` (React UI) | `partyplanner64/static/` (HTML, CSS, JS modules) |
| `apps/partyplanner64/img/**` | `partyplanner64/static/img/**` |
| `apps/cli` | `partyplanner64/cli.py` |
| `scripts/update-symbols.js` | `scripts/update_symbols.py` |

Tests are in `tests/`, mirroring the package (`tests/lib/test_compression.py`, ...), run with
`python -m pytest`.

## Names

- **Files**: `packages/lib/fs/mainfs.ts` -> `partyplanner64/lib/fs/mainfs.py`. Every path part is
  converted with the rule below and lower-cased; dots become underscores:
  `adapter/MP3.U.boardoverlay.ts` -> `adapter/mp3_u_boardoverlay.py`,
  `adapter/boardinfo.MP1.U.ts` -> `adapter/boardinfo_mp1_u.py`,
  `events/builtin/MP1/U/BooEvent1.ts` -> `events/builtin/mp1/u/boo_event1.py`,
  `utils/img/ImgPack.ts` -> `utils/img/img_pack.py`, `audio/ALBank.ts` -> `audio/al_bank.py`,
  `utils/c-compiler.ts` -> `utils/c_compiler.py`. Every directory has an `__init__.py`.
- **Functions, methods, variables, parameters**: snake_case by this rule (Python):
  ```python
  re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()
  ```
  `getROMAdapter` -> `get_rom_adapter`, `getHVQFS` -> `get_hvqfs`, `readBackground` ->
  `read_background`, `RGBA5551fromRGBA32` -> `rgba5551from_rgba32` (keep what the rule gives,
  even when odd, so that others can predict it). Private stays private: `_pullBoardFromRom` ->
  `_pull_board_from_rom`.
- **Classes** keep their names: `MainFS`, `HVQFS`, `ROM`, `AdapterBase`, `ChainSplit1`, `FORM`.
- **Enums** keep their member names (`Space.BLUE`, `Game.MP3_USA`); numeric ones are `IntEnum`,
  string ones `(str, Enum)`, so they compare equal to the plain values found in board JSON.
- **Constants** keep their names (`EVENT_MEM_SIZE`).
- Special cases: `$$log` -> `log`, `$$hex` -> `hexstr`, `assert` -> `assert_` (all in
  `partyplanner64.lib.utils.debug`); `isDebug`/`setDebug` -> `partyplanner64.lib.debug`.
- **Module singletons** stay singletons: `romhandler` (`partyplanner64.lib.romhandler.romhandler`),
  the adapter registry, the event library.

## Data

- **Board JSON is unchanged.** Boards (`IBoard`), spaces, event instances, and everything saved
  to or loaded from `.json` board files are plain `dict`/`list` values with the original
  **camelCase keys** (`board["bg"]["src"]`, `space["subtype"]`, `event["activationType"]`).
  Board files written by the TypeScript editor must load, and files the Python writes must load in
  the TypeScript editor. Enum values in them are the plain numbers/strings.
- Interfaces that are not saved (`IBoardInfo`, `ISceneInfo`, `IEventParseInfo`,
  `IEventWriteInfo`, `IAdapterOptions`, ...) are **dicts with snake_case keys** by the naming rule
  (`board_info["bg_dir"]`, `info["cur_space_index"]`), so modules ported separately agree on them.
  Use `.get()` where the TypeScript field was optional.
- Events (`IEvent`, built-in or custom) are objects with snake_case attributes: `id`, `name`,
  `activation_type`, `execution_type`, `fake_event`, `supported_games`, `parameters` (a list of
  `{"name", "type"}` dicts, saved form), `custom`, `asm`, `language`, and methods
  `parse(data_view, info)` and `write(data_view, event, info, temp)` (as in `events/events.ts`).
  `to_json()` gives the camelCase form the TypeScript saved (localStorage "events").
- **Buffers**: `ArrayBuffer` -> `bytearray` (`bytes` when read-only). `DataView` ->
  `partyplanner64.lib.utils.dataview.DataView` (same methods in snake_case, big-endian by default,
  views share the buffer like ArrayBuffer views do). `buffer.slice(a, b)` -> `bytearray(buf[a:b])`
  (a copy, as in JS). `Uint8Array` over a buffer -> the bytearray itself or a `memoryview`.
- **Numbers**: JS bit operations are 32-bit; mask with `& 0xFFFFFFFF` where TS used `>>> 0`, and
  convert to signed where TS relied on `| 0`. Integer division: `Math.floor(a / b)` -> `a // b`
  only for non-negative values; mind negatives.
- **Images**: the canvas is replaced by Pillow via `partyplanner64.lib.utils.canvas`: `ImageData`
  (width, height, RGBA bytearray), `get_image_data(src, w, h)`, `open_image(src)`,
  `image_data_to_data_url`, `rgba_to_data_url(buffer, w, h)`, `to_pil`/`from_pil`. Image sources
  are data URLs (as stored in boards), paths or bytes. Compositing that used `drawImage` uses
  Pillow directly.
- **Async**: `async`/`await`/Promises become plain synchronous code.
- **Errors**: `throw new Error(msg)` -> `raise ValueError(msg)` or `RuntimeError(msg)` (an
  `Exception` subclass in any case; the server shows the message).
- **three.js maths** used outside rendering (perspective in the adapters) is reimplemented in
  `partyplanner64/lib/utils/three_math.py` (Vector3, Matrix4, PerspectiveCamera).
- **Third-party JS** bundled in `packages/lib/lib`: spark-md5 -> `hashlib.md5`; cppjs (C
  preprocessor) -> ported to Python; SmallerC (C compiler, WebAssembly) -> run with `wasmtime`
  (optional dependency, needed only to compile C events); ThreeJS-export-OBJ -> Python OBJ export.
- Dependencies: the Python standard library and Pillow. `wasmtime` is optional (C events).
  No numpy.

## Testing against the original

A runnable copy of the TypeScript, with its node modules, is used to produce reference outputs:
`node ref/run.mjs ref/<script>.ts` bundles a script (which may import `../packages/lib/...`) with
esbuild and runs it. Port tests compare the Python with saved reference outputs
(`tests/fixtures/<area>/*.json`); the TypeScript scripts that produced them are kept next to them
(`tests/fixtures/<area>/gen_*.ts`) for the record. There is no Mario Party ROM in the repository
(and none may be added): tests use synthetic data.

## The web app

`python -m partyplanner64` starts `partyplanner64/server` (standard library `http.server`) on
http://127.0.0.1:8064 and opens the page. The server holds the state the browser used to hold:
the open ROM (in memory), the boards and the event library (saved in the data folder,
`~/.partyplanner64`, as the browser saved them in localStorage), settings, and the undo history.

- `partyplanner64/server/http.py`: the framework. Route modules in
  `partyplanner64/server/routes/*.py` register handlers with `@route("GET", "/api/...")`;
  they're imported automatically. Handlers return a dict (JSON), a `Response` (files) or None, and
  raise `ApiError` for messages meant for the user. `hub.publish(kind, data)` sends a server-sent
  event to every open page.
- `partyplanner64/static/index.html`: the top bar (brand, page tabs, ROM buttons, badge), one
  empty container per page, a shared `<dialog>`, the busy overlay and toasts.
- `partyplanner64/static/js/app.js`: the shell. Shows pages (lazy-loading
  `js/pages/<name>.js`, which exports `init(container, app)` and optionally `show()`/`hide()`),
  keeps `app.state` (GET `/api/state`), relays server events (`app.on(kind, fn)`), and runs the
  ROM buttons.
- `partyplanner64/static/js/api.js`: `api()`, `toast()`, `act()`, `busy()`, `dialog()`,
  `confirmDialog()`, `promptDialog()`, `pickFile()`, `readDataURL()`, `download()`, `saveBlob()`,
  `loadCss()`, `esc()`, `$`, `$$`.
- `partyplanner64/static/css/app.css`: the design system (tokens, top bar, sidebar + cards,
  buttons, inputs, segmented controls, toggles, pills, tables, list boxes, viewer overlay, console,
  dialogs, toasts). Pages add `css/<page>.css`.

### UI design language (from the SPOT Console)

Dark theme (`--bg #0b0d11`, panels `#13161c`/`#1a1e26`, borders `#262b35`, accent `#4c8dff`, go
`#2fb36b`, stop `#e5484d`, warn `#f5a524`). A page is either a **layout** (a 360 px sidebar of
`.card`s with `.card-head h2` titles in small caps, next to a main view with an overlaid
`.viewer-toolbar` and `.legend`, and a `.console` with `.tabs` underneath) or a
**scroll-page** (a `.page-head` and a `.grid` of cards). Controls: `.btn` (`-primary`, `-go`,
`-stop`, `-ghost`, `-sm`), `.segmented` button groups, `.toggle` switches, `.pill` statuses,
`.input`, `.field-label`, `.hint`, `.tip` (dotted underline, explanation in `title`), `.advanced`
`<details>`. Titles and labels use Title Case. Feedback is a `toast()`, long work runs under
`busy()`, questions are `dialog()`s. Every control has a `title` that explains it.

### API

All JSON. Board JSON in answers has every image data URL replaced by a URL of the server's image
cache, `/api/image/<sha1>` (so pages load images with `<img src>`); images sent *to* the server
are data URLs.

State and settings (`routes/state.py`, `routes/settings.py`):
- `GET /api/state` -> `{version, rom, settings, boards}`;
  `rom` is `null` or `{game: "NMVE", gameName: "MP3_USA", gameVersion: 3, supported, fileName,
  title: "Mario Party 3 (U)", shortName: "MP3"}`;
  `boards` is `{revision, current: {index, rom}, list: [summary], romList: [summary]}`, a summary
  being `{index, rom, name, game, type, spaceCount}`.
- `GET /api/settings`, `POST /api/settings {id: value, ...}` (ids as the original: `ui.theme`,
  `ui.advanced`, `ui.debug`, `ui.skipvalidation`, `ui.allowallroms`, `ui.showromboards`,
  `write.branding`, `write.decompressed`, `models.limitfps`, `models.limitAnimations`,
  `models.useGLB`).
- `GET /api/image/<sha1>` -> the image.
- Server events: `state`, `rom`, `settings` (the page reloads `/api/state`), `boards` (the board
  list or current board changed), `board` (`{revision}`: the current board's content changed),
  `events` (the event library changed), `progress` (`{text, fraction}`), `log`.

The ROM (`routes/rom.py`):
- `POST /api/rom?name=<file name>` with the file's bytes -> `{rom, boards}` (400 if not a
  recognized/supported ROM; `ui.allowallroms` allows unsupported ones).
- `POST /api/rom/close`; `POST /api/rom/save` -> the .z64 (download; `write.decompressed`).
- `POST /api/rom/overwrite {romBoardIndex}` writes the current board over a ROM board
  (validated first unless `ui.skipvalidation`) -> `{boards}`.

Boards (`routes/boards.py`):
- `GET /api/board` -> `{revision, index, rom, board, canUndo, canRedo}` (the current board).
- `GET /api/boards/<index>?rom=1` -> `{board}` (any board).
- `POST /api/boards/current {index, rom}`; `POST /api/boards/new {game, type, theme}`;
  `POST /api/boards/import` (a board .json file's bytes); `GET /api/boards/<index>/export?rom=1`
  (a .json download); `POST /api/boards/copy {index, rom}`; `POST /api/boards/delete {index}`.
- `POST /api/board/op {op, args}` applies one edit to the current board and returns
  `{revision, board, canUndo, canRedo}`. `op` is a Redux reducer name of
  `apps/partyplanner64/boardState.ts` without `Action` (e.g. `addSpace`, `setSpacePositions`,
  `addConnection`, `eraseConnections`, `setSpaceType`, `setBoardName`, `setBackground`,
  `addEventToSpaces`, `setSpaceEventEventParameter`, ...), `args` its payload as in the TypeScript.
  `POST /api/board/ops {ops: [{op, args}, ...]}` applies several as one undo step.
- `POST /api/board/undo`, `POST /api/board/redo` -> as `op`.
- `GET /api/board/validate?romBoard=<i>` -> `{results: [{level: 1|2, message}]}` (1 error,
  2 warning).
- `POST /api/board/code/test {kind: "additionalbg"|"audioselect", code, language}` ->
  `{ok, messages}`.

The event library (`routes/events.py`):
- `GET /api/events` -> `{events: [...]}` (built-in and custom: id, name, custom, supportedGames,
  activationType, executionType, parameters, language).
- `GET /api/events/<id>` (with code, for custom events); `POST /api/events {code, language}`
  creates or replaces a custom event; `POST /api/events/import` (a .s/.c file's bytes);
  `GET /api/events/<id>/export`; `POST /api/events/<id>/delete`;
  `POST /api/events/test {code, language}` -> per-game compile results.

ROM pages (`routes/<page>.py`, owned with the page): `/api/audio/...`, `/api/models/...`,
`/api/sprites/...`, `/api/strings/...`, `/api/patches/...`, `/api/debug/...`.
