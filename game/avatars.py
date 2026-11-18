"""Profile pictures: the Staunton pieces a player can pick, and uploads.

An upload is re-encoded by Pillow and kept in the database as a data URI,
because Vercel has no disk that lasts between requests. Pages never inline
that data: they point an <img> at /u/<id>/avatar/, which serves the bytes
with a long cache, so a leaderboard of fifty players stays a small page.
"""

import base64
import io

from django.templatetags.static import static
from PIL import Image

PRESETS = (
    ('wk', 'White king'),
    ('wq', 'White queen'),
    ('wr', 'White rook'),
    ('wb', 'White bishop'),
    ('wn', 'White knight'),
    ('wp', 'White pawn'),
    ('bk', 'Black king'),
    ('bq', 'Black queen'),
    ('br', 'Black rook'),
    ('bb', 'Black bishop'),
    ('bn', 'Black knight'),
    ('bp', 'Black pawn'),
)

# Uploads come out as one of these; anything else in the column is not served.
SERVED_TYPES = ('image/png', 'image/jpeg')
MAX_SIDE = 256
MAX_SOURCE_SIDE = 4096


class AvatarError(ValueError):
    """The upload could not be turned into a picture."""


def preset_url(key):
    return static(f'game/pieces/staunton-single/{key}.webp')


def encode_upload(uploaded_file):
    """Return the upload as a data URI of a PNG or JPEG at most 256 px a side.

    Re-encoding keeps only the pixels, so metadata and anything hidden in the
    original file are dropped.
    """
    try:
        image = Image.open(uploaded_file)
        if image.size[0] > MAX_SOURCE_SIDE or image.size[1] > MAX_SOURCE_SIDE:
            raise AvatarError(f'Pictures can be at most {MAX_SOURCE_SIDE} pixels a side.')
        # Decoding everything now finds truncated files before any resizing.
        image.load()
    except AvatarError:
        raise
    except Exception as exc:
        # Pillow reports broken files with several unrelated exception types.
        raise AvatarError('That file is not a picture Checkora can read.') from exc

    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGBA')
        save_format, mime = 'PNG', 'image/png'
    else:
        image = image.convert('RGB')
        save_format, mime = 'JPEG', 'image/jpeg'

    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    buffer = io.BytesIO()
    if save_format == 'JPEG':
        image.save(buffer, format='JPEG', quality=85, optimize=True)
    else:
        image.save(buffer, format='PNG', optimize=True)
    return f'data:{mime};base64,{base64.b64encode(buffer.getvalue()).decode()}'


def decode(data_uri):
    """Split a stored data URI into (mime type, bytes), or None if it is not one we serve."""
    header, separator, payload = data_uri.partition(';base64,')
    mime = header.removeprefix('data:')
    if not separator or mime not in SERVED_TYPES:
        return None
    try:
        return mime, base64.b64decode(payload, validate=True)
    except ValueError:
        return None
