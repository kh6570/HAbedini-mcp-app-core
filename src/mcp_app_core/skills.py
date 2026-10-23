# In the name of God, the Most Gracious, the Most Merciful
"""Skill manifests and on-demand reference files.

A skill directory contains ``SKILL.md`` and ``manifest.yaml``. ``load_skill``
returns the manifest and the short ``SKILL.md`` body. It does not read
``reference/``. ``load_skill_reference`` reads one listed filename from that
directory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mcp_app_core.errors import ArtifactMissingError, ParseError, ValidationError

_SKILL_NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_KEY = re.compile(r"\A[A-Za-z][A-Za-z0-9_-]*\Z")
_REFERENCE_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\.md\Z")
_BLOCK_SCALARS = frozenset({">", "|", ">-", "|-", ">+", "|+"})


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """When a skill applies, and which reference filenames may be opened.

    ``trigger`` comes from the ``SKILL.md`` description. ``when_not_to_use`` and
    ``reference_files`` come from ``manifest.yaml``. Reference names are
    filenames inside the skill's ``reference/`` directory, not paths.
    """

    name: str
    trigger: str
    when_not_to_use: str
    reference_files: tuple[str, ...]

    def __post_init__(self) -> None:
        name = _one_line(self.name, "Skill name")
        trigger = _one_line(self.trigger, "Skill trigger")
        when_not_to_use = _one_line(self.when_not_to_use, "when_not_to_use")
        if not _SKILL_NAME.fullmatch(name):
            raise ValidationError(f"Invalid skill name {self.name!r}.")
        if not isinstance(self.reference_files, tuple):
            raise ValidationError("reference_files must be a tuple of filenames.")
        seen: set[str] = set()
        filenames: list[str] = []
        for item in self.reference_files:
            if not isinstance(item, str):
                raise ValidationError("Reference file names must be strings.")
            filename = item.strip()
            if not _safe_reference_name(filename):
                raise ValidationError(f"Reference file {item!r} must be a filename, not a path.")
            if filename in seen:
                raise ValidationError(f"Duplicate reference file {filename!r}.")
            seen.add(filename)
            filenames.append(filename)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(self, "when_not_to_use", when_not_to_use)
        object.__setattr__(self, "reference_files", tuple(filenames))


@dataclass(frozen=True, slots=True)
class LoadedSkill:
    """Parsed manifest plus the short ``SKILL.md`` body."""

    manifest: SkillManifest
    body: str

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, SkillManifest):
            raise TypeError("Loaded skills contain a SkillManifest.")
        body = self.body.strip("\n")
        if not body.strip():
            raise ValidationError("SKILL.md body must not be empty.")
        object.__setattr__(self, "body", body + "\n")


def load_skill(skill_dir: Path) -> LoadedSkill:
    """Load one skill directory without reading reference file bodies."""

    directory = _skill_directory(skill_dir)
    frontmatter, body = _split_frontmatter(_read_utf8(directory / "SKILL.md", "SKILL.md"))
    name = frontmatter.get("name", "")
    trigger = frontmatter.get("description", "")
    if not name:
        raise ParseError("SKILL.md frontmatter requires name.")
    if not trigger:
        raise ParseError("SKILL.md frontmatter requires description.")
    if directory.name != name.strip():
        raise ParseError(
            f"Skill directory {directory.name!r} does not match frontmatter name {name.strip()!r}."
        )
    scalars, lists = _parse_manifest(_read_utf8(directory / "manifest.yaml", "manifest.yaml"))
    if "when-not-to-use" in lists:
        raise ParseError("when-not-to-use must be a single line.")
    if "when-not-to-use" not in scalars:
        raise ParseError("manifest.yaml requires when-not-to-use.")
    if "reference-files" in scalars:
        raise ParseError("reference-files must be a list of filenames.")
    if "reference-files" not in lists:
        raise ParseError("manifest.yaml requires reference-files.")
    manifest = SkillManifest(
        name=name,
        trigger=trigger,
        when_not_to_use=scalars["when-not-to-use"],
        reference_files=lists["reference-files"],
    )
    return LoadedSkill(manifest=manifest, body=body)


def load_skill_reference(skill_dir: Path, name: str) -> str:
    """Read one reference file whose filename is listed on the manifest.

    Names that are not listed, including paths that leave ``reference/``, are
    refused before the file is opened.
    """

    if not isinstance(name, str):
        raise ValidationError("Reference name must be a string.")
    loaded = load_skill(skill_dir)
    if name not in loaded.manifest.reference_files:
        raise ValidationError(
            f"Reference {name!r} is not listed for skill {loaded.manifest.name!r}."
        )
    directory = _skill_directory(skill_dir)
    root = (directory / "reference").resolve()
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"Reference {name!r} escapes the skill reference directory.") from exc
    if candidate.parent != root or not _safe_reference_name(name):
        raise ValidationError(f"Reference {name!r} escapes the skill reference directory.")
    if not candidate.is_file():
        raise ArtifactMissingError(f"Reference {name!r} was not found.")
    return _read_utf8(candidate, name)


def _skill_directory(skill_dir: Path) -> Path:
    if not isinstance(skill_dir, Path):
        raise ValidationError("Skill directory must be a path.")
    if not skill_dir.is_dir():
        raise ArtifactMissingError("Skill directory was not found.")
    return skill_dir


def _read_utf8(path: Path, label: str) -> str:
    if not path.is_file():
        raise ArtifactMissingError(f"{label} was not found.")
    try:
        return path.read_text(encoding="utf-8").lstrip("\ufeff")
    except UnicodeError as exc:
        raise ParseError(f"Could not read {label} as UTF-8.") from exc
    except OSError as exc:
        raise ParseError(f"Could not read {label}.") from exc


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ParseError("SKILL.md must start with YAML frontmatter.", line=1)
    fields: dict[str, str] = {}
    nested = False
    end: int | None = None
    for line_number, line in enumerate(lines[1:], start=2):
        stripped = line.strip()
        if stripped == "---":
            end = line_number
            break
        if not stripped or stripped.startswith("#"):
            continue
        if line[0] in " \t":
            if not nested:
                raise ParseError("Frontmatter indent is outside a block.", line=line_number)
            _, value = _key_value(stripped, line_number=line_number)
            if not value:
                raise ParseError("Nested frontmatter must be a key and a value.", line=line_number)
            continue
        nested = False
        key, value = _key_value(line, line_number=line_number)
        if key in fields:
            raise ParseError(f"Duplicate frontmatter key {key!r}.", line=line_number)
        if value in _BLOCK_SCALARS:
            raise ParseError("Block scalars are not supported.", line=line_number)
        if not value:
            nested = True
            continue
        if value.startswith(("[", "{")):
            raise ParseError("Inline collections are not supported.", line=line_number)
        fields[key] = _unquote(value)
    if end is None:
        raise ParseError("SKILL.md frontmatter is not closed.")
    return fields, "\n".join(lines[end:])


def _parse_manifest(text: str) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current: str | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[0] in " \t":
            if current is None or not stripped.startswith("- "):
                raise ParseError("Manifest list item is outside a list.", line=line_number)
            item = _unquote(stripped[2:].strip())
            if not item:
                raise ParseError("Manifest list item is empty.", line=line_number)
            lists[current].append(item)
            continue
        current = None
        key, value = _key_value(line, line_number=line_number)
        if key in scalars or key in lists:
            raise ParseError(f"Duplicate manifest key {key!r}.", line=line_number)
        if value in _BLOCK_SCALARS:
            raise ParseError("Block scalars are not supported.", line=line_number)
        if value == "[]":
            lists[key] = []
            continue
        if value.startswith(("[", "{")):
            raise ParseError("Inline collections are not supported.", line=line_number)
        if not value:
            current = key
            lists[key] = []
            continue
        scalars[key] = _unquote(value)
    return scalars, {key: tuple(items) for key, items in lists.items()}


def _key_value(line: str, *, line_number: int) -> tuple[str, str]:
    key, separator, value = line.partition(":")
    if not separator:
        raise ParseError("Expected a key and a value.", line=line_number)
    parsed_key = key.strip()
    if not _KEY.fullmatch(parsed_key):
        raise ParseError(f"Invalid key {parsed_key!r}.", line=line_number)
    return parsed_key, value.strip()


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value.strip()


def _one_line(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string.")
    text = value.strip()
    if not text or any(ord(char) < 32 for char in text):
        raise ValidationError(f"{label} must be one non-empty line.")
    return text


def _safe_reference_name(name: str) -> bool:
    return ".." not in name and _REFERENCE_NAME.fullmatch(name) is not None


__all__ = [
    "LoadedSkill",
    "SkillManifest",
    "load_skill",
    "load_skill_reference",
]
