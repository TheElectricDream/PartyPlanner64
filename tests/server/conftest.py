"""A live server on a free port, with its state in a temporary data folder."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from partyplanner64 import state
from partyplanner64.editor import images
from partyplanner64.server import app
from partyplanner64.server.http import Server


class Client:
    """Calls the API of a running server."""

    def __init__(self, port):
        self.base = "http://127.0.0.1:%d" % port

    def call(self, method, path, body=None, headers=None):
        """Return (status, headers, body bytes)."""
        data = None
        hdrs = dict(headers or {})
        if body is not None:
            if isinstance(body, (bytes, bytearray)):
                data = bytes(body)
                hdrs.setdefault("Content-Type", "application/octet-stream")
            else:
                data = json.dumps(body).encode("utf-8")
                hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return res.status, res.headers, res.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def get(self, path, expect=200):
        status, _, body = self.call("GET", path)
        assert status == expect, (path, status, body[:500])
        return json.loads(body)

    def post(self, path, body=None, expect=200):
        status, _, data = self.call("POST", path, {} if body is None else body)
        assert status == expect, (path, status, data[:500])
        return json.loads(data) if data else None

    def op(self, op, args=None, expect=200):
        return self.post("/api/board/op", {"op": op, "args": args}, expect)


def start_server(data_dir, debug=False):
    state.configure(data_dir=str(data_dir), debug=debug)
    app.load_routes()
    server = Server(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                              daemon=True)
    thread.start()
    return server


@pytest.fixture(autouse=True)
def _restore_globals():
    """state.configure replaces the global event library; put it back after."""
    from partyplanner64.lib import debug
    from partyplanner64.lib.events import event_library
    from partyplanner64.lib.romhandler import romhandler
    library = event_library.get_event_library_implementation()
    was_debug = debug.is_debug()
    yield
    event_library._event_library = library
    debug.set_debug(was_debug)
    romhandler.clear()


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def client(data_dir):
    images.clear()
    server = start_server(data_dir)
    yield Client(server.server_address[1])
    server.shutdown()
    server.server_close()
    state.shutdown()
