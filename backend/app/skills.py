"""Agent Skills — discover and serve SKILL.md files from the filesystem.

A skill is a directory containing a single `SKILL.md` file whose YAML frontmatter
declares `name` and `description`. The markdown body (after the frontmatter) is
loaded on demand by the `load_skill` agent tool.

Default discovery root: `<backend-cwd>/.abletonagent/skills/`
"""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator

from .logger import logger

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_CONSECUTIVE_HYPHENS = re.compile(r"--")


class Skill(BaseModel):
    name: str
    description: str
    path: Path  # absolute path to SKILL.md

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) > 64:
            raise ValueError("name must be ≤ 64 characters")
        if not _NAME_RE.match(v):
            raise ValueError(
                "name must match ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ (lowercase, digits, hyphens)"
            )
        if _CONSECUTIVE_HYPHENS.search(v):
            raise ValueError("name must not contain consecutive hyphens")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description must not be empty")
        if len(v) > 1024:
            raise ValueError("description must be ≤ 1024 characters")
        return v

    @model_validator(mode="after")
    def check_dir_name(self) -> "Skill":
        parent_name = self.path.parent.name
        if parent_name != self.name:
            logger.warning(
                f"Skill name '{self.name}' does not match its parent directory '{parent_name}' "
                f"({self.path}). Loading anyway."
            )
        return self


# ---------------------------------------------------------------------------
# YAML frontmatter parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_text). Body is the content after the closing ---."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw_yaml = match.group(1)
    body = text[match.end():]
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        # Fallback: wrap bare colon values in quotes and retry once.
        fixed = re.sub(r"^(\s*\w+:\s*)(.+)$", r'\1"\2"', raw_yaml, flags=re.MULTILINE)
        try:
            data = yaml.safe_load(fixed)
        except yaml.YAMLError:
            return {}, body
    return data if isinstance(data, dict) else {}, body


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class SkillRegistry:
    def __init__(self, skills: list[Skill]) -> None:
        # First-discovered wins; dict preserves insertion order for catalog display.
        self._skills: dict[str, Skill] = {s.name: s for s in skills}

    @classmethod
    def discover(cls, dirs: list[Path]) -> "SkillRegistry":
        """Scan each directory in *dirs* for `<name>/SKILL.md` entries.

        First discovered wins on name collision; later duplicates are warned and skipped.
        """
        seen: dict[str, Path] = {}  # name → first source dir
        skills: list[Skill] = []

        for base in dirs:
            if not base.is_dir():
                continue
            for skill_dir in sorted(base.iterdir()):
                skill_file = skill_dir / "SKILL.md"
                if not skill_dir.is_dir() or not skill_file.is_file():
                    continue

                try:
                    text = skill_file.read_text(encoding="utf-8")
                except OSError as e:
                    logger.warning(f"Skills: cannot read {skill_file}: {e}")
                    continue

                frontmatter, _ = _parse_frontmatter(text)
                if not frontmatter:
                    logger.warning(
                        f"Skills: {skill_file} has no parseable frontmatter — skipping"
                    )
                    continue

                try:
                    skill = Skill.model_validate(
                        {
                            "name": frontmatter.get("name", ""),
                            "description": frontmatter.get("description", ""),
                            "path": skill_file,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Skills: {skill_file} failed validation — skipping: {e}")
                    continue

                if skill.name in seen:
                    logger.warning(
                        f"Skills: '{skill.name}' already loaded from {seen[skill.name]}; "
                        f"shadowing entry at {skill_file} — skipping"
                    )
                    continue

                seen[skill.name] = base
                skills.append(skill)
                logger.info(f"Skills: loaded '{skill.name}' from {skill_file}")

        return cls(skills)

    # ------------------------------------------------------------------
    # Public API used by agent.py
    # ------------------------------------------------------------------

    def catalog_text(self) -> str:
        """Return the Skills section for the system prompt, or '' if none are loaded."""
        if not self._skills:
            return ""
        header = (
            "---\n\n"
            "## Skills\n\n"
            "The following skills are available. When a task matches a skill's description, "
            "call `load_skill` with the skill name to load its full instructions before proceeding.\n\n"
        )
        entries = "\n".join(
            f"- **{s.name}**: {s.description}" for s in self._skills.values()
        )
        return header + entries

    def load_body(self, name: str) -> str:
        """Read SKILL.md, strip frontmatter, return the markdown body.

        Returns an error string if *name* is unknown (same convention as other tools).
        """
        skill = self._skills.get(name)
        if skill is None:
            available = ", ".join(self._skills) or "none"
            return f"Error: skill '{name}' not found. Available skills: {available}"
        try:
            text = skill.path.read_text(encoding="utf-8")
        except OSError as e:
            return f"Error: could not read skill '{name}': {e}"
        _, body = _parse_frontmatter(text)
        return body.strip()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_skill_registry() -> SkillRegistry:
    dirs = [Path.cwd() / ".abletonagent" / "skills"]
    return SkillRegistry.discover(dirs)
