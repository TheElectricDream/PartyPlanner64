"""GET /api/image/<sha1>: images of the boards (see partyplanner64/editor/images.py)."""

from ...editor import images
from ..http import ApiError, Response, route


@route("GET", "/api/image/<sha>")
def get_image(req, sha):
    found = images.get(sha.lower())
    if found is None:
        raise ApiError("No such image.", 404)
    mime, data = found
    # The URL names the content, so it may be cached for good.
    return Response(data, mime, headers=[("X-Content-Type-Options", "nosniff"),
                                         ("Cache-Control", "public, max-age=31536000, immutable"),
                                         # Board files are untrusted: no scripts in SVGs.
                                         ("Content-Security-Policy",
                                          "default-src 'none'; style-src 'unsafe-inline'; sandbox")])
