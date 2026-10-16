"""The HTTP layer: routing, JSON, static files and server-sent events.

Route modules (partyplanner64/server/routes/*.py) register handlers with
the @route decorator; they are imported automatically at start-up.

    from ..http import route, ApiError, Response

    @route("GET", "/api/strings/<int:index>")
    def get_string(req, index):
        return {"index": index, "text": ...}        # sent as JSON

A handler gets a Request (req.query, req.json, req.body, req.headers) and
the path parameters, and returns:

- a dict or list: sent as JSON (200);
- a Response: bytes with a content type (downloads, images, WAVs);
- None: {"ok": true}.

Raising ApiError("message") sends {"error": "message"} with status 400
(or the status given); any other exception is a 500 with its message.

Path parameters are URL-decoded. GET /api/events is the server-sent event
stream when the request accepts text/event-stream (EventSource does), and an
ordinary route otherwise (the event library, routes/events.py).
"""

import json
import mimetypes
import queue
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

MAX_BODY = 512 * 1024 * 1024        # ROMs are up to 64 MB; leave room for boards with images
EVENT_KEEPALIVE = 15                # [s] a comment line when no event has come

CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".svg": "image/svg+xml", ".png": "image/png", ".gif": "image/gif",
                 ".jpg": "image/jpeg", ".ico": "image/x-icon", ".json": "application/json",
                 ".txt": "text/plain; charset=utf-8", ".woff2": "font/woff2", ".woff": "font/woff",
                 ".ttf": "font/ttf", ".wasm": "application/wasm", ".cur": "image/x-icon",
                 ".wav": "audio/wav", ".xml": "application/xml"}


class ApiError(Exception):
    """An error meant for the user, sent as {"error": message}."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Response:
    """A non-JSON answer: bytes and a content type.

    Args:
        body: The bytes (or str, sent as UTF-8).
        content_type: The MIME type.
        filename: If given, the browser is told to download it under this name.
        headers: Extra (name, value) pairs.
        status: The HTTP status.
    """

    def __init__(self, body, content_type="application/octet-stream", filename=None,
                 headers=None, status=200):
        self.body = body.encode("utf-8") if isinstance(body, str) else bytes(body)
        self.content_type = content_type
        self.headers = list(headers or [])
        self.status = status
        if filename:
            self.headers.append(("Content-Disposition",
                                 "attachment; filename*=UTF-8''%s" % quote(filename)))


class Request:
    """What a handler gets: the method, path, query, headers and body."""

    def __init__(self, method, path, query, headers, body):
        self.method = method
        self.path = path
        self.query = query          # {name: first value}
        self.headers = headers
        self.body = body            # raw bytes
        self._json = None

    @property
    def json(self):
        """The body parsed as JSON ({} when empty)."""
        if self._json is None:
            if not self.body:
                self._json = {}
            else:
                try:
                    self._json = json.loads(self.body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    raise ApiError("The request is not valid JSON (%s)." % e)
        return self._json

    def arg(self, name, default=None):
        """Return a value from the JSON body, else the query string."""
        body = self.json if self.body else {}
        if isinstance(body, dict) and name in body:
            return body[name]
        return self.query.get(name, default)


# Routing

_ROUTES = []      # (method, regex, converters, handler)
_PARAM = re.compile(r"<(?:(int|str|path):)?([a-zA-Z_][a-zA-Z0-9_]*)>")


def route(method, pattern):
    """Register a handler for METHOD and a path pattern.

    Patterns may hold <name> (one path segment), <int:name> (an integer,
    may be negative) and <path:name> (the rest of the path).
    """
    converters = {}

    def to_regex(m):
        kind, name = m.group(1) or "str", m.group(2)
        converters[name] = int if kind == "int" else str
        return {"int": r"(?P<%s>-?\d+)", "str": r"(?P<%s>[^/]+)", "path": r"(?P<%s>.+)"}[kind] % name

    regex = re.compile("^" + _PARAM.sub(to_regex, pattern) + "$")

    def register(fn):
        _ROUTES.append((method.upper(), regex, converters, fn))
        return fn
    return register


def find_route(method, path):
    """Return (handler, params) for a request, or (None, allowed_methods)."""
    allowed = []
    for m, regex, converters, fn in _ROUTES:
        match = regex.match(path)
        if not match:
            continue
        if m != method:
            allowed.append(m)
            continue
        params = {k: converters[k](unquote(v)) for k, v in match.groupdict().items()}
        return fn, params
    return None, allowed


# Server-sent events


class EventHub:
    """Pushes events to every open page (GET /api/events).

    publish("rom", {...}) sends `event: rom` with the JSON data.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._clients = set()

    def subscribe(self):
        q = queue.Queue(maxsize=1000)
        with self._lock:
            self._clients.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._clients.discard(q)

    def publish(self, kind, data=None):
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait((kind, data))
            except queue.Full:
                pass


hub = EventHub()


# Requests


class Handler(BaseHTTPRequestHandler):
    """One HTTP request."""

    server_version = "PartyPlanner64/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        """Keep the terminal quiet."""
        pass

    def _host_ok(self):
        """Turn away pages whose domain points at a loopback server (DNS rebinding)."""
        if not getattr(self.server, "loopback_only", True):
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method):
        url = urlparse(self.path)
        try:
            if not self._host_ok():
                return self._send(403, b"Forbidden", "text/plain")
            if method == "GET":
                if url.path in ("/", "/index.html"):
                    return self._file(STATIC_DIR / "index.html")
                if url.path.startswith("/static/"):
                    target = (STATIC_DIR / url.path[len("/static/"):]).resolve()
                    if STATIC_DIR not in target.parents:
                        return self._send(404, b"Not found", "text/plain")
                    return self._file(target)
                if url.path == "/api/events" and "text/event-stream" in (
                        self.headers.get("Accept") or ""):
                    return self._events()
            if not url.path.startswith("/api/"):
                return self._send(404, b"Not found", "text/plain")

            fn, params = find_route(method, url.path)
            if fn is None:
                if params:
                    return self._json({"error": "Method not allowed."}, 405)
                return self._json({"error": "No such API: %s" % url.path}, 404)

            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json({"error": "The upload is too large."}, 413)
            body = self.rfile.read(length) if length else b""
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            req = Request(method, url.path, query, self.headers, body)
            try:
                result = fn(req, **params)
            except ApiError as e:
                return self._json({"error": str(e)}, e.status)
            except Exception as e:  # noqa: BLE001 - reported to the page
                traceback.print_exc()
                return self._json({"error": "%s: %s" % (type(e).__name__, e),
                                   "traceback": traceback.format_exc()}, 500)
            if isinstance(result, Response):
                return self._send(result.status, result.body, result.content_type, result.headers)
            return self._json({"ok": True} if result is None else result)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # Answers

    def _send(self, status, body, content_type, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if not any(name.lower() == "cache-control" for name, _ in headers or []):
            self.send_header("Cache-Control", "no-store")
        for name, value in headers or []:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, status=200):
        self._send(status, json.dumps(data, separators=(",", ":")).encode("utf-8"),
                   "application/json")

    def _file(self, path):
        path = Path(path)
        if not path.is_file():
            return self._send(404, b"Not found", "text/plain")
        ctype = CONTENT_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] \
            or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype)

    def _events(self):
        """Stream events to a page until it goes away."""
        q = hub.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while True:
                try:
                    kind, data = q.get(timeout=EVENT_KEEPALIVE)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                payload = json.dumps(data, separators=(",", ":"))
                self.wfile.write(("event: %s\ndata: %s\n\n" % (kind, payload)).encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            hub.unsubscribe(q)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, loopback_only=True):
        super().__init__(address, Handler)
        self.loopback_only = loopback_only
