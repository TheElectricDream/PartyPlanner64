"""The image cache: board images as URLs instead of data URLs.

Boards keep their images as data URLs (as the TypeScript did). Boards the
API sends have each image data URL replaced by /api/image/<sha1>, which the
cache serves; such URLs sent back are turned into the data URLs again.
"""

import base64
import hashlib
import re
import threading
from collections import OrderedDict
from urllib.parse import unquote_to_bytes

URL_PREFIX = "/api/image/"
_URL_RE = re.compile(r"^/api/image/([0-9a-f]{40})$")
_DATA_URL_RE = re.compile(r"^data:([^,;]*)((?:;[^,;]*)*?)(;base64)?,(.*)$", re.S)

_lock = threading.Lock()
_sha_by_data_url = {}       # data URL -> sha1 hex
_data_url_by_sha = {}       # sha1 hex -> data URL
_decoded = OrderedDict()    # sha1 -> (mime, bytes), a small LRU
_DECODED_MAX = 64


def is_image_data_url(value):
    """Whether value is an image data URL (data:image/...)."""
    return isinstance(value, str) and value.startswith("data:image/")


def register(data_url):
    """Add a data URL to the cache; return its /api/image/<sha1> URL."""
    with _lock:
        sha = _sha_by_data_url.get(data_url)
        if sha is None:
            sha = hashlib.sha1(data_url.encode("utf-8")).hexdigest()
            _sha_by_data_url[data_url] = sha
            _data_url_by_sha[sha] = data_url
    return URL_PREFIX + sha


def url_for(value):
    """The cache URL for an image data URL; other values are returned as they are."""
    if is_image_data_url(value):
        return register(value)
    return value


def externalize(obj):
    """A copy of obj (dicts, lists, values) with image data URLs replaced by cache URLs."""
    if isinstance(obj, dict):
        return {k: externalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [externalize(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("data:image/"):
        return register(obj)
    return obj


def resolve(value):
    """The data URL for a cache URL (/api/image/<sha1>); other values as they are."""
    if isinstance(value, str) and value.startswith(URL_PREFIX):
        m = _URL_RE.match(value)
        if m:
            with _lock:
                found = _data_url_by_sha.get(m.group(1))
            if found is not None:
                return found
    return value


def internalize(obj):
    """A copy of obj with cache URLs replaced by their data URLs."""
    if isinstance(obj, dict):
        return {k: internalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [internalize(v) for v in obj]
    if isinstance(obj, str) and obj.startswith(URL_PREFIX):
        return resolve(obj)
    return obj


def decode_data_url(data_url):
    """Return (mime type, bytes) of a data URL; raises ValueError if it isn't one."""
    m = _DATA_URL_RE.match(data_url)
    if not m:
        raise ValueError("Not a data URL")
    mime = m.group(1) or "text/plain"
    payload = m.group(4)
    if m.group(3):
        data = base64.b64decode(re.sub(r"\s+", "", unquote_to_bytes(payload).decode("latin-1"))
                                + "===")
    else:
        data = unquote_to_bytes(payload)
    return mime, data


def get(sha):
    """Return (mime, bytes) for an image in the cache, or None."""
    with _lock:
        hit = _decoded.get(sha)
        if hit is not None:
            _decoded.move_to_end(sha)
            return hit
        data_url = _data_url_by_sha.get(sha)
    if data_url is None:
        return None
    try:
        result = decode_data_url(data_url)
    except (ValueError, base64.binascii.Error):
        return None
    with _lock:
        _decoded[sha] = result
        while len(_decoded) > _DECODED_MAX:
            _decoded.popitem(last=False)
    return result


def clear():
    """Forget every image (tests)."""
    with _lock:
        _sha_by_data_url.clear()
        _data_url_by_sha.clear()
        _decoded.clear()
