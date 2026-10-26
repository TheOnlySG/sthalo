"""Unit tests for listing image validation and re-encoding."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.modules.listings import photos as photo_module
from app.modules.listings.photos import PhotoValidationError, process_photo


def _save(image: Image.Image, fmt: str, **kwargs: object) -> bytes:
    output = BytesIO()
    image.save(output, format=fmt, **kwargs)
    return output.getvalue()


def test_jpeg_is_reencoded_and_metadata_removed() -> None:
    image = Image.new("RGB", (2400, 1200), (20, 100, 180))
    exif = Image.Exif()
    exif[0x0112] = 6
    exif[0x010F] = "Test Camera"
    raw = _save(image, "JPEG", exif=exif)

    processed = process_photo(raw, max_bytes=5 * 1024 * 1024)

    assert processed.mime_type == "image/jpeg"
    assert max(processed.width, processed.height) <= 1600
    assert len(processed.data) < len(raw)
    with Image.open(BytesIO(processed.data)) as result:
        assert result.format == "JPEG"
        assert len(result.getexif()) == 0


def test_png_transparency_is_flattened() -> None:
    image = Image.new("RGBA", (100, 80), (255, 0, 0, 0))
    raw = _save(image, "PNG")

    processed = process_photo(raw, max_bytes=5 * 1024 * 1024)

    with Image.open(BytesIO(processed.data)) as result:
        assert result.mode == "RGB"
        assert result.size == (100, 80)


def test_animated_webp_is_rejected() -> None:
    frames = [
        Image.new("RGB", (20, 20), (255, 0, 0)),
        Image.new("RGB", (20, 20), (0, 255, 0)),
    ]
    raw = _save(frames[0], "WEBP", save_all=True, append_images=frames[1:])

    with pytest.raises(PhotoValidationError, match="Animated"):
        process_photo(raw, max_bytes=5 * 1024 * 1024)


def test_svg_and_plain_text_are_rejected() -> None:
    with pytest.raises(PhotoValidationError):
        process_photo(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", max_bytes=1024)
    with pytest.raises(PhotoValidationError):
        process_photo(b"not an image", max_bytes=1024)


def test_raw_upload_limit_is_enforced() -> None:
    raw = _save(Image.new("RGB", (10, 10)), "JPEG")

    with pytest.raises(PhotoValidationError, match="upload limit"):
        process_photo(raw, max_bytes=len(raw) - 1)


def test_source_pixel_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(photo_module, "MAX_SOURCE_PIXELS", 100)
    raw = _save(Image.new("RGB", (20, 20)), "JPEG")

    with pytest.raises(PhotoValidationError, match="resolution"):
        process_photo(raw, max_bytes=5 * 1024 * 1024)
