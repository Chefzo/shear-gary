"""Copy an optional local file and store metadata. Bytes stay under data/photos."""

from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path

from gary.errors import PhotoError
from gary.models import Photo, PhotoInput
from gary.util import utcnow

MAX_PHOTO_BYTES = 15 * 1024 * 1024
MAX_PHOTOS = 8


def safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._")
    if not cleaned:
        cleaned = "photo"
    return cleaned[:80]


def store_photo(
    photos_dir: Path,
    data_dir: Path,
    request_id: str,
    photo_id: str,
    incoming: PhotoInput,
) -> tuple[Photo, Path | None]:
    if incoming.path:
        return _copy_file(photos_dir, data_dir, request_id, photo_id, incoming)
    if not incoming.filename:
        raise PhotoError("a photo needs a filename or a local path")
    return (
        Photo(
            id=photo_id,
            request_id=request_id,
            filename=safe_filename(incoming.filename),
            content_type=incoming.content_type,
            size_bytes=None,
            sha256=None,
            stored_relative_path=None,
            note=_note(incoming.note) or "metadata only; file bytes were not on this machine",
            created_at=utcnow(),
        ),
        None,
    )


def _copy_file(
    photos_dir: Path,
    data_dir: Path,
    request_id: str,
    photo_id: str,
    incoming: PhotoInput,
) -> tuple[Photo, Path]:
    src = Path(incoming.path or "").expanduser()
    if src.is_symlink():
        raise PhotoError("refusing a symlink as a photo source")
    if not src.is_file():
        raise PhotoError(f"photo file not found: {src.name}")
    size = src.stat().st_size
    if size > MAX_PHOTO_BYTES:
        raise PhotoError("photo is over the 15 MB local cap")
    filename = safe_filename(incoming.filename or src.name)
    dest = _destination(photos_dir, request_id, filename)
    blob = src.read_bytes()
    if len(blob) != size:
        raise PhotoError("photo size changed while reading")
    dest.write_bytes(blob)
    relative = dest.resolve().relative_to(data_dir.resolve()).as_posix()
    content_type = incoming.content_type or mimetypes.guess_type(filename)[0]
    photo = Photo(
        id=photo_id,
        request_id=request_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(blob),
        sha256=hashlib.sha256(blob).hexdigest(),
        stored_relative_path=relative,
        note=_note(incoming.note),
        created_at=utcnow(),
    )
    return photo, dest


def _destination(photos_dir: Path, request_id: str, filename: str) -> Path:
    if not re.fullmatch(r"req_[a-f0-9]{12}", request_id):
        raise PhotoError("refusing to store a photo under an unexpected request id")
    root = photos_dir.resolve()
    folder = (photos_dir / request_id).resolve()
    if folder != root and root not in folder.parents:
        raise PhotoError("photo folder escaped the data directory")
    folder.mkdir(parents=True, exist_ok=True)
    dest = (folder / filename).resolve()
    if root not in dest.parents:
        raise PhotoError("photo path escaped the data directory")
    return dest


def _note(note: str | None) -> str | None:
    if note is None:
        return None
    text = note.strip()
    if len(text) > 500:
        raise PhotoError("photo note is too long")
    return text or None
