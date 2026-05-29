import io
from dataclasses import dataclass

from PIL import Image



ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


@dataclass(frozen=True)
class AvatarProcessingResult:
    image_bytes: bytes
    content_type: str


def _get_extension(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower().strip()


def _guess_image_format(file_bytes: bytes) -> str:
    # imghdr is not available in some Python builds.
    # Fallback: rely on Pillow's decoder for image-type sanity.
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            return (img.format or "").lower()
    except Exception:
        return ""



def validate_avatar_upload(
    file_name: str,
    content_type: str,
    size_bytes: int,
    file_bytes: bytes,
) -> None:
    """Strict validation: extension + content-type + magic/decoder sanity."""
    if size_bytes <= 0:
        raise ValueError("Invalid file size.")

    max_bytes = 5 * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValueError("File too large. Max size is 5MB.")

    ext = _get_extension(file_name)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type.")

    # Content-Type can be missing; only enforce when present.
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported file content type.")

    guessed = _guess_image_format(file_bytes)
    # imghdr returns: 'jpeg', 'png', 'webp'
    if guessed not in {"jpeg", "png", "webp"}:
        raise ValueError("Invalid image payload.")


def process_avatar_image(file_bytes: bytes) -> AvatarProcessingResult:
    """Normalize to a 256x256 square WebP avatar.

    - Preserves aspect ratio and center-crops.
    - Converts to RGB to avoid alpha-channel issues.
    """
    with Image.open(io.BytesIO(file_bytes)) as img:
        img.verify()

    # Re-open after verify (Pillow needs it to decode again)
    with Image.open(io.BytesIO(file_bytes)) as img:
        img = img.convert("RGBA")

        # Handle transparency by compositing on a dark background
        if img.mode in {"RGBA", "LA"}:
            bg = Image.new("RGBA", img.size, (15, 15, 26, 255))
            bg.alpha_composite(img)
            img = bg.convert("RGB")
        else:
            img = img.convert("RGB")

        w, h = img.size
        if w <= 0 or h <= 0:
            raise ValueError("Invalid image dimensions.")

        # Center crop to square
        side = min(w, h)
        left = int((w - side) / 2)
        top = int((h - side) / 2)
        img = img.crop((left, top, left + side, top + side))

        img = img.resize((256, 256), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        # quality tuned for small size; loss acceptable for avatars.
        img.save(
            out,
            format="WEBP",
            quality=85,
            method=6,
            optimize=True,
        )
        return AvatarProcessingResult(image_bytes=out.getvalue(), content_type="image/webp")

