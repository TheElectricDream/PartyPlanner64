"""Adapter lookup (port of adapter/adapters.ts).

The game adapters are imported when first asked for: boards imports this
module, and the adapters import boards.
"""


def get_rom_adapter(adapter_options=None):
    """Return the adapter for the loaded ROM's game, or None."""
    from ..romhandler import romhandler

    game = romhandler.get_game_version()
    if not game:
        return None

    return get_adapter(game, adapter_options)


def get_adapter(game, adapter_options=None):
    """Return a new adapter for a game version (1, 2 or 3), or None.

    Args:
        game: The game version.
        adapter_options: IAdapterOptions dict ({"write_branding": bool}).
    """
    if adapter_options is None:
        adapter_options = {}
    if game == 1:
        from .mp1 import MP1Adapter
        return MP1Adapter(adapter_options)
    if game == 2:
        from .mp2 import MP2Adapter
        return MP2Adapter(adapter_options)
    if game == 3:
        from .mp3 import MP3Adapter
        return MP3Adapter(adapter_options)

    return None
