"""Stubs for the modules a ROM load/save calls outside of the file systems.

The synthetic ROMs of tests/fixtures/core/gen_rom.ts have no audio, no cheats
and use the adapters only for the character map and onAfterSave, so these
are replaced by stand-ins (the same ones the generator used).
"""

import sys
import types

from partyplanner64.lib.utils.dataview import DataView


def _module(monkeypatch, name):
    try:
        __import__(name)
        return sys.modules[name]
    except ImportError:
        mod = types.ModuleType(name)
        parent_name, _, child = name.rpartition(".")
        if parent_name:
            parent = _module(monkeypatch, parent_name)
            monkeypatch.setattr(parent, child, mod, raising=False)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod


class FakeAdapter:
    def __init__(self, game_version, char_map):
        self.game_version = game_version
        self._char_map = char_map

    def get_character_map(self):
        return self._char_map

    def on_after_save(self, rom_view):
        if self.game_version == 3:
            # MP3Adapter.onAfterSave
            rom_view.set_uint32(0x0000CEC0, 0)
            rom_view.set_uint32(0x0007FC58, 0)
            rom_view.set_uint32(0x0007FC60, 0)


def install(monkeypatch, char_map=None):
    from partyplanner64.lib.romhandler import romhandler

    hook = _module(monkeypatch, "partyplanner64.lib.patches.gameshark.hook")
    monkeypatch.setattr(hook, "apply_hook", lambda buffer: None, raising=False)
    cheats = _module(monkeypatch, "partyplanner64.lib.patches.gameshark.cheats")
    monkeypatch.setattr(cheats, "reset_cheats", lambda: None, raising=False)

    adapters = _module(monkeypatch, "partyplanner64.lib.adapter.adapters")
    monkeypatch.setattr(adapters, "get_rom_adapter",
                        lambda options=None: FakeAdapter(romhandler.get_game_version(), char_map or {}),
                        raising=False)

    try:
        import partyplanner64.lib.utils.mips as mips  # noqa: F401
        has_mips = hasattr(mips, "get_reg_set_address")
    except ImportError:
        mips = None
        has_mips = False
    if not has_mips:
        mips = _module(monkeypatch, "partyplanner64.lib.utils.mips")

        def get_reg_set_upper_and_lower(address):
            lower = address & 0x0000FFFF
            upper = (address & 0xFFFFFFFF) >> 16
            if lower & 0x8000:
                upper += 1
            return [upper, lower]

        def get_reg_set_address(upper, lower):
            upper &= 0x0000FFFF
            lower &= 0x0000FFFF
            if lower & 0x8000:
                upper -= 1
            return ((upper << 16) | lower) & 0x7FFFFFFF

        monkeypatch.setattr(mips, "get_reg_set_upper_and_lower", get_reg_set_upper_and_lower, raising=False)
        monkeypatch.setattr(mips, "get_reg_set_address", get_reg_set_address, raising=False)

    # The audio section stub of gen_rom.ts.
    from partyplanner64.lib.fs.audio import Audio

    def pack(self, buf, off):
        buf[off:off + 0x30] = bytes((0xA0 + i) & 0xFF for i in range(0x30))
        return 0x30

    monkeypatch.setattr(Audio, "extract", lambda self: None)
    monkeypatch.setattr(Audio, "get_byte_length", lambda self: 0x30)
    monkeypatch.setattr(Audio, "pack", pack)
    monkeypatch.setattr(Audio, "set_rom_offset", lambda self, off, buf: DataView(buf).set_uint32(0x100, off))
