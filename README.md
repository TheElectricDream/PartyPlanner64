# ![PartyPlanner64](http://i.imgur.com/ygEasfG.png)

> Mario Party N64 board editor

PartyPlanner64 allows players to create and import customized boards into a Mario Party N64 ROM for playback in emulators or on real hardware.

PartyPlanner64 is written in Python: a local web app (a Python server and a page in your browser) and a command line. It needs Python 3.10 or newer and [Pillow](https://pypi.org/project/Pillow/); nothing else to build.

It is highly recommended to read [**this**](https://github.com/PartyPlanner64/PartyPlanner64/wiki/Creating-a-Board) before creating a board. This documentation highlights some common mistakes made while using PartyPlanner64.

The [wiki](https://github.com/PartyPlanner64/PartyPlanner64/wiki) has additional information about the editor, as well as technical documentation on the game itself.

## Getting Started

    pip install .            # or `pip install ".[c]"` to also write custom events in C
    partyplanner64           # or: python -m partyplanner64

This starts the editor on http://127.0.0.1:8064 and opens it in your browser. Your boards, custom events and settings are kept in `~/.partyplanner64` (change it with `--data-dir`). Other options:

    partyplanner64 serve --port 9000          # another port
    partyplanner64 serve --rom "Mario Party 3 (U).z64"   # open a ROM at start-up
    partyplanner64 serve --no-browser

The editor only listens on this computer unless you pass `--host`.

### The Editor

- **Editor**: lay out a board's spaces and paths, characters, events and decision trees; validate it against the game's rules; write it over one of the ROM's boards. Drag with the middle mouse button to scroll the board; Ctrl+scroll zooms.
- **Test Play** (in the Editor's Boards card, with a ROM open): starts your emulator on the current board, in the middle of a game. See [Testing a board](#testing-a-board).
- **Details**: the board's name and description, difficulty, backgrounds and other images, music (with [custom soundbanks](#custom-soundbanks)), and the code that picks backgrounds and music.
- **Events**: the event library, and custom events written in MIPS assembly or C. **Test Play** on an event starts your emulator on a small board where the player lands on (or passes) it. See [Testing an event](#testing-an-event).
- **Reference**: what the code means. See [Code help](#code-help).
- With a ROM open: **Audio** (play and export the songs and sounds), **Models** (view and export the 3D models), **Sprites**, **Strings**, **Patches** (GameShark codes) and, with debug features on, **Debug**.

Boards are saved as `.json` files, the same format as the earlier TypeScript editor's, so boards made with either open in both.

### Testing a board

With a ROM open, **Test Play** builds a test ROM and starts your Nintendo 64 emulator with it. The test ROM boots straight into the board, on the first player's turn: no logos, title screen, file select, set-up screens or opening scenes, so a change to a board or to an event's code can be tried seconds after it is made. The board is checked as for *Overwrite to ROM* and written into a copy of the ROM; the ROM you have open is not changed, and the game saves nothing from a test.

**Options…** sets what a test starts with: each player's character, who plays it (a controller, or the computer and its skill; players can share a controller, so with *Controller 1* for all four you take every turn yourself), the items held, everyone's coins and stars, the number of turns and the turn the game is on. It also holds the emulator's command, e.g. `/home/me/Applications/RMG-K.AppImage %f` (`%f` is the ROM file). Left empty, an installed emulator is used: on Linux, the application that opens N64 ROMs. *Download Test ROM* saves the test ROM instead, for another emulator or a flash cart.

Test play is available for Mario Party 3 (U) Battle Royal boards so far. The test ROM tells emulators its save type (16K EEPROM) with the "Advanced Homebrew ROM Header", which mupen64plus-based emulators (RMG, RMG-K, simple64), ares and flash carts read; like every Mario Party ROM it needs the Expansion Pak (8MB RAM). How the game is made to start on the board is described in `partyplanner64/lib/playtest/mp3.py`.

### Testing an event

On the Events page, **Test Play** (on each custom event, and in the event editor's Test card) tests one event without a board of your own. It builds a small board for it: a start space, an invisible space, then a loop of ten spaces. The dice show 1 to 10, so the first roll always ends on the loop:

- **Land On**: every loop space (a Happening, Blue or Red space, as chosen) runs the event, so whatever you roll, you land on one.
- **Walk Over**: the invisible space right after the start runs it, so every first move passes it.

The dialog also takes values for the event's parameters; a Space parameter names one of the test board's spaces. From the editor, the code is tested as it is, saved or not. Each event's choices are kept for its next test. The players, coins and emulator are the Test Play options (*Players & Emulator…*), and the board is tested as above, in a copy of the ROM. The event must list `MP3_USA` in its GAMES.

### Custom soundbanks

A custom song (a MIDI file on the Details page) plays with a soundbank: the instruments its MIDI program numbers pick, from 0. Besides the game's own soundbanks, a board can have soundbanks of its own (the **Soundbanks** card, shown with custom music):

- **New Game Boy Soundbank**: the Game Boy's sound chip: pulse waves (12.5, 25 and 50% duty), the wave channel (any 32-step pattern, written as 32 hex digits) and noise. They play in tune on every key.
- **+ From WAV File…** adds a recording as an instrument; loop points in the file make it sustain. Choose the key it sounds as.
- Each instrument has a volume and an envelope (attack, decay, sustain, release). ▶ plays a note; **Preview Song** plays a custom song with the soundbank as the game will (looped samples, channel volume and pitch bends).
- **Export** and **Import…** move soundbanks between boards (`.soundbank.json`).

Then choose the soundbank with the song's **Soundbank** button. Custom soundbanks work with Mario Party 3 (U) so far. The game keeps all soundbanks in a small audio memory at boot, so a board's soundbanks may use about 10,000 bytes of it (the card shows each one's size; the Game Boy soundbank is about 6,500); a soundbank that is too big is refused, as it would stop the game at boot. The samples themselves are read from the ROM as they play, so their length doesn't matter. How soundbanks are built and added to the ROM is described in `partyplanner64/lib/audio/custom_bank.py`.

**Game Boy music**: `scripts/gbs_to_midi.py` turns a Game Boy song (a `.gbs` file, through [gbsplay](https://github.com/mmitch/gbsplay)'s register dump) into a MIDI file and the soundbank it needs, with the song's own duty cycles, wave patterns, volume envelopes, pitch slides and panning. It finds the song's loop, so the game repeats it seamlessly. The script's help has the steps.

### Code help

The code editors (custom events, and a board's background and music code on the Details page) explain the code as you write it:

- **Hover**: rest the mouse on a word (an instruction, a register, a directive, a C keyword, a header line, one of the game's functions, your own parameters and labels) to see what it is, with a short example.
- **Completion** (as you type, or Ctrl+Space): instructions, registers, C keywords, the game's functions and data for the code's games, your parameters and labels, and in board code its own names (`DEFAULT_BG`, `MUSIC_TRACK_INDEX_1`, ...). Each comes with its explanation.
- **F1** opens the word by the cursor on the **Reference** page.

The Reference page has all of it, searchable: guides to how events work (the delay slot, the stack, calling the game's functions, messages, parameters...), MIPS, C, the event header, board code, and the games' functions and data (the symbol tables of Mario Party 1, 2 and 3; the main functions are explained). Every example in it is assembled or compiled by the tests, so they stay correct.

### Command Line

    partyplanner64 overwrite --rom-file "Mario Party (U).z64" --target-board-index 0 \
        --board-file board.json --output-file MyMarioParty.z64
    partyplanner64 playtest --rom-file "Mario Party 3 (U).z64" --board-file board.json
    partyplanner64 info "Mario Party 3 (U).z64"          # the game and its boards
    partyplanner64 export-boards "Mario Party 2 (U).z64" boards/
    partyplanner64 validate board.json --rom "Mario Party (U).z64"

`overwrite` writes a board file over a board of a stock ROM (index 0 is the game's first board, e.g. DK's Jungle Adventure in Mario Party 1) into a new ROM file. `playtest` builds the test ROM of a board file (or of one of the ROM's own boards) and starts the emulator with it, as Test Play does. See `partyplanner64 <command> --help`.

## Limitations

A ROM is not required to create and edit boards with PartyPlanner64, however to play them you will need to open a Mario Party ROM file. Only the NTSC USA files are supported.

- `Mario Party (U).z64` ROM file (MD5 `8BC2712139FBF0C56C8EA835802C52DC`).
- `Mario Party 2 (U).z64` ROM file (MD5 `04840612A35ECE222AFDB2DFBF926409`).
- `Mario Party 3 (U).z64` ROM file (MD5 `76A8BBC81BC2060EC99C9645867237CC`).

ROMs that have been edited can also be re-opened.

The games' own board backgrounds (Hudson's HVQ format, which the earlier TypeScript editor could not decode) are shown in the editor. Backgrounds you set are still written in the formats the games accept from PartyPlanner64, not HVQ.

ROM files must be ran with Expansion Pak on hardware, emulators must be configured to use 8MB RAM or the game will crash.

### Emulators

These emulators are reported to work:

- Project64 2.3
- Mupen64plus
- Nemu64

This emulator has issues, even with the right setup (8MB RAM):

- Project64 1.6

See the [emulator setup](https://github.com/PartyPlanner64/PartyPlanner64/wiki/Emulator-Setup) page for details on configuring each emulator.

## Development

    pip install -e ".[dev]"
    python -m pytest

- `partyplanner64/lib`: reading and writing Mario Party ROMs: the file systems, compression, images, audio, models, events, the per-game adapters that load and write boards, and validation. It includes Python ports of the [mips-inst](https://github.com/wnayes/mips-inst) and [mips-assembler](https://github.com/wnayes/mips-assembler) libraries and of cpp.js; custom C events are compiled with SmallerC, run as WebAssembly through `wasmtime`.
- `partyplanner64/editor`: the editor's board store, with undo and redo.
- `partyplanner64/server`: the web app's HTTP server and its JSON API ([docs/API.md](docs/API.md)).
- `partyplanner64/lib/reference`: the code reference (hover help, completions, the Reference page); its examples are checked by `tests/lib/test_reference.py`.
- `partyplanner64/lib/playtest`: test ROMs that boot straight into a board; `partyplanner64/emulator.py` finds and starts the emulator.
- `partyplanner64/static`: the page itself: HTML, CSS and JavaScript modules, no build step.
- `partyplanner64/cli.py`: the command line.
- `scripts/update_symbols.py`: regenerates the game symbol tables (and their whole comments, `lib/symbols/notes`) from the `symbols` submodule.

PartyPlanner64 was a TypeScript and React app until version 0.8.2. [docs/PORTING.md](docs/PORTING.md) explains how it was ported to Python; the tests compare the Python with the TypeScript's own outputs (`tests/fixtures`).

## Contributors

Pull requests and other contributions are greatly appreciated.

## [FAQ](https://github.com/PartyPlanner64/PartyPlanner64/wiki/FAQ)

## License

Code in this repository is released into the public domain, with the exception of included third party libraries with separate licenses (in `partyplanner64/lib/mips`, `partyplanner64/lib/cppjs.py` and `partyplanner64/static/vendor`) and the Source Sans Pro font (`partyplanner64/static/fonts`, SIL Open Font License, as the original editor shipped it).
