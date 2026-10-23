# In the name of God, the Most Gracious, the Most Merciful
"""Hash-guarded single-file commit."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_app_core.commit import commit_file, content_sha256, file_content_sha256
from mcp_app_core.errors import ArtifactMissingError, ContentConflictError, ValidationError
from mcp_app_core.handlers import error_payload


def test_commit_replaces_only_when_the_hash_matches(tmp_path: Path) -> None:
    path = tmp_path / "amp.qsch"
    path.write_bytes(b"v1")
    first = file_content_sha256(path)
    assert first == content_sha256(b"v1")

    second = commit_file(path, expected_hash=first.upper(), content=b"v2")
    assert path.read_bytes() == b"v2"
    assert second == content_sha256(b"v2")

    third = commit_file(path, expected_hash=f"sha256:{second}", content=b"v3")
    assert path.read_bytes() == b"v3"
    assert third == file_content_sha256(path)
    assert list(tmp_path.iterdir()) == [path]


def test_commit_refuses_a_stale_hash(tmp_path: Path) -> None:
    path = tmp_path / "amp.qsch"
    path.write_bytes(b"v1")
    stale = file_content_sha256(path)
    path.write_bytes(b"v2")

    with pytest.raises(ContentConflictError) as caught:
        commit_file(path, expected_hash=stale, content=b"v3")

    assert path.read_bytes() == b"v2"
    assert caught.value.expected_hash == stale
    assert caught.value.actual_hash == content_sha256(b"v2")
    assert caught.value.error_code == "content_conflict"
    assert "amp.qsch" not in str(caught.value)
    assert list(tmp_path.iterdir()) == [path]
    payload = error_payload(caught.value)
    assert payload["expected_hash"] == stale
    assert payload["actual_hash"] == content_sha256(b"v2")


def test_commit_rejects_a_malformed_hash(tmp_path: Path) -> None:
    path = tmp_path / "amp.qsch"
    path.write_bytes(b"v1")
    with pytest.raises(ValidationError, match="SHA-256"):
        commit_file(path, expected_hash="nope", content=b"v2")
    assert path.read_bytes() == b"v1"
    assert list(tmp_path.iterdir()) == [path]


def test_commit_requires_an_existing_file(tmp_path: Path) -> None:
    with pytest.raises(ArtifactMissingError):
        commit_file(tmp_path / "missing.qsch", expected_hash="ab" * 32, content=b"v1")


def test_content_hash_requires_bytes() -> None:
    with pytest.raises(ValidationError, match="bytes"):
        content_sha256("v1")  # type: ignore[arg-type]
