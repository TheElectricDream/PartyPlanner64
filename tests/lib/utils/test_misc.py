import io
import zipfile

import pytest
from PIL import Image

from partyplanner64.lib.utils import arrays, colors, string
from partyplanner64.lib.utils.canvas import bytes_to_data_url
from partyplanner64.lib.utils.dataview import DataView
from partyplanner64.lib.utils.img.get_image_data import get_image_data
from partyplanner64.lib.utils.image import to_array_buffer


def test_copy_range():
    out = bytearray(8)
    arrays.copy_range(out, b"abcdef", 2, 1, 3)
    assert out == b"\0\0bcd\0\0\0"
    arrays.copy_range(DataView(out, 4), [1, 2, 0x103], 0, 0, 3)
    assert out[4:7] == b"\1\2\3"
    arrays.copy_range(out, DataView(bytearray(b"xyz"), 1), 0, 0, 2)
    assert out[:2] == b"yz"
    with pytest.raises(IndexError):
        arrays.copy_range(out, b"abc", 7, 0, 2)
    with pytest.raises(IndexError):
        arrays.copy_range(out, b"abc", 0, 2, 2)
    assert len(out) == 8


def test_array_helpers():
    assert arrays.array_buffers_equal(b"ab", bytearray(b"ab")) and not arrays.array_buffers_equal(b"ab", b"a")
    assert arrays.join(b"ab", b"cd") == b"abcd" and arrays.join(None, b"x") == b"x"
    assert arrays.data_url_to_array_buffer("data:x;base64,AAEC") == b"\0\1\2"
    a = {"k": 1}
    assert arrays.equal([1, a], [1, a]) and not arrays.equal([{"k": 1}], [{"k": 1}])
    assert arrays.intersection([1, 2, 3], [3, 1]) == [1, 3]
    assert arrays.intersection([1, 2], [2], lambda x, y: x * 2 == y) == [1]
    assert arrays.create_filled_array(0, 3) == [0, 0, 0]
    assert arrays.hash_equal([b"abc", 0, 3], "900150983CD24FB0D6963F7D28E17F72")
    img = arrays.array_buffer_to_image_data(bytes(range(16)), 2, 2)
    assert img.data == bytes(range(16))
    assert arrays.array_buffer_to_data_url(bytes(16), 2, 2).startswith("data:image/png;base64,")


def test_string_helpers():
    assert string.pad("7", 3, "0") == "007"
    assert string.splice("abcdef", 1, -2, "XY") == "aXYdef"
    assert string.normalize_line_endings("a\r\nb\rc") == "a\nb\nc"
    assert string.string_comparer("a", "b") == -1 and string.string_comparer("b", "b") == 0
    assert string.to_char_codes("a\U0001F600") == [0x61, 0xD83D, 0xDE00]
    assert string.string_to_array_buffer("é") == b"\xc3\xa9"
    assert string.string_from_array_buffer(b"\xef\xbb\xbfhi\xff") == "hi�"


def test_colors():
    q = colors.make_color_queue()
    first = [q.next() for _ in range(21)]
    assert first[0] == [166, 189, 215] and first[20] == first[0]
    assert colors.get_distinct_color(19) == [35, 44, 22]


def test_get_image_data_from_data_url():
    img = Image.new("RGBA", (3, 2), (10, 20, 30, 255))
    img.putpixel((2, 1), (200, 100, 50, 0))
    out = io.BytesIO()
    img.save(out, "PNG")
    url = bytes_to_data_url(out.getvalue())
    data = get_image_data(url, 3, 2)
    assert (data.width, data.height) == (3, 2)
    assert bytes(data.data[:4]) == bytes((10, 20, 30, 255)) and bytes(data.data[20:24]) == bytes((200, 100, 50, 0))
    resized = get_image_data(url, 6, 4)
    assert (resized.width, resized.height) == (6, 4)
    assert bytes(to_array_buffer(url, 3, 2)) == bytes(data.data)


def test_dump_zip_round_trip(monkeypatch):
    from partyplanner64.lib.utils import dump

    class _FS:
        def __init__(self):
            self.files = [[bytearray(b"FORM...."), bytearray(b"plain")], [bytearray(b"x")]]
            self.written = []

        def get_directory_count(self):
            return len(self.files)

        def get_file_count(self, d):
            return len(self.files[d])

        def get(self, d, f):
            return self.files[d][f]

        def write(self, d, f, content):
            self.written.append((d, f, bytes(content)))

    fs = _FS()

    class _Rom:
        def get_main_fs(self):
            return fs

    class _Handler:
        def get_rom(self):
            return _Rom()

    class _Model:
        def __init__(self, magic):
            self.magic = magic

        def is_form(self, b):
            return bytes(b[:4]) == self.magic

        is_mtnx = is_form

    monkeypatch.setattr(dump, "_romhandler", lambda: _Handler())
    monkeypatch.setattr(dump, "_form_class", lambda: _Model(b"FORM"))
    monkeypatch.setattr(dump, "_mtnx_class", lambda: _Model(b"MTNX"))
    seen = []
    data = dump.create(seen.append)
    assert seen == [data]
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "mainfs/0/0.form" in names and "mainfs/0/1" in names and "mainfs/1/0" in names
    dump.load(data)
    assert sorted(fs.written) == [(0, 0, b"FORM...."), (0, 1, b"plain"), (1, 0, b"x")]
    errors = []
    dump.load(b"not a zip", errors.append)
    assert len(errors) == 1
