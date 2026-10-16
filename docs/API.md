# The PartyPlanner64 server API

The core API of the web app (`partyplanner64/server/routes/{state,settings,image,rom,boards,events}.py`,
backed by `partyplanner64/state.py` and `partyplanner64/editor/`). The ROM pages' own APIs
(`/api/audio/...`, `/api/models/...`, ...) are documented by their route modules.

Conventions:

- Requests and answers are JSON unless noted. A POST body may be empty (`{}`).
- Errors: status 400 (or 404, 409, 500) with `{"error": "message for the user"}`.
  409 means "no ROM is open" for endpoints that need one.
- **Images**: in every board sent by the server, each image data URL (`data:image/...`) is
  replaced by a URL of the image cache, `/api/image/<sha1>`. Images sent *to* the server are data
  URLs; a `/api/image/<sha1>` URL sent back is also accepted (it is turned back into the image).
  Other data URLs (custom music, `audioData[i].data`) are left as they are.
- Board JSON keeps the original camelCase keys (`bg.src`, `otherbg.boardselect`, `links`,
  `events`, `boardevents`, `audioType`, ...); `links` keys are strings (`{"0": 1, "1": [2, 3]}`).
- `revision` is a counter that grows each time any board (or the board list) changes.
- Path parameters are URL-encoded (`/api/events/My%20Event`).

## Server events

`GET /api/events` with `Accept: text/event-stream` (what `EventSource` sends) is the event
stream; without that header it is the event list (below).

| event | data | when |
|---|---|---|
| `state` | null | everything may have changed: reload `/api/state` |
| `rom` | `{rom}` (`null` when closed) | a ROM was opened or closed, or a board was written to it |
| `settings` | `{settings}` | a setting changed |
| `boards` | `{revision, current: {index, rom}}` | the board list or the current board changed |
| `board` | `{revision, canUndo, canRedo}` | the current board's content changed (edit, undo, redo) |
| `events` | null | the event library changed |
| `progress` | `{text, fraction}` | long work |
| `log` | `{text}` | messages |

## State and settings

### `GET /api/state`
```json
{"version": "0.1.0",
 "rom": null,
 "settings": {"ui.theme": "classic", "ui.advanced": false, ...},
 "boards": {"revision": 12, "current": {"index": 0, "rom": false},
            "list": [summary, ...], "romList": [summary, ...]}}
```
`rom` (when a ROM is open):
`{game: "NMVE", gameName: "MP3_USA", gameVersion: 3, supported: true, fileName: "mp3.z64",
title: "Mario Party 3 (U)", shortName: "MP3"}`.

A board summary: `{index, rom, name, game, type, spaceCount, description, bg}` (`bg`: the
background's image URL). `romList` is always sent; the UI shows it when `ui.showromboards`
is on (as the original did).

### `GET /api/settings` -> `{id: value, ...}`
### `POST /api/settings {id: value, ...}` -> `{id: value, ...}` (all settings)
Unknown ids or values of the wrong type -> 400. Saved in `settings.json`. Turning `ui.debug`
on or off turns the library's debug behaviours on or off.

| id | type | default | name (UI) | advanced |
|---|---|---|---|---|
| `ui.theme` | `"classic"`, `"dark-gray"` | `"classic"` | Theme | |
| `ui.advanced` | bool | false | Advanced features | |
| `ui.debug` | bool | false (`--debug`: true) | Debug features | yes |
| `ui.skipvalidation` | bool | false | Skip Overwrite Validation | yes |
| `ui.showromboards` | bool | false | Show ROM Boards | yes |
| `ui.allowallroms` | bool | false | Allow All ROMs | yes |
| `write.branding` | bool | true | Include branding | |
| `write.decompressed` | bool | false | Leave ROM decompressed | yes |
| `models.limitfps` | bool | true | Limit FPS | |
| `models.limitAnimations` | bool | true | Limit animations | |
| `models.useGLB` | bool | false | Use GLB container for glTF | |

### `GET /api/settings/schema`
`{sections: [{name: "Theme", settings: [{id, type: "theme"|"checkbox", name, desc, default,
advanced, choices?}]}, ...]}`: the original settings page's layout and descriptions.

### `POST /api/settings/reset` -> `{id: value, ...}`: back to the defaults.

### `GET /api/image/<sha1>`
The image bytes (with its content type), cacheable for good (the URL names the content).
404 if unknown.

## The ROM

### `POST /api/rom?name=<file name>` (body: the ROM file's bytes)
Opens the ROM (closing one already open) and reads its boards.
-> `{rom, boards}` (`boards` as in `/api/state`). 400 `{"error": "File is not recognized as any
valid ROM."}` or `"This ROM is not supported right now."` (`ui.allowallroms` skips the second
check). Publishes `rom` and `boards`.

### `POST /api/rom/close` -> `{boards}`
Closes the ROM: its boards go, the current board becomes board 0. Publishes `rom`, `boards`.

### `POST /api/rom/save`
-> the ROM file (`application/octet-stream`, download name `MyMarioParty<1|2|3>.z64`),
written decompressed if `write.decompressed`. 409 if no ROM.

### `POST /api/rom/overwrite {romBoardIndex}`
Writes the current board over ROM board `romBoardIndex` (with `write.branding`). It is
validated first (as `GET /api/board/validate`); errors, or a board that can't be overwritten,
-> 400 with the messages, unless `ui.skipvalidation`. Afterwards the ROM boards are read again
and your board stays current (or board 0 if a ROM board was current).
-> `{boards}`. Publishes `rom`, `boards`.

## Boards

### `GET /api/board`
`{revision, index, rom, board, canUndo, canRedo}`: the current board.

### `GET /api/boards/<index>?rom=1` -> `{board}`
Any board (`rom=1`: a ROM board). 404 if there is none.

### `POST /api/boards/current {index, rom}` -> `{boards}`
Makes a board current (clears the undo history and the selection). Publishes `boards`.

### `POST /api/boards/new {game: 1|2|3, type: "NORMAL"|"DUEL", theme: "default"}` -> `{boards, index}`
Adds a board with the game's defaults and makes it current. Duel boards need `ui.debug`
("Duel board support is partially finished, coming soon!"), as in the original.

### `POST /api/boards/import` (body: a board .json file's bytes) -> `{boards, index}`
Adds the board (old formats are upgraded) and makes it current.
400 "Board could not be parsed." if it isn't a board.

### `GET /api/boards/<index>/export?rom=1`
The board file (`application/json`, download name `<board name>.json`), with private (`_...`)
properties removed, as the original wrote it (compact JSON, data URLs).

### `POST /api/boards/copy {index, rom, makeCurrent?}` -> `{boards, index}`
Adds "Copy of <name>" after the board (ROM boards: at the end of your boards); `index` is the
copy's. The current board stays current unless `makeCurrent`.

### `POST /api/boards/delete {index}` -> `{boards}`
Deletes one of your boards (ROM boards can't be deleted). There is always at least one board:
deleting the last one leaves a new default board.

### `POST /api/board/op {op, args}` -> `{revision, board, canUndo, canRedo}`
Applies one reducer of the original `boardState.ts` to the current board. `op` is the reducer
name without `Action` (`setSpacePositionsAction` -> `setSpacePositions`; the `Action` suffix is
also accepted), `args` its payload as in the TypeScript. If the op fails, nothing changes
(400 with the message). Publishes `board`.

| op | args |
|---|---|
| `setBoardName` | `{name}` |
| `setBoardDescription` | `{description}` |
| `setBoardDifficulty` | `{difficulty}` |
| `setBoardCostumeTypeIndex` | `{costumeType}` |
| `setBackground` | `{bg}` (data URL) |
| `setBoardOtherBg` | `{name: "boardselect"\|..., value}` (data URL) |
| `addAnimationBackground` / `removeAnimationBackground` | `{bg}` / `{index}` |
| `addAdditionalBackground` / `removeAdditionalBackground` | `{bg}` / `{index}` |
| `setAdditionalBackgroundCode` / `setAudioSelectCode` | `{code, language}` (empty code removes it) |
| `setBoardAudio` | `{audioChanges: {audioType?, gameAudioIndex?, customAudioIndex?, midiName?, midiData?, soundbankIndex?, delete?}}` |
| `addSpace` | `{x, y, type, subtype?}` |
| `removeSpace` | `{index}` |
| `removeSpaces` | `{spaceIndices}` |
| `addConnection` | `{startSpaceIndex, endSpaceIndex}` |
| `eraseConnections` | `{x, y}` (erases the connections passing within 4 px of the point) |
| `setSpacePositions` | `{spaceIndices, coords: [{x?, y?, z?}]}` |
| `setSpaceType` | `{spaceIndices, type, subtype?}` |
| `setSpaceSubtype` | `{spaceIndices, subtype?}` (absent: removes it) |
| `setSpaceHostsStar` | `{spaceIndices, hostsStar}` |
| `setSpaceRotation` | `{spaceIndex, angleYAxisDeg}` (not on ROM boards) |
| `addEventToBoard` | `{event: {id, activationType, executionType, parameterValues?, custom?}}` |
| `removeEventFromBoard` | `{eventIndex}` |
| `includeEventInBoard` | `{event: {name, language, asm}}` or `{eventId}` (from the library) |
| `excludeEventFromBoard` | `{eventId}` |
| `setBoardEventActivationType` | `{eventIndex, activationType}` |
| `setBoardEventEventParameter` | `{eventIndex, name, value}` |
| `addEventToSpace` | `{event, toStart?, spaceIndex?}` |
| `addEventToSpaces` | `{event, spaceIndices}` |
| `removeEventFromSpace` | `{eventIndex, spaceIndex?}` |
| `removeEventsFromSpaces` | `{eventIndices, spaceIndices}` |
| `setSpaceEventActivationType` | `{eventIndex, activationType, spaceIndex?}` |
| `setSpaceEventsActivationType` | `{spaceIndices, eventIndices, activationType}` |
| `setSpaceEventEventParameter` | `{eventIndex, name, value, spaceIndex?}` |
| `setSpaceEventsEventParameter` | `{spaceIndices, eventIndices, name, value}` |

ROM boards: the original didn't edit them; clicking a space of a ROM board first made a copy and
switched to it (`copyCurrentBoard(true)`). Pages should do the same with
`POST /api/boards/copy {index, rom: true, makeCurrent: true}` before editing. (The ops themselves
work on whatever board is current; `setSpaceRotation` refuses ROM boards, as in the original.)

The original's single-space ops worked on the one selected space; here `spaceIndex` names it
(without it, the selection kept by the selection ops below is used).

Also accepted (UI state, not undoable, nothing in the board changes): `setSelectedSpace`
(args: an index), `setSelectedSpaces` (a list), `addSelectedSpace`, `clearSelectedSpaces`,
`setHighlightedSpaces {spaceIndices}`, `setSelectionBoxCoords {selectionCoords}`,
`setTemporaryUIConnections {connections}`, `setHoveredBoardEventIndex {eventIndex}`,
`changeCurrentEvent {id, type}`. `GET /api/board` answers include them as `ui`:
`{selectedSpaceIndices: [...], highlightedSpaceIndices, selectionBoxCoords, temporaryConnections,
hoveredBoardEventIndex, currentEventId, currentEventType}`.

Board-list reducers (`addBoard`, `deleteBoard`, `setCurrentBoard`, `copyCurrentBoard`,
`setBoards`, `clearBoardsFromROM`) and the library's (`addEventToLibrary`,
`removeEventFromLibrary`) are accepted too, but use the endpoints above.

Undo: like the original (redux-undo): each op is one step, except that consecutive
`setSpacePositions` ops (or consecutive `setSpaceRotation` ops) make one step (a drag).
The history is cleared when the current board changes, a board is added from a file or the ROM,
or the ROM is opened or closed.

### `POST /api/board/ops {ops: [{op, args}, ...]}` -> as `op`
Several ops as one undo step; all or nothing.

### `POST /api/board/undo`, `POST /api/board/redo` -> as `op`

### `GET /api/board/validate?romBoard=<i>`
`{results: [{level: 1|2, message}], general: {errors, warnings},
boards: [{index, name, unavailable, forcedDisabled, errors, warnings}], romLoaded}`
(`level` 1 error, 2 warning). `results` holds the game's rules and, with `romBoard`, that ROM
board's own. Without a ROM, everything is empty and `romLoaded` is false.

### `POST /api/board/code/test {kind: "additionalbg"|"audioselect", code, language}`
-> `{ok, messages}` (the compile/assembly failures for each game).

### `GET /api/board/code?kind=additionalbg|audioselect`
-> `{code, language}` of the current board (`code` null when it has none).

### `GET /api/board/code/default?kind=...&language=0|1` -> `{code}`: the starting template.

## The event library

An event (list form): `{id, name, custom, supportedGames: ["NMVE", ...], activationType,
executionType, parameters: [{name, type}], language}` (`language` 0 MIPS assembly, 1 C;
null for built-in events).

### `GET /api/events` (without `Accept: text/event-stream`)
`{events: [...], boardEvents: [...]}`: the library (built-in and custom), and the custom events
kept in the current board's file (each with `inLibrary` and `differs`: whether the library's copy
has other code).

### `GET /api/events/<id>` -> the event, plus `code` (custom events)
### `GET /api/board/events/<id>` -> a board event, with `code`

### `POST /api/events {code, language, board?}` -> `{event, warning}`
Creates or replaces a custom event from its code (the name, games and parameters are read from the
code's header comments). 400 if the code lacks them or the name is a built-in event's. It is then
test-assembled/compiled for each supported game; if that fails, it is saved anyway (as the
original did) and `warning` says why (null otherwise). With `board: true` it goes into the
current board's file instead of the library (an undoable change).

### `POST /api/events/import?name=<file name>` (body: a .s or .c file) -> `{event}`
Adds it to the library if it passes the test compile (400 otherwise).

### `GET /api/events/<id>/export` -> the code file (`<id>.s` or `<id>.c`)
### `POST /api/events/<id>/delete` -> `{}` (custom events only)
### `POST /api/events/<id>/copy-to-board` -> `{revision}`: includes the library's copy in the current board.
### `POST /api/board/events/<id>/copy-to-library` -> `{event}`
### `POST /api/board/events/<id>/delete`: removes it from the board's file, and its uses on the board.

### `POST /api/events/test {code, language}`
`{event: {...} | null, error, results: [{game: "NMVE", gameName: "MP3_USA", ok, error}]}`:
the event read from the code and a test compile for each game it supports. For a C event
(`language` 1), each passing result also has `asm`, the MIPS assembly the C compiles to.

## Song names

### `GET /api/songs/<game>` -> `{game, names: {index: name}}`
The in-game songs of Mario Party 1, 2 or 3 by name (from the adapters; no ROM needed), for
choosing a board's music.

## For route modules (Python)

`partyplanner64.state`: `lock` (an RLock; hold it while using the ROM), `require_rom()` (the
open `ROM`, or ApiError 409), `rom_info()`, `get_setting(id)`, `get_settings()`,
`current_board()` (the store's board: don't change it), `get_board(index, rom)`,
`boards_info()`. Board edits go through `partyplanner64.editor.store.store.dispatch(type,
payload)` or `partyplanner64.editor.ops.apply([(op, args)])`.

## Files in the data folder

`~/.partyplanner64` (or `--data-dir`): `boards.json` (your boards, as the original's localStorage
"boards": a JSON list of boards), `events.json` (custom events, as localStorage "events": a list
of `{id, name, custom, language, asm, activationType, executionType, supportedGames,
parameters}`), `settings.json` (`{id: value}`). They are written shortly after each change and when
the server stops.
