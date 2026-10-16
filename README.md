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

- **Editor**: lay out a board's spaces and paths, characters, events and decision trees; validate it against the game's rules; write it over one of the ROM's boards.
- **Details**: the board's name and description, difficulty, backgrounds and other images, music, and the code that picks backgrounds and music.
- **Events**: the event library, and custom events written in MIPS assembly or C.
- With a ROM open: **Audio** (play and export the songs and sounds), **Models** (view and export the 3D models), **Sprites**, **Strings**, **Patches** (GameShark codes) and, with debug features on, **Debug**.

Boards are saved as `.json` files, the same format as the earlier TypeScript editor's, so boards made with either open in both.

### Command Line

    partyplanner64 overwrite --rom-file "Mario Party (U).z64" --target-board-index 0 \
        --board-file board.json --output-file MyMarioParty.z64
    partyplanner64 info "Mario Party 3 (U).z64"          # the game and its boards
    partyplanner64 export-boards "Mario Party 2 (U).z64" boards/
    partyplanner64 validate board.json --rom "Mario Party (U).z64"

`overwrite` writes a board file over a board of a stock ROM (index 0 is the game's first board, e.g. DK's Jungle Adventure in Mario Party 1) into a new ROM file. See `partyplanner64 <command> --help`.

## Limitations

A ROM is not required to create and edit boards with PartyPlanner64, however to play them you will need to open a Mario Party ROM file. Only the NTSC USA files are supported.

- `Mario Party (U).z64` ROM file (MD5 `8BC2712139FBF0C56C8EA835802C52DC`).
- `Mario Party 2 (U).z64` ROM file (MD5 `04840612A35ECE222AFDB2DFBF926409`).
- `Mario Party 3 (U).z64` ROM file (MD5 `76A8BBC81BC2060EC99C9645867237CC`).

ROMs that have been edited can also be re-opened.

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
- `partyplanner64/static`: the page itself: HTML, CSS and JavaScript modules, no build step.
- `partyplanner64/cli.py`: the command line.
- `scripts/update_symbols.py`: regenerates the game symbol tables from the `symbols` submodule.

PartyPlanner64 was a TypeScript and React app until version 0.8.2. [docs/PORTING.md](docs/PORTING.md) explains how it was ported to Python; the tests compare the Python with the TypeScript's own outputs (`tests/fixtures`).

## Contributors

Pull requests and other contributions are greatly appreciated.

## [FAQ](https://github.com/PartyPlanner64/PartyPlanner64/wiki/FAQ)

## License

Code in this repository is released into the public domain, with the exception of included third party libraries with separate licenses (in `partyplanner64/lib/mips`, `partyplanner64/lib/cppjs.py` and `partyplanner64/static/vendor`).
