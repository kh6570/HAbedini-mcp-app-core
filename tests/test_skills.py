# In the name of God, the Most Gracious, the Most Merciful
"""Skill manifest parsing and on-demand reference loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_app_core.errors import ArtifactMissingError, ParseError, ValidationError
from mcp_app_core.skills import SkillManifest, load_skill, load_skill_reference

_BISMILLAH = "In the name of God, the Most Gracious, the Most Merciful"


def _write_skill(
    root: Path,
    *,
    references: dict[str, str] | None = None,
    manifest_lines: str | None = None,
    skill_text: str | None = None,
    directory_name: str = "demo-skill",
) -> Path:
    skill = root / directory_name
    skill.mkdir(parents=True)
    skill_text = skill_text or (
        "---\n"
        "name: demo-skill\n"
        "description: Use when starting a demo task that needs a short router.\n"
        "license: MIT\n"
        "metadata:\n"
        "  author: demo\n"
        '  version: "1.1"\n'
        "---\n"
        f"{_BISMILLAH}\n\n"
        "# Demo\n\n"
        "Open notes.md for the procedure.\n"
    )
    manifest = manifest_lines or (
        f"# {_BISMILLAH}\n"
        "schema_version: 1\n"
        'version: "1.1"\n'
        "human-description: A demo skill for the parser.\n"
        "requires-tools:\n"
        "  - describe_server_capabilities\n"
        "requires-skills: []\n"
        "requires-products: []\n"
        "when-not-to-use: Do not use this for unrelated work.\n"
        "reference-files:\n"
        "  - notes.md\n"
    )
    (skill / "SKILL.md").write_text(skill_text, encoding="utf-8")
    (skill / "manifest.yaml").write_text(manifest, encoding="utf-8")
    if references is not None:
        reference_dir = skill / "reference"
        reference_dir.mkdir()
        for name, text in references.items():
            (reference_dir / name).write_text(text, encoding="utf-8")
    return skill


def test_load_skill_reads_manifest_and_short_body(tmp_path: Path) -> None:
    skill = _write_skill(
        tmp_path,
        references={"notes.md": f"{_BISMILLAH}\n\nREFERENCE SENTINEL procedure line.\n"},
    )
    loaded = load_skill(skill)
    assert loaded.manifest == SkillManifest(
        name="demo-skill",
        trigger="Use when starting a demo task that needs a short router.",
        when_not_to_use="Do not use this for unrelated work.",
        reference_files=("notes.md",),
    )
    assert loaded.body.startswith(_BISMILLAH)
    assert "REFERENCE SENTINEL" not in loaded.body
    assert "name: demo-skill" not in loaded.body
    assert "license: MIT" not in loaded.body


def test_load_skill_does_not_read_reference_bodies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill = _write_skill(
        tmp_path,
        references={"notes.md": "REFERENCE SENTINEL that must stay on disk.\n"},
    )
    reads: list[str] = []
    original = Path.read_text

    def tracking(self: Path, *args: object, **kwargs: object) -> str:
        reads.append(self.name)
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", tracking)
    loaded = load_skill(skill)
    assert "notes.md" not in reads
    assert set(reads) == {"SKILL.md", "manifest.yaml"}
    assert "REFERENCE SENTINEL" not in loaded.body


def test_load_skill_reference_reads_only_the_named_file(tmp_path: Path) -> None:
    skill = _write_skill(
        tmp_path,
        references={
            "notes.md": "The named procedure.\n",
            "other.md": "The other procedure.\n",
        },
        manifest_lines=(
            f"# {_BISMILLAH}\n"
            "when-not-to-use: Do not use this for unrelated work.\n"
            "reference-files:\n"
            "  - notes.md\n"
            "  - other.md\n"
        ),
    )
    assert load_skill_reference(skill, "other.md") == "The other procedure.\n"
    with pytest.raises(ValidationError, match="not listed"):
        load_skill_reference(skill, "notes.md/../../secret.md")


def test_unlisted_and_escaping_names_are_refused(tmp_path: Path) -> None:
    secret = tmp_path / "secret.md"
    secret.write_text("SECRET", encoding="utf-8")
    skill = _write_skill(tmp_path, references={"notes.md": "Visible procedure.\n"})
    (skill / "reference" / "extra.md").write_text("Not listed.\n", encoding="utf-8")
    for name in ("extra.md", "../secret.md", "..\\secret.md", str(secret), "reference/notes.md"):
        with pytest.raises(ValidationError):
            load_skill_reference(skill, name)
    assert "SECRET" not in load_skill(skill).body


def test_empty_reference_list_refuses_every_name(tmp_path: Path) -> None:
    skill = _write_skill(
        tmp_path,
        manifest_lines=(
            "when-not-to-use: 'Do not use this: the quoted reason stands alone.'\n"
            "reference-files: []\n"
        ),
    )
    loaded = load_skill(skill)
    assert loaded.manifest.reference_files == ()
    assert loaded.manifest.when_not_to_use == "Do not use this: the quoted reason stands alone."
    with pytest.raises(ValidationError, match="not listed"):
        load_skill_reference(skill, "notes.md")


def test_manifest_rejects_path_names_and_missing_keys(tmp_path: Path) -> None:
    skill = _write_skill(
        tmp_path,
        manifest_lines=(
            "when-not-to-use: Do not use this for unrelated work.\n"
            "reference-files:\n"
            "  - ../secret.md\n"
        ),
    )
    with pytest.raises(ValidationError, match="filename"):
        load_skill(skill)

    missing = _write_skill(
        tmp_path / "missing",
        directory_name="demo-skill",
        manifest_lines="schema_version: 1\n",
    )
    with pytest.raises(ParseError, match="when-not-to-use"):
        load_skill(missing)


def test_frontmatter_and_directory_must_agree(tmp_path: Path) -> None:
    skill = _write_skill(tmp_path, directory_name="other-name")
    with pytest.raises(ParseError, match="does not match"):
        load_skill(skill)
    bare = tmp_path / "bare-skill"
    bare.mkdir()
    (bare / "SKILL.md").write_text("# No frontmatter\n", encoding="utf-8")
    (bare / "manifest.yaml").write_text(
        "when-not-to-use: No.\nreference-files: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ParseError, match="frontmatter"):
        load_skill(bare)


def test_block_scalars_and_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    folded = _write_skill(
        tmp_path,
        skill_text=("---\nname: demo-skill\ndescription: >\n  folded trigger\n---\nBody\n"),
    )
    with pytest.raises(ParseError, match="Block scalars"):
        load_skill(folded)
    duplicate = _write_skill(
        tmp_path / "duplicate",
        directory_name="demo-skill",
        manifest_lines=(
            "when-not-to-use: First reason.\nwhen-not-to-use: Second reason.\nreference-files: []\n"
        ),
    )
    with pytest.raises(ParseError, match="Duplicate"):
        load_skill(duplicate)


def test_direct_manifest_rejects_unsafe_filenames(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Duplicate"):
        SkillManifest(
            name="demo-skill",
            trigger="Use when testing.",
            when_not_to_use="Do not use this in production.",
            reference_files=("notes.md", "notes.md"),
        )
    with pytest.raises(ValidationError, match="filename"):
        SkillManifest(
            name="demo-skill",
            trigger="Use when testing.",
            when_not_to_use="Do not use this in production.",
            reference_files=("../secret.md",),
        )
    with pytest.raises(ArtifactMissingError):
        load_skill_reference(tmp_path / "missing-skill-dir", "notes.md")
