# In the name of God, the Most Gracious, the Most Merciful
"""Content hashes and a single-file replace that refuses a stale hash."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from mcp_app_core.errors import ArtifactMissingError, ContentConflictError, ValidationError

_HEX = frozenset("0123456789abcdef")
_HASH_PREFIX = "sha256:"


def content_sha256(content: bytes) -> str:
    """Return the lowercase SHA-256 hex digest of ``content``."""

    if not isinstance(content, bytes):
        raise ValidationError("Content hash requires bytes.")
    return hashlib.sha256(content).hexdigest()


def file_content_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of one file's bytes."""

    target = Path(path)
    if not target.is_file():
        raise ArtifactMissingError(f"File not found: {target.name}")
    try:
        data = target.read_bytes()
    except FileNotFoundError as exc:
        raise ArtifactMissingError(f"File not found: {target.name}") from exc
    return content_sha256(data)


def _normalize_hash(value: object) -> str:
    if not isinstance(value, str):
        raise ValidationError("Content hash must be a SHA-256 hex digest.")
    text = value.strip().lower()
    if text.startswith(_HASH_PREFIX):
        text = text[len(_HASH_PREFIX) :]
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ValidationError("Content hash must be a SHA-256 hex digest.")
    return text


def _write_temporary(directory: Path, content: bytes) -> Path:
    descriptor, raw_name = tempfile.mkstemp(prefix=".commit-", suffix=".part", dir=directory)
    temp_path = Path(raw_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def commit_file(path: Path, *, expected_hash: str, content: bytes) -> str:
    """Replace one file when its bytes still match ``expected_hash``.

    The hash is the SHA-256 digest from ``content_sha256`` or
    ``file_content_sha256``. A mismatch raises ``ContentConflictError`` and
    leaves the destination bytes in place. The new bytes are written to a
    temporary file in the same directory, then that file replaces the
    destination. The return value is the hash of the bytes just written.
    """

    if not isinstance(content, bytes):
        raise ValidationError("commit_file writes bytes.")
    digest = _normalize_hash(expected_hash)
    target = Path(path).resolve(strict=False)
    if not target.is_file():
        raise ArtifactMissingError(f"File not found: {target.name}")
    try:
        snapshot = target.read_bytes()
    except FileNotFoundError as exc:
        raise ArtifactMissingError(f"File not found: {target.name}") from exc
    actual = content_sha256(snapshot)
    if actual != digest:
        raise ContentConflictError(expected_hash=digest, actual_hash=actual)

    new_hash = content_sha256(content)
    temp_path = _write_temporary(target.parent, content)
    try:
        latest = target.read_bytes()
    except FileNotFoundError as exc:
        temp_path.unlink(missing_ok=True)
        raise ArtifactMissingError(f"File not found: {target.name}") from exc
    if latest != snapshot:
        temp_path.unlink(missing_ok=True)
        raise ContentConflictError(expected_hash=digest, actual_hash=content_sha256(latest))
    try:
        temp_path.replace(target)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return new_hash
