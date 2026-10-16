"""The command line: start the web app, or work on ROMs without it.

    python -m partyplanner64                 # the web app (same as `serve`)
    python -m partyplanner64 serve --port 9000
"""

import argparse

from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(prog="partyplanner64",
                                     description="PartyPlanner64 v%s: Mario Party N64 board editor"
                                     % __version__)
    sub = parser.add_subparsers(dest="command")

    from .server import app
    serve = sub.add_parser("serve", help="start the web app (the default)")
    app.add_arguments(serve)

    args = parser.parse_args(argv)
    if args.command in (None, "serve"):
        if args.command is None:
            args = serve.parse_args([])
        app.serve(args)
