"""The games' song names, which need no ROM (the adapters know them).

    GET /api/songs/<game>  ->  {"game": 1|2|3, "names": {index: name}}

Used by the Details page to pick a board's in-game music by name.
"""

from ..http import ApiError, route


@route("GET", "/api/songs/<int:game>")
def song_names(req, game):
    if game not in (1, 2, 3):
        raise ApiError("There is no Mario Party %d." % game)
    from ...lib.adapter.adapters import get_adapter
    names = get_adapter(game).get_audio_map(0)
    return {"game": game, "names": {str(i): n for i, n in enumerate(names) if n}}
