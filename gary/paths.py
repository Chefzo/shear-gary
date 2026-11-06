from __future__ import annotations

import tempfile
from pathlib import Path

from gary.errors import UnsafePath


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def assert_safe_data_dir(path: Path) -> Path:
    """Allow a data directory under the working directory or the system temp dir.

    Absolute paths outside those roots are refused so a bad flag cannot wipe
    or write an unrelated location.
    """

    resolved = path.expanduser().resolve()
    if resolved == Path(resolved.anchor):
        raise UnsafePath("refusing the filesystem root as a data directory")
    cwd = Path.cwd().resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    allowed = resolved == cwd or cwd in resolved.parents or resolved == tmp or tmp in resolved.parents
    if not allowed:
        raise UnsafePath(
            "data directory must stay inside the working directory or the system temp directory"
        )
    return resolved
