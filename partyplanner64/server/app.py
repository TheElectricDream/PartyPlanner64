"""Start the PartyPlanner64 web app: python -m partyplanner64 [serve].

Serves the editor (partyplanner64/static) and its JSON API on
http://127.0.0.1:8064 and opens it in a browser.
"""

import argparse
import importlib
import ipaddress
import pkgutil
import sys
import threading
import webbrowser

from .http import Server
from . import routes

DEFAULT_PORT = 8064


def load_routes():
    """Import every module in partyplanner64/server/routes (each registers its routes)."""
    for info in pkgutil.iter_modules(routes.__path__):
        if not info.name.startswith("_"):
            importlib.import_module("%s.%s" % (routes.__name__, info.name))


def add_arguments(parser):
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to listen on (default 127.0.0.1: this computer only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="web port (default %d)" % DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    parser.add_argument("--rom", help="a Mario Party ROM to open at start-up")
    parser.add_argument("--data-dir",
                        help="where boards, events and settings are kept "
                             "(default: ~/.partyplanner64)")
    parser.add_argument("--debug", action="store_true", help="turn on debug features")


def serve(args):
    """Run the server until interrupted."""
    from .. import state
    state.configure(data_dir=args.data_dir, debug=args.debug)
    load_routes()
    if args.rom:
        state.open_rom_file(args.rom)

    loopback = True
    try:
        loopback = ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        loopback = args.host == "localhost"
    if not loopback:
        print("Warning: listening on %s; anyone who can reach this computer can use the editor."
              % args.host, file=sys.stderr)

    server = Server((args.host, args.port), loopback_only=loopback)
    url = "http://%s:%d/" % ("127.0.0.1" if loopback else args.host, server.server_address[1])
    print("PartyPlanner64 is running at %s (Ctrl+C to stop)" % url)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="partyplanner64-web", description=__doc__)
    add_arguments(parser)
    serve(parser.parse_args(argv))


if __name__ == "__main__":
    main()
