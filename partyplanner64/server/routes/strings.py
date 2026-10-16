"""Strings: the ROM's text (apps/partyplanner64/views/strings.tsx).

Mario Party 1 and 2 keep one table of strings (Strings); Mario Party 3 keeps,
for each language, directories of strings (Strings3). Text comes as the
adapters' character maps convert it: colour tags such as <RED>, "\\n", and
private-use characters for the button and coin images (\\u3000 is the A button,
see texteditor.tsx); the page draws them.

    GET  /api/strings                       -> {game, version, multi, locales, locale,
                                                 directories: [{index, count}]}
    GET  /api/strings/list?locale=en&dir=0  -> {locale, dir, strings: [{index, text}]}
    GET  /api/strings/<int:index>?locale=en&dir=0&raw=1 -> {index, text, raw (hex)}
    POST /api/strings/write {locale, dir, index, text} -> {index, text}
    GET  /api/strings/search?q=Star&locale=en -> {results: [{dir, index, text}]}
"""

from ..http import ApiError, route

MAX_RESULTS = 500


def _romhandler():
    from ...lib.romhandler import romhandler
    return romhandler


def _rom():
    rom = _romhandler().get_rom()
    if rom is None:
        raise ApiError("Open a ROM first.", 409)
    return rom


def _is_multi():
    """True for Mario Party 3 (Strings3: languages and directories)."""
    return _romhandler().get_game_version() == 3


def _locale(req):
    return req.arg("locale") or "en"


def _int(req, name, default=0):
    value = req.arg(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError("%s must be a number." % name)


def _hex_bytes(buf):
    return " ".join("%02X" % b for b in bytes(buf))


class _Table:
    """One list of strings: MP1/2's table, or one MP3 directory of a language."""

    def __init__(self, locale="en", dir=0):
        rom = _rom()
        self.multi = _is_multi()
        self.locale = locale
        self.dir = dir
        if self.multi:
            self.strings = rom.get_strings3()
            if locale not in self.strings.get_locales(_romhandler().get_rom_game()):
                raise ApiError("This ROM has no %s strings." % locale)
            if not 0 <= dir < self.strings.get_directory_count(locale):
                raise ApiError("There is no strings directory %d." % dir, 404)
        else:
            self.strings = rom.get_strings()

    def count(self):
        if self.multi:
            return self.strings.get_string_count(self.locale, self.dir)
        return self.strings.get_string_count()

    def read(self, index, raw=False):
        if not 0 <= index < self.count():
            raise ApiError("There is no string %d." % index, 404)
        if self.multi:
            return self.strings.read(self.locale, self.dir, index, raw)
        return self.strings.read(index, raw)

    def write(self, index, content):
        if self.multi:
            self.strings.write(self.locale, self.dir, index, content)
        else:
            self.strings.write(index, content)


def text_to_bytes(text):
    """The game's bytes for text (adapter character map), as strToBytes."""
    from ...lib.fs.strings import str_to_bytes
    return bytes(str_to_bytes(text))


@route("GET", "/api/strings")
def get_strings_info(req):
    rom = _rom()
    rh = _romhandler()
    from ...lib.types import get_game_name
    multi = _is_multi()
    locale = _locale(req)
    if multi:
        strings3 = rom.get_strings3()
        locales = list(strings3.get_locales(rh.get_rom_game()))
        if locale not in locales:
            locale = "en" if "en" in locales else (locales[0] if locales else locale)
        dirs = [{"index": d, "count": strings3.get_string_count(locale, d)}
                for d in range(strings3.get_directory_count(locale))]
    else:
        locales = []
        dirs = [{"index": 0, "count": rom.get_strings().get_string_count()}]
    return {"game": get_game_name(rh.get_rom_game()), "version": rh.get_game_version(),
            "multi": multi, "locales": locales, "locale": locale, "directories": dirs}


@route("GET", "/api/strings/list")
def list_strings(req):
    table = _Table(_locale(req), _int(req, "dir"))
    out = []
    for i in range(table.count()):
        try:
            out.append({"index": i, "text": table.read(i)})
        except Exception as e:  # noqa: BLE001 - one bad entry shouldn't hide the rest
            out.append({"index": i, "text": "", "error": str(e)})
    return {"locale": table.locale, "dir": table.dir, "strings": out}


@route("GET", "/api/strings/<int:index>")
def get_string(req, index):
    table = _Table(_locale(req), _int(req, "dir"))
    return {"index": index, "text": table.read(index),
            "raw": _hex_bytes(table.read(index, True))}


@route("POST", "/api/strings/write")
def write_string(req):
    table = _Table(_locale(req), _int(req, "dir"))
    index = _int(req, "index", -1)
    text = req.arg("text")
    if not isinstance(text, str):
        raise ApiError("The text is missing.")
    old = bytes(table.read(index, True))
    content = text_to_bytes(text.replace("\r\n", "\n"))
    # The game reads up to a NUL; keep the terminator the string had.
    if old.endswith(b"\x00") and not content.endswith(b"\x00"):
        content += b"\x00"
    table.write(index, bytearray(content))
    return {"index": index, "text": table.read(index), "raw": _hex_bytes(table.read(index, True))}


def search(query, locale="en", raw=False):
    """Strings containing query (as dump.findStrings/findStrings3): [{dir, index, text}]."""
    rom = _rom()
    results = []
    if _is_multi():
        strings3 = rom.get_strings3()
        dirs = range(strings3.get_directory_count(locale))
        tables = [(d, strings3.get_string_count(locale, d),
                   (lambda d: lambda s, r=False: strings3.read(locale, d, s, r))(d)) for d in dirs]
    else:
        strings = rom.get_strings()
        tables = [(None, strings.get_string_count(), strings.read)]
    for d, count, read in tables:
        for s in range(count):
            try:
                text = read(s)
            except Exception:  # noqa: BLE001
                continue
            if query not in text:
                continue
            entry = {"dir": d, "index": s, "text": text}
            if raw:
                entry["raw"] = _hex_bytes(read(s, True))
            results.append(entry)
            if len(results) >= MAX_RESULTS:
                return results
    return results


@route("GET", "/api/strings/search")
def search_strings(req):
    query = req.query.get("q", "")
    results = search(query, _locale(req), req.query.get("raw") in ("1", "true"))
    return {"query": query, "results": results, "truncated": len(results) >= MAX_RESULTS}
