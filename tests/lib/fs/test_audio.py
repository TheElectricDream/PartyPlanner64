import pytest

from partyplanner64.lib.fs import audio as audio_fs
from partyplanner64.lib.fs.audio import Audio


class _Seq:
    def __init__(self, n):
        self.midis = []
        self.n = n

    def get_byte_length(self):
        return self.n

    def pack(self, buffer, offset):
        buffer[offset:offset + self.n] = b"S" * self.n
        return self.n


class _Snd:
    sounds = []


class _Rom:
    def get_game(self):
        return "TEST"


def _audio(infos, parsed, buffers):
    audio_fs._audio_offsets["TEST"] = infos
    a = Audio(_Rom())
    a._parsed_cache = parsed
    a._buffer_cache = buffers
    return a


def test_tables_lengths_and_pack():
    infos = [{"type": "S2", "offsets": []}, {"type": "T3", "byte_length": 0x20, "offsets": []},
             {"type": "MBF0", "offsets": []}, {"type": "Pointer", "byte_length": 0, "offsets": []}]
    seq1, seq2, snd = _Seq(0x13), _Seq(0x20), _Snd()
    try:
        a = _audio(infos, [seq1, snd, seq2, None], [b"", b"T" * 0x20, b"", None])
        assert a.get_sequence_table_count() == 2 and a.get_sound_table_count() == 1
        assert a.get_sequence_table(1) is seq2 and a.get_sequence_table(2) is None
        assert a.get_sound_table(0) is snd
        assert a.get_byte_length() == 0x13 + 0x20 + 0x20
        buf = bytearray(0x80)
        written = a.pack(buf, 0x10)
        assert written == 0x60
        assert buf[0x10:0x23] == b"S" * 0x13 and buf[0x30:0x50] == b"T" * 0x20 and buf[0x50:0x70] == b"S" * 0x20
        with pytest.raises(NotImplementedError):
            a.read(0)
    finally:
        del audio_fs._audio_offsets["TEST"]


def test_unhandled_type():
    try:
        a = _audio([{"type": "XX", "offsets": []}], [None], [None])
        with pytest.raises(ValueError):
            a.get_byte_length()
    finally:
        del audio_fs._audio_offsets["TEST"]
