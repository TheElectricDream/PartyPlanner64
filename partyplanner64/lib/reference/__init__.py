"""The code reference: what the words in event, background and music code mean.

The editor shows it when the mouse rests on a word of code (hover help), next to
completions, and on the Reference page (GET /api/reference). An entry is a dict:

    id        "mips:addiu", "reg:a0", "dir:ascii", "hdr:games", "param:space",
              "concept:delay-slot", "c:if", "board:default_bg", "game:AdjustPlayerCoins"
    kind      instruction, pseudo, register, directive, syntax, header, parameter,
              concept, c-keyword, c-type, c-library, board, function, variable
    category  the Reference page's group: "MIPS", "C", "Events", "Board code", "Game"
    name      as it is written in code ("ADDIU", "A0", ".ascii", "if", "DEFAULT_BG")
    words     the words that bring up the entry in the editor (lower case; default: name)
    lang      the language it is a word of: "mips", "c" or "any"
    syntax    how it is written (optional)
    summary   one sentence
    body      the explanation, in a little markup: paragraphs (blank lines between),
              "- " bullet lines, `code`, **bold**, [[id]] or [[id|text]] links
    examples  [{title, lang ("mips"/"c"), code, check}]; every example is assembled or
              compiled by the tests (see examples_to_check), so they stay correct:
                check "event": a whole event (with its header)
                check "mips":  instructions inside an event (a header and the RA save
                               are put around them)
                check "c":     statements inside main()
                check "c-top": C outside any function (declarations, other functions)
                check "background" / "music": board code (Details page)
                check "none":  not checked (for code that is wrong on purpose)
              "params" ([[type, name]]) gives the event parameters an example uses.
    see       ids of related entries
    games     game functions and data: the games ("MP3_USA") the entry is about
    contexts  board code words: the code they belong to ("event", "background", "music")
    tags      more words to search by

Game functions and data the reference does not explain are still shown (from the
symbol tables, GET /api/symbols); this is for the ones worth explaining.
"""

import re

from . import c, events, games, mips

CATEGORIES = ["Events", "MIPS", "C", "Board code", "Game"]

_KINDS = {"instruction", "pseudo", "register", "directive", "syntax", "header", "parameter",
          "concept", "c-keyword", "c-type", "c-library", "board", "function", "variable"}
_CHECKS = {"event", "mips", "c", "c-top", "background", "music", "none"}
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

_entries = None


def _normalize(entry):
    e = dict(entry)
    e.setdefault("lang", "any")
    e.setdefault("words", [e["name"].lower()])
    e["words"] = [w.lower() for w in e["words"]]
    e.setdefault("summary", "")
    e.setdefault("body", "")
    e.setdefault("examples", [])
    e.setdefault("see", [])
    e.setdefault("tags", [])
    return e


def get_entries():
    """Every entry, in the Reference page's order (cached)."""
    global _entries
    if _entries is None:
        raw = events.ENTRIES + mips.entries() + c.ENTRIES + events.BOARD_ENTRIES + games.ENTRIES
        _entries = [_normalize(e) for e in raw]
    return _entries


def get_entry(entry_id):
    return next((e for e in get_entries() if e["id"] == entry_id), None)


def links(text):
    """The entry ids that [[links]] in text name."""
    return _LINK.findall(text or "")


def problems():
    """What is wrong with the entries (for the tests): unknown kinds, duplicate ids,
    links and "see" ids that name no entry."""
    out = []
    ids = set()
    for e in get_entries():
        if e["id"] in ids:
            out.append("duplicate id %s" % e["id"])
        ids.add(e["id"])
        if e["kind"] not in _KINDS:
            out.append("%s: unknown kind %s" % (e["id"], e["kind"]))
        if e["category"] not in CATEGORIES:
            out.append("%s: unknown category %s" % (e["id"], e["category"]))
        if e["lang"] not in ("mips", "c", "any"):
            out.append("%s: unknown lang %s" % (e["id"], e["lang"]))
        if not e["summary"]:
            out.append("%s: no summary" % e["id"])
        for ex in e["examples"]:
            if ex.get("check") not in _CHECKS:
                out.append("%s: example %r has check %r" % (e["id"], ex.get("title"), ex.get("check")))
            if ex.get("lang") not in ("mips", "c"):
                out.append("%s: example %r has lang %r" % (e["id"], ex.get("title"), ex.get("lang")))
    for e in get_entries():
        for target in e["see"] + links(e["body"]) + links(e["summary"]):
            if target not in ids:
                out.append("%s links to unknown entry %s" % (e["id"], target))
    return out


def examples_to_check():
    """(entry id, example) for each example the tests assemble or compile."""
    return [(e["id"], ex) for e in get_entries() for ex in e["examples"] if ex["check"] != "none"]
