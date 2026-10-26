"""Image validation and safe re-encoding for listing photos."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SOURCE_PIXELS = 40_000_000
MAX_OUTPUT_EDGE = 1600
JPEG_QUALITY = 85


class PhotoValidationError(ValueError):
    """Raised when an upload is not a safe, supported still image."""


@dataclass(frozen=True, slots=True)
class ProcessedPhoto:
    data: bytes
    mime_type: str
    width: int
    height: int


def process_photo(raw: bytes, *, max_bytes: int) -> ProcessedPhoto:
    """Validate an upload, strip metadata, and re-encode it as JPEG."""
    if not raw:
        raise PhotoValidationError("Photo is empty.")
    if len(raw) > max_bytes:
        raise PhotoValidationError("Photo is larger than the upload limit.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise PhotoValidationError("Photo must be a JPEG, PNG, or WebP still image.")
                if getattr(source, "n_frames", 1) > 1:
                    raise PhotoValidationError("Animated images are not supported.")
                width, height = source.size
                if width <= 0 or height <= 0:
                    raise PhotoValidationError("Photo has invalid dimensions.")
                if width * height > MAX_SOURCE_PIXELS:
                    raise PhotoValidationError("Photo resolution is too large.")
                source.load()
                image = ImageOps.exif_transpose(source)

            image = _flatten_alpha(image)
            image.thumbnail(
                (MAX_OUTPUT_EDGE, MAX_OUTPUT_EDGE),
                Image.Resampling.LANCZOS,
            )
            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
            )
    except PhotoValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise PhotoValidationError("Photo is not a valid image.") from exc
    except Image.DecompressionBombError as exc:
        raise PhotoValidationError("Photo resolution is too large.") from exc
    except Image.DecompressionBombWarning as exc:
        raise PhotoValidationError("Photo resolution is too large.") from exc

    encoded = output.getvalue()
    if len(encoded) > max_bytes:
        raise PhotoValidationError("Photo is larger than the upload limit.")
    return ProcessedPhoto(
        data=encoded,
        mime_type="image/jpeg",
        width=image.width,
        height=image.height,
    )


def _flatten_alpha(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")
