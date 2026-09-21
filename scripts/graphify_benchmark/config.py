"""Configuration loading, creation, and environment validation."""

import copy
import hashlib
import json
import random
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .skills import SkillConfigurationError, resolve_skill_source


CONFIG_FILENAME = ".graphify-benchmark.json"
TREATMENT_MODES = ("mcp_only", "skill_and_mcp", "forced_graphify_skill_cli")
DEFAULT_FORCED_GRAPHIFY_DIRECTIVE = (
    "You must use the Graphify skill and run Graphify CLI queries before using "
    "grep, find, glob, or reading source files. Use Graphify to identify the "
    "relevant symbols, relationships, and files, then verify them in source."
)

DEFAULT_METRICS = {
    "graphify_tool_name_patterns": ["(?i)graphify"],
    "known_graphify_tool_names": [],
    "search_tool_name_patterns": ["(?i)(search|grep|ripgrep|rg|glob|find)"],
    "read_tool_name_patterns": ["(?i)(read|view|get_file|file_content|cat)"],
    "shell_tool_name_patterns": ["(?i)(bash|shell|terminal|powershell|pwsh|cmd)"],
    "shell_read_command_patterns": [
        r"(?i)(?:^|[;&|]\s*)(?:cat|head|tail|less|more|sed|awk)\b"
    ],
    "targeted_argument_patterns": [
        r"(?:src|test|tests|docs|scripts)/[A-Za-z0-9_./-]+",
        r"\b[A-Z][A-Za-z0-9_]{3,}\b",
        r"\b[A-Za-z_][A-Za-z0-9_]*\.(?:java|py|js|ts|tsx|go|rs|cs|cpp|c|h|md|json|xml|yml|yaml)\b",
    ],
    "broad_argument_patterns": [
        r"\*\*",
        r"(?i)\b(entire|everything|all files|whole repository|codebase)\b",
        r'(?i)"(?:path|paths|directory)"\s*:\s*"[./]*"',
    ],
    "graphify_follow_up_window": 4,
}


class ConfigurationError(RuntimeError):
    """Raised when configuration or prerequisites are invalid."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(
    args: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def git_root(start: Path) -> Path:
    result = run_checked(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if result.returncode != 0:
        raise ConfigurationError(
            "Run the harness from inside the repository: "
            + (result.stderr.strip() or "git root not found")
        )
    return Path(result.stdout.strip()).resolve()


def resolve_git_ref(repo_root: Path, ref: str) -> str:
    result = run_checked(["git", "rev-parse", "--verify", "%s^{commit}" % ref], cwd=repo_root)
    if result.returncode != 0:
        raise ConfigurationError(
            "Repository ref %r does not resolve to a commit: %s"
            % (ref, result.stderr.strip())
        )
    return result.stdout.strip()


def list_mcp_servers(
    copilot_command: str = "copilot",
    cwd: Optional[Path] = None,
) -> str:
    result = run_checked([copilot_command, "mcp", "list"], cwd=cwd)
    if result.returncode != 0:
        raise ConfigurationError(
            "Unable to list Copilot MCP servers: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    return result.stdout


def require_mcp_server(
    server_name: str,
    copilot_command: str = "copilot",
    cwd: Optional[Path] = None,
) -> str:
    result = run_checked([copilot_command, "mcp", "get", server_name], cwd=cwd)
    if result.returncode != 0:
        available = ""
        try:
            available = "\n\nConfigured servers:\n" + list_mcp_servers(
                copilot_command, cwd=cwd
            )
        except ConfigurationError:
            pass
        raise ConfigurationError(
            "Graphify treatment server %r is not available to Copilot CLI. "
            "Use `python3 scripts/graphify_benchmark.py list-servers`, then rerun "
            "`configure` with the exact server name.%s"
            % (server_name, available)
        )
    return result.stdout


def copilot_version(copilot_command: str = "copilot") -> str:
    result = run_checked([copilot_command, "--version"])
    if result.returncode != 0:
        return "unknown"
    return (result.stdout or result.stderr).strip() or "unknown"


def create_config(
    repo_root: Path,
    graphify_server: Optional[str],
    model: str,
    reasoning_effort: str,
    repetitions: int,
    tasks_dir: str,
    results_dir: str,
    repo_ref: str,
    seed: int,
    copilot_command: str = "copilot",
    graphify_skill_source: Optional[str] = None,
    treatment_mode: Optional[str] = None,
    graphify_graph_source: Optional[str] = None,
    graphify_graph_build_duration_seconds: Optional[float] = None,
    graphify_graph_build_cost_usd: Optional[float] = None,
    forced_graphify_directive: str = DEFAULT_FORCED_GRAPHIFY_DIRECTIVE,
) -> Dict[str, Any]:
    commit = resolve_git_ref(repo_root, repo_ref)
    metrics = copy.deepcopy(DEFAULT_METRICS)
    if graphify_server:
        server_pattern = "(?i)%s" % re.escape(graphify_server)
        if server_pattern not in metrics["graphify_tool_name_patterns"]:
            metrics["graphify_tool_name_patterns"].insert(0, server_pattern)
    if treatment_mode is None:
        treatment_mode = "skill_and_mcp" if graphify_skill_source else "mcp_only"
    return {
        "schema_version": 1,
        "treatment_mode": treatment_mode,
        "graphify_server": graphify_server,
        "graphify_skill_source": graphify_skill_source,
        "graphify_graph_source": graphify_graph_source,
        "graphify_graph_build_duration_seconds": graphify_graph_build_duration_seconds,
        "graphify_graph_build_cost_usd": graphify_graph_build_cost_usd,
        "forced_graphify_directive": forced_graphify_directive,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "repetitions": repetitions,
        "seed": seed,
        "repo_root": str(repo_root),
        "repo_ref": commit,
        "copilot_version": copilot_version(copilot_command),
        "tasks_dir": tasks_dir,
        "results_dir": results_dir,
        "worktree_exclude_paths": [
            "graphify-out",
            ".copilot/skills/graphify",
        ],
        "copilot_command": copilot_command,
        "copilot_extra_args": [],
        "run_timeout_seconds": 1800,
        "validation_timeout_seconds": 300,
        "score_tie_tolerance": 0.01,
        "metrics": metrics,
        "otel": {
            "enabled": False,
            "capture_message_content": False,
        },
    }


def write_config(path: Path, config: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def load_config(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigurationError(
            "Configuration not found at %s. Run the `configure` command first." % path
        )
    except json.JSONDecodeError as error:
        raise ConfigurationError("Invalid JSON in %s: %s" % (path, error))
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration root must be a JSON object")
    return data


def _require_nonempty_string(config: Dict[str, Any], key: str) -> None:
    if not isinstance(config.get(key), str) or not config[key].strip():
        raise ConfigurationError("Configuration field %r must be a non-empty string" % key)


def _validate_patterns(patterns: Iterable[str], field: str) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as error:
            raise ConfigurationError("Invalid regex in %s: %s" % (field, error))


def validate_config(
    config: Dict[str, Any],
    config_path: Path,
    check_environment: bool = True,
) -> Tuple[Path, Path, Path]:
    for key in (
        "model",
        "reasoning_effort",
        "repo_root",
        "repo_ref",
        "tasks_dir",
        "results_dir",
        "copilot_command",
    ):
        _require_nonempty_string(config, key)
    treatment_mode = config.get("treatment_mode")
    if treatment_mode is None:
        treatment_mode = (
            "skill_and_mcp"
            if config.get("graphify_skill_source")
            else "mcp_only"
        )
        config["treatment_mode"] = treatment_mode
    if treatment_mode not in TREATMENT_MODES:
        raise ConfigurationError(
            "treatment_mode must be one of: %s" % ", ".join(TREATMENT_MODES)
        )
    if treatment_mode != "forced_graphify_skill_cli":
        _require_nonempty_string(config, "graphify_server")
    elif config.get("graphify_server") is not None and (
        not isinstance(config["graphify_server"], str)
        or not config["graphify_server"].strip()
    ):
        raise ConfigurationError(
            "graphify_server must be null or a non-empty disabled server name "
            "in forced_graphify_skill_cli mode"
        )

    repetitions = config.get("repetitions")
    if not isinstance(repetitions, int) or repetitions < 1:
        raise ConfigurationError("Configuration field 'repetitions' must be at least 1")
    if treatment_mode == "forced_graphify_skill_cli" and repetitions != 1:
        raise ConfigurationError(
            "forced_graphify_skill_cli mode requires repetitions=1 because it runs one "
            "control phase followed by one treatment phase"
        )
    seed = config.get("seed")
    if not isinstance(seed, int):
        raise ConfigurationError("Configuration field 'seed' must be an integer")

    metrics = config.get("metrics")
    if not isinstance(metrics, dict):
        raise ConfigurationError("Configuration field 'metrics' must be an object")
    for field in (
        "graphify_tool_name_patterns",
        "search_tool_name_patterns",
        "read_tool_name_patterns",
        "shell_tool_name_patterns",
        "shell_read_command_patterns",
        "targeted_argument_patterns",
        "broad_argument_patterns",
    ):
        value = metrics.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConfigurationError("metrics.%s must be an array of strings" % field)
        _validate_patterns(value, "metrics.%s" % field)
    exclude_paths = config.get("worktree_exclude_paths", [])
    if not isinstance(exclude_paths, list) or not all(
        isinstance(item, str) and item.strip() for item in exclude_paths
    ):
        raise ConfigurationError(
            "worktree_exclude_paths must be an array of non-empty relative paths"
        )
    for relative_path in exclude_paths:
        if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            raise ConfigurationError(
                "worktree_exclude_paths must stay inside the benchmark worktree: %s"
                % relative_path
            )

    base = config_path.parent.resolve()
    repo_root = (base / config["repo_root"]).resolve()
    tasks_dir = (repo_root / config["tasks_dir"]).resolve()
    results_dir = (repo_root / config["results_dir"]).resolve()
    try:
        skill = resolve_skill_source(config.get("graphify_skill_source"), base)
    except SkillConfigurationError as error:
        raise ConfigurationError(str(error))
    if skill:
        skill_source, skill_name = skill
        config["_resolved_graphify_skill_source"] = str(skill_source)
        config["_graphify_skill_name"] = skill_name
    if treatment_mode in ("skill_and_mcp", "forced_graphify_skill_cli") and not skill:
        raise ConfigurationError(
            "%s mode requires graphify_skill_source" % treatment_mode
        )
    graph_source_value = config.get("graphify_graph_source")
    if treatment_mode == "forced_graphify_skill_cli":
        _require_nonempty_string(config, "forced_graphify_directive")
        if not isinstance(graph_source_value, str) or not graph_source_value.strip():
            raise ConfigurationError(
                "forced_graphify_skill_cli mode requires graphify_graph_source"
            )
        graph_source = Path(graph_source_value).expanduser()
        if not graph_source.is_absolute():
            graph_source = base / graph_source
        graph_source = graph_source.resolve()
        if not graph_source.is_file():
            raise ConfigurationError(
                "Graphify graph source does not exist: %s" % graph_source
            )
        config["_resolved_graphify_graph_source"] = str(graph_source)
        config["_graphify_graph_sha256"] = file_sha256(graph_source)
        config["_graphify_graph_size_bytes"] = graph_source.stat().st_size
        build_duration = config.get("graphify_graph_build_duration_seconds")
        if build_duration is not None and (
            not isinstance(build_duration, (int, float)) or build_duration < 0
        ):
            raise ConfigurationError(
                "graphify_graph_build_duration_seconds must be null or non-negative"
            )
        build_cost = config.get("graphify_graph_build_cost_usd")
        if build_cost is not None and (
            not isinstance(build_cost, (int, float)) or build_cost < 0
        ):
            raise ConfigurationError(
                "graphify_graph_build_cost_usd must be null or non-negative"
            )
    if not (repo_root / ".git").exists() and not (repo_root / ".git").is_file():
        raise ConfigurationError("Configured repo_root is not a Git worktree: %s" % repo_root)
    if not tasks_dir.is_dir():
        raise ConfigurationError("Configured tasks_dir does not exist: %s" % tasks_dir)
    resolve_git_ref(repo_root, config["repo_ref"])

    if check_environment:
        copilot_command = config["copilot_command"]
        if shutil.which(copilot_command) is None:
            raise ConfigurationError(
                "Copilot CLI command %r was not found on PATH" % copilot_command
            )
        if treatment_mode != "forced_graphify_skill_cli":
            require_mcp_server(
                config["graphify_server"], copilot_command, cwd=repo_root
            )
        current_version = copilot_version(copilot_command)
        recorded_version = config.get("copilot_version")
        if recorded_version and current_version != recorded_version:
            raise ConfigurationError(
                "Copilot CLI version changed from configured %r to %r. "
                "Rerun `configure --force` before benchmarking."
                % (recorded_version, current_version)
            )

    return repo_root, tasks_dir, results_dir


def balanced_plan(
    task_ids: Iterable[str],
    repetitions: int,
    seed: int,
) -> List[Dict[str, Any]]:
    randomizer = random.Random(seed)
    task_ids = list(task_ids)
    extra_on_first = randomizer.choice([True, False])
    on_first_count = len(task_ids) // 2
    if len(task_ids) % 2 and extra_on_first:
        on_first_count += 1
    starts = ["graphify_on"] * on_first_count
    starts.extend(["graphify_off"] * (len(task_ids) - on_first_count))
    randomizer.shuffle(starts)

    plan = []
    for task_id, initial_condition in zip(task_ids, starts):
        for repetition in range(1, repetitions + 1):
            first_condition = initial_condition
            if repetition % 2 == 0:
                first_condition = (
                    "graphify_off"
                    if initial_condition == "graphify_on"
                    else "graphify_on"
                )
            second_condition = (
                "graphify_off"
                if first_condition == "graphify_on"
                else "graphify_on"
            )
            pair_id = "%s-r%02d" % (task_id, repetition)
            for position, condition in enumerate(
                [first_condition, second_condition], start=1
            ):
                plan.append(
                    {
                        "task_id": task_id,
                        "repetition": repetition,
                        "pair_id": pair_id,
                        "position": position,
                        "condition": condition,
                    }
                )
    return plan


def forced_graphify_skill_cli_plan(
    task_ids: Iterable[str],
) -> List[Dict[str, Any]]:
    task_ids = list(task_ids)
    plan = []
    for condition in ("graphify_off", "graphify_on"):
        for task_id in task_ids:
            pair_id = "%s-r01" % task_id
            plan.append(
                {
                    "task_id": task_id,
                    "repetition": 1,
                    "pair_id": pair_id,
                    "position": 1 if condition == "graphify_off" else 2,
                    "condition": condition,
                }
            )
    return plan
