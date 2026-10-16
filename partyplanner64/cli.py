"""The command line: start the web app, or work on ROMs without it.

    python -m partyplanner64                      # the web app (same as `serve`)
    python -m partyplanner64 serve --port 9000 --rom MarioParty3.z64

    # Write a board file over a ROM board (as the original apps/cli did):
    python -m partyplanner64 overwrite --rom-file MarioParty.z64 \\
        --target-board-index 0 --board-file board.json --output-file MyMarioParty.z64

    python -m partyplanner64 info MarioParty.z64             # the game and its boards
    python -m partyplanner64 export-boards MarioParty.z64 out/  # the ROM's boards as .json
    python -m partyplanner64 validate board.json [--rom MarioParty.z64 [--rom-board 0]]

overwrite: --target-board-index is 0-based (0 is DK's Jungle Adventure in Mario
Party 1). The input ROM is not changed; a new ROM is written to --output-file.
validate: without --rom, the board file is read and checked for a start space and
dead ends; with --rom, it gets the checks the editor ran before overwriting a
board of that ROM (all its boards, or the one given with --rom-board).
"""

import argparse
import re
import sys
from pathlib import Path

from . import __version__

START_BANNER = "PartyPlanner64 v%s" % __version__


def _setup_library():
    """What apps/cli/index.ts imported: the built-in events."""
    from . import state
    state._load_builtin_events()


def _load_rom(rom_file, skip_supported_check=False):
    """Load a ROM file into the romhandler; returns True, or prints why not."""
    from .lib.romhandler import romhandler
    rom_buffer = Path(rom_file).read_bytes()
    errors = []
    loaded = romhandler.set_rom_buffer(bytearray(rom_buffer), skip_supported_check,
                                       errors.append)
    for err in errors:
        print(err, file=sys.stderr)
    return bool(loaded)


def _read_board(board_file):
    from .editor import jsjson
    from .lib.boards import fix_potentially_old_board
    board = jsjson.parse(Path(board_file).read_bytes())
    if not isinstance(board, dict):
        raise ValueError("%s is not a board file." % board_file)
    return fix_potentially_old_board(board)


def overwrite(rom_file, target_board_index, board_file, output_file):
    """Port of apps/cli/commands/overwrite.ts. Returns an exit code."""
    _setup_library()
    if not _load_rom(rom_file, False):
        return 1

    board = _read_board(board_file)

    from .lib.adapter.adapters import get_rom_adapter
    from .lib.romhandler import romhandler
    adapter = get_rom_adapter({})
    if not adapter:
        print("Could not get ROM adapter", file=sys.stderr)
        return 1

    adapter.load_boards()

    try:
        adapter.overwrite_board(target_board_index, board)
    except Exception as e:  # noqa: BLE001 - reported as the TypeScript did
        print("Error overwriting board:\n", e, file=sys.stderr)
        return 1

    new_rom_buffer = romhandler.save_rom(False)
    Path(output_file).write_bytes(bytes(new_rom_buffer))
    return 0


def _cmd_overwrite(args):
    print(START_BANNER)
    if not args.rom_file or not args.board_file or not args.output_file \
            or args.target_board_index is None:
        print("Bad arguments", file=sys.stderr)
        return 2
    print("Overwriting board %d in %s with %s" % (args.target_board_index, args.rom_file,
                                                  args.board_file))
    code = overwrite(args.rom_file, args.target_board_index, args.board_file, args.output_file)
    if code == 0:
        print("Wrote %s" % args.output_file)
    return code


def _rom_boards():
    from .lib.adapter.adapters import get_rom_adapter
    adapter = get_rom_adapter({})
    if not adapter:
        raise RuntimeError("Could not get ROM adapter")
    return adapter.load_boards()


def _cmd_info(args):
    _setup_library()
    if not _load_rom(args.rom, args.allow_all):
        return 1
    from .lib.romhandler import romhandler
    from .lib.types import get_game_name
    from .state import GAME_TITLES
    game = romhandler.get_rom_game()
    print("%s: %s (%s, %s)" % (args.rom, GAME_TITLES.get(game, game), game, get_game_name(game)))
    boards = _rom_boards()
    print("%d boards:" % len(boards))
    for i, board in enumerate(boards):
        print("  %2d  %-28s %-6s %3d spaces" % (i, board.get("name"), board.get("type"),
                                                len(board.get("spaces") or ())))
    return 0


def _safe_file_name(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", str(name)).strip().strip(".")
    return name or "board"


def _cmd_export_boards(args):
    _setup_library()
    if not _load_rom(args.rom, args.allow_all):
        return 1
    from .editor import jsjson
    from .editor.boards import strip_private_props
    out_dir = Path(args.dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, board in enumerate(_rom_boards()):
        path = out_dir / ("%d - %s.json" % (i, _safe_file_name(board.get("name"))))
        path.write_text(jsjson.stringify(strip_private_props(board)), encoding="utf-8")
        print("Wrote %s" % path)
    return 0


def _cmd_validate(args):
    _setup_library()
    try:
        board = _read_board(args.board)
    except (ValueError, OSError) as e:
        print("Board could not be parsed: %s" % e, file=sys.stderr)
        return 1
    print("%s: %s (Mario Party %s, %s, %d spaces)" % (
        args.board, board.get("name"), board.get("game"), board.get("type"),
        len(board.get("spaces") or ())))
    if not args.rom:
        from .lib import boards as lib_boards
        problems = 0
        if board.get("type") != "DUEL" and lib_boards.get_start_space_index(board) < 0:
            print("  error: No start space could be found on the board.")
            problems += 1
        dead_ends = lib_boards.get_dead_ends(board)
        if dead_ends:
            print("  error: Some spaces are dead ends: %s"
                  % ", ".join(str(i) for i in dead_ends))
            problems += 1
        if not problems:
            print("  No problems found (give --rom for the full checks).")
        return 1 if problems else 0

    if not _load_rom(args.rom, args.allow_all):
        return 1
    from .lib.validation.validation import validate_current_board_for_overwrite
    rom_boards = _rom_boards()
    results = validate_current_board_for_overwrite(rom_boards, board, False) or []
    failed = False

    def show(title, result):
        print(title)
        if result.get("unavailable"):
            print("  (cannot be overwritten)")
        for e in result.get("errors") or []:
            print("  error: %s" % e)
        for w in result.get("warnings") or []:
            print("  warning: %s" % w)
        if not result.get("errors") and not result.get("warnings") \
                and not result.get("unavailable"):
            print("  ok")

    if results:
        show("General:", results[0])
        failed = bool(results[0].get("errors"))
        for i, result in enumerate(results[1:]):
            if args.rom_board is not None and i != args.rom_board:
                continue
            show("ROM board %d, %s:" % (i, result.get("name")), result)
            if args.rom_board is not None:
                failed = failed or bool(result.get("errors")) or bool(result.get("unavailable"))
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="partyplanner64", description="PartyPlanner64 v%s: Mario Party N64 board editor"
        % __version__, epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=START_BANNER)
    sub = parser.add_subparsers(dest="command", metavar="command")

    from .server import app
    serve = sub.add_parser("serve", help="start the web app (the default)")
    app.add_arguments(serve)

    ow = sub.add_parser("overwrite", help="overwrite a ROM board with a custom board file")
    ow.add_argument("--rom-file", help="a stock Mario Party ROM (often a .z64 file)")
    ow.add_argument("--target-board-index", type=int,
                    help="the index of the board to overwrite (0-based)")
    ow.add_argument("--board-file", help="a custom board JSON file")
    ow.add_argument("--output-file", help="the ROM file to create")

    info = sub.add_parser("info", help="show a ROM's game and boards")
    info.add_argument("rom", help="a Mario Party ROM")
    info.add_argument("--allow-all", action="store_true", help="try ROMs that aren't supported")

    exp = sub.add_parser("export-boards", help="write a ROM's boards as board files")
    exp.add_argument("rom", help="a Mario Party ROM")
    exp.add_argument("dir", help="the folder to write them to")
    exp.add_argument("--allow-all", action="store_true", help="try ROMs that aren't supported")

    val = sub.add_parser("validate", help="check a board file")
    val.add_argument("board", help="a board JSON file")
    val.add_argument("--rom", help="check it for writing into this ROM")
    val.add_argument("--rom-board", type=int, help="only this ROM board (0-based)")
    val.add_argument("--allow-all", action="store_true", help="try ROMs that aren't supported")

    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv.insert(0, "serve")         # python -m partyplanner64 --port 9000
    args = parser.parse_args(argv)
    if args.command in (None, "serve"):
        if args.command is None:
            args = serve.parse_args([])
        app.serve(args)
        return 0
    handler = {"overwrite": _cmd_overwrite, "info": _cmd_info,
               "export-boards": _cmd_export_boards, "validate": _cmd_validate}[args.command]
    code = handler(args)
    if code:
        sys.exit(code)
    return 0
