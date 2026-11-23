"""The code reference (lib/reference): GET /api/reference.

    GET /api/reference -> {categories: ["Events", "MIPS", ...], entries: [{id, kind, category,
        name, words, lang, syntax, summary, body, examples, see, games, contexts, tags}],
        functions: {name: sentence}}

"functions" has one sentence for every named game function, for the ones without an entry.

The editor's hover help and completions, and the Reference page, read it once. The
games' own symbols (addresses, the symbol tables' comments) come from GET /api/symbols.
"""

from ..http import route


@route("GET", "/api/reference")
def get_reference(req):
    from ...lib.reference import CATEGORIES, get_entries
    from ...lib.reference.sentences import FUNCTIONS
    return {"categories": CATEGORIES, "entries": get_entries(), "functions": FUNCTIONS}
