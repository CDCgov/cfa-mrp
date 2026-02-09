"""File staging — resolve URIs to local paths."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

_stage_dir: Path | None = None


def get_stage_dir() -> Path:
    global _stage_dir
    if _stage_dir is None:
        _stage_dir = Path(tempfile.mkdtemp(prefix="mrp_staged_"))
    return _stage_dir


def stage_files(files: dict[str, str]) -> dict[str, str]:
    """Stage files from URIs to local paths.

    Supports: local paths, http/https URLs, s3:// (placeholder).
    Returns a new dict mapping logical names to local file paths.
    """
    if not files:
        return {}

    staged = {}
    for name, uri in files.items():
        staged[name] = str(_stage_one(name, uri))
    return staged


def _stage_one(name: str, uri: str) -> Path:
    parsed = urlparse(uri)

    # Local file — just verify it exists and return as-is
    if not parsed.scheme or parsed.scheme == "file":
        local = Path(parsed.path if parsed.scheme == "file" else uri)
        if not local.exists():
            raise FileNotFoundError(f"File not found for '{name}': {local}")
        return local

    # HTTP(S) — download to stage dir
    if parsed.scheme in ("http", "https"):
        dest = get_stage_dir() / name / Path(parsed.path).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(uri, dest)
        return dest

    # S3 — placeholder
    if parsed.scheme == "s3":
        raise NotImplementedError(
            f"S3 staging not yet implemented for '{name}': {uri}. "
            "Use a local path or HTTP URL for now."
        )

    raise ValueError(f"Unsupported URI scheme '{parsed.scheme}' for '{name}': {uri}")


def cleanup():
    global _stage_dir
    if _stage_dir and _stage_dir.exists():
        shutil.rmtree(_stage_dir, ignore_errors=True)
        _stage_dir = None
