"""Treatment-only Copilot skill staging and discovery checks."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SKILL_DESTINATION_ROOT = Path(".github/skills")
SECTION_PATTERN = re.compile(r"^([A-Za-z][A-Za-z ]+) skills:$")
ENTRY_PATTERN = re.compile(r"^\s{2}([^\s]+)\s+-\s+")
NAME_PATTERN = re.compile(r"^name:\s*[\"']?([^\"'\s]+)[\"']?\s*$", re.MULTILINE)


class SkillConfigurationError(RuntimeError):
    """Raised when treatment skill configuration or discovery is invalid."""


def read_skill_name(source: Path) -> str:
    skill_file = source / "SKILL.md"
    if not source.is_dir() or not skill_file.is_file():
        raise SkillConfigurationError(
            "Graphify skill source must be a directory containing SKILL.md: %s"
            % source
        )
    text = skill_file.read_text(encoding="utf-8")
    match = NAME_PATTERN.search(text)
    if not match:
        raise SkillConfigurationError("Graphify skill SKILL.md has no frontmatter name")
    name = match.group(1)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise SkillConfigurationError("Graphify skill name is not path-safe: %r" % name)
    return name


def resolve_skill_source(
    configured_source: Optional[str],
    config_base: Path,
) -> Optional[Tuple[Path, str]]:
    if configured_source is None:
        return None
    if not isinstance(configured_source, str) or not configured_source.strip():
        raise SkillConfigurationError(
            "graphify_skill_source must be null or a non-empty directory path"
        )
    source = Path(configured_source).expanduser()
    if not source.is_absolute():
        source = config_base / source
    source = source.resolve()
    return source, read_skill_name(source)


def skill_destination(skill_name: str) -> Path:
    return SKILL_DESTINATION_ROOT / skill_name


def stage_skill(source: Path, worktree: Path, skill_name: str) -> Path:
    destination = worktree / skill_destination(skill_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SkillConfigurationError(
            "Treatment skill destination was not isolated before staging: %s"
            % destination
        )
    shutil.copytree(str(source), str(destination))
    return destination


def parse_skill_list(output: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = None
    for line in output.splitlines():
        section = SECTION_PATTERN.match(line.strip())
        if section:
            current = section.group(1).lower().replace(" ", "_")
            sections.setdefault(current, [])
            continue
        entry = ENTRY_PATTERN.match(line)
        if current and entry:
            sections[current].append(entry.group(1))
    return sections


def inspect_skill_discovery(
    copilot_command: str,
    worktree: Path,
    skill_name: str,
) -> Dict[str, Any]:
    completed = subprocess.run(
        [
            copilot_command,
            "-C",
            str(worktree),
            "--no-color",
            "--no-auto-update",
            "skill",
            "list",
        ],
        cwd=str(worktree),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=False,
        errors="replace",
    )
    output = completed.stdout
    sections = parse_skill_list(output)
    matching_sections = sorted(
        section for section, names in sections.items() if skill_name in names
    )
    return {
        "command_exit_code": completed.returncode,
        "stdout": output,
        "stderr": completed.stderr,
        "sections": sections,
        "matching_sections": matching_sections,
        "project_discovered": skill_name in sections.get("project", []),
        "non_project_matches": [
            section for section in matching_sections if section != "project"
        ],
    }


def validate_skill_condition(
    condition: str,
    configured: bool,
    staged: bool,
    discovery: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    if not configured:
        return True, None
    if discovery is None:
        return False, "Graphify skill discovery was not inspected"
    if discovery["command_exit_code"] != 0:
        return False, "Copilot skill discovery failed"
    if discovery["non_project_matches"]:
        return (
            False,
            "Graphify skill contamination detected in non-project sources: %s"
            % ", ".join(discovery["non_project_matches"]),
        )
    if condition == "graphify_on":
        if not staged:
            return False, "Graphify treatment skill was not staged"
        if not discovery["project_discovered"]:
            return False, "Graphify treatment skill was not discovered as a project skill"
        return True, None
    if staged or discovery["project_discovered"]:
        return False, "Graphify skill was present in the control condition"
    return True, None
