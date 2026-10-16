"""Image helpers that stand in for the browser canvas (Pillow-backed).

The TypeScript drew on an HTML canvas to decode, resize and encode images
(utils/canvas.ts, utils/img/getImageData.ts, toDataURL calls). Here:

- ImageData is a width, height and an RGBA bytearray, as in the browser.
- Image sources are what boards store: "data:image/png;base64,..." URLs.
  Paths and raw bytes are accepted too.
- Compositing that used drawImage is done with Pillow Images directly
  (to_pil / from_pil convert).
"""

import base64
import io

from PIL import Image


class ImageData:
    """RGBA pixels: data has width * height * 4 bytes."""

    __slots__ = ("width", "height", "data")

    def __init__(self, width, height, data=None):
        self.width = int(width)
        self.height = int(height)
        if data is None:
            data = bytearray(self.width * self.height * 4)
        elif not isinstance(data, bytearray):
            data = bytearray(data)
        if len(data) != self.width * self.height * 4:
            raise ValueError("ImageData of %dx%d needs %d bytes, got %d"
                             % (self.width, self.height, self.width * self.height * 4, len(data)))
        self.data = data

    def __repr__(self):
        return "ImageData(%dx%d)" % (self.width, self.height)


def create_image_data(width, height):
    """Return a transparent ImageData (canvasCtx.createImageData)."""
    return ImageData(width, height)


def data_url_to_bytes(data_url):
    """Return the bytes a base64 data URL holds."""
    head, _, payload = data_url.partition(",")
    if ";base64" in head:
        return base64.b64decode(payload)
    from urllib.parse import unquote_to_bytes
    return unquote_to_bytes(payload)


def bytes_to_data_url(data, mime="image/png"):
    """Return a base64 data URL for bytes."""
    return "data:%s;base64,%s" % (mime, base64.b64encode(bytes(data)).decode("ascii"))


def open_image(src):
    """Open an image source as a Pillow RGBA Image.

    Args:
        src: A data URL, a file path (str or Path), bytes, or a Pillow Image.
    """
    if isinstance(src, Image.Image):
        img = src
    elif isinstance(src, (bytes, bytearray, memoryview)):
        img = Image.open(io.BytesIO(bytes(src)))
    elif isinstance(src, str) and src.startswith("data:"):
        img = Image.open(io.BytesIO(data_url_to_bytes(src)))
    else:
        img = Image.open(src)
    return img.convert("RGBA")


def to_pil(image_data):
    """Return a Pillow RGBA Image of an ImageData."""
    return Image.frombytes("RGBA", (image_data.width, image_data.height), bytes(image_data.data))


def from_pil(img):
    """Return the ImageData of a Pillow Image."""
    img = img.convert("RGBA")
    return ImageData(img.width, img.height, bytearray(img.tobytes()))


def get_image_data(src, width, height):
    """Return the ImageData for an image source, sized to width x height.

    Port of utils/img/getImageData.ts: when the size differs it resizes
    with the exact port of npm resize-image-data (bilinear), so images
    written to ROMs match the TypeScript's pixel for pixel.
    """
    from .img.get_image_data import get_image_data as exact
    return exact(src, width, height)


def image_data_to_data_url(image_data):
    """Return a PNG data URL of an ImageData (canvas.toDataURL())."""
    return pil_to_data_url(to_pil(image_data))


def pil_to_data_url(img):
    """Return a PNG data URL of a Pillow Image."""
    out = io.BytesIO()
    img.save(out, format="PNG")
    return bytes_to_data_url(out.getvalue(), "image/png")


def rgba_to_data_url(buffer, width, height):
    """Return a PNG data URL of raw RGBA32 bytes (arrayBufferToDataURL)."""
    return image_data_to_data_url(ImageData(width, height, bytearray(buffer)))


def image_size(src):
    """Return (width, height) of an image source."""
    img = open_image(src)
    return img.width, img.height
