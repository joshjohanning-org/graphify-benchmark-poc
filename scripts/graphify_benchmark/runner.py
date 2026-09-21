"""Paired clean-worktree benchmark execution."""

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import balanced_plan, file_sha256, forced_graphify_skill_cli_plan
from .events import calculate_metrics, extract_final_answer, load_events
from .grading import grade_task, validate_task
from .report import build_report, write_csv, write_json, write_markdown
from .skills import (
    inspect_skill_discovery,
    skill_destination,
    stage_skill,
    validate_skill_condition,
)


class BenchmarkRunError(RuntimeError):
    """Raised when the harness cannot safely execute a benchmark."""


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _run_capture(
    args: List[str],
    cwd: Path,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        errors="replace",
    )


def _is_injected_path(relative_path: str, excluded_paths: List[str]) -> bool:
    path = Path(relative_path)
    return any(path == Path(item) or Path(item) in path.parents for item in excluded_paths)


def _append_untracked_diffs(
    worktree_path: Path,
    tracked_diff: str,
    excluded_paths: Optional[List[str]] = None,
) -> str:
    untracked = _run_capture(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=worktree_path,
    )
    if untracked.returncode != 0 or not untracked.stdout:
        return tracked_diff
    parts = [tracked_diff]
    excluded_paths = excluded_paths or []
    for relative_path in untracked.stdout.split("\0"):
        if not relative_path:
            continue
        if _is_injected_path(relative_path, excluded_paths):
            continue
        path = worktree_path / relative_path
        if not path.is_file():
            continue
        diff = _run_capture(
            ["git", "--no-pager", "diff", "--no-index", "--", "/dev/null", relative_path],
            cwd=worktree_path,
        )
        parts.append(diff.stdout)
    return "".join(parts)


def _filtered_status(status: str, excluded_paths: List[str]) -> str:
    lines = []
    for line in status.splitlines():
        relative_path = line[3:].strip()
        if " -> " in relative_path:
            relative_path = relative_path.rsplit(" -> ", 1)[1]
        if not _is_injected_path(relative_path, excluded_paths):
            lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def load_tasks(tasks_dir: Path) -> List[Dict[str, Any]]:
    tasks = []
    ids = set()
    for path in sorted(tasks_dir.glob("*.json")):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise BenchmarkRunError("Invalid task JSON %s: %s" % (path, error))
        validate_task(task, str(path))
        if task["id"] in ids:
            raise BenchmarkRunError("Duplicate task id %r" % task["id"])
        task["_source_path"] = str(path)
        ids.add(task["id"])
        tasks.append(task)
    if not tasks:
        raise BenchmarkRunError("No task JSON files found in %s" % tasks_dir)
    return tasks


def choose_pilot_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected = []
    seen_categories = set()
    for task in tasks:
        if task["category"] not in seen_categories:
            selected.append(task)
            seen_categories.add(task["category"])
    return selected


def _remove_excluded_paths(worktree_path: Path, paths: List[str]) -> List[str]:
    removed = []
    worktree_resolved = worktree_path.resolve()
    for relative_path in paths:
        target = (worktree_path / relative_path).resolve()
        if worktree_resolved not in target.parents:
            raise BenchmarkRunError(
                "Excluded path escapes benchmark worktree: %s" % relative_path
            )
        tracked = _run_capture(
            ["git", "ls-files", "--", relative_path],
            cwd=worktree_path,
        )
        if tracked.returncode != 0:
            raise BenchmarkRunError(
                "Unable to inspect excluded worktree path %s: %s"
                % (relative_path, tracked.stderr.strip())
            )
        tracked_files = [line for line in tracked.stdout.splitlines() if line]
        if tracked_files:
            skipped = _run_capture(
                ["git", "update-index", "--skip-worktree", "--"] + tracked_files,
                cwd=worktree_path,
            )
            if skipped.returncode != 0:
                raise BenchmarkRunError(
                    "Unable to isolate excluded worktree path %s: %s"
                    % (relative_path, skipped.stderr.strip())
                )
        if target.is_dir():
            shutil.rmtree(str(target))
            removed.append(relative_path)
        elif target.exists():
            target.unlink()
            removed.append(relative_path)
    return removed


def _condition_validity(
    condition: str,
    statuses: List[str],
    graphify_invocations: int,
) -> Tuple[bool, Optional[str]]:
    final_status = statuses[-1].lower() if statuses else None
    if condition == "graphify_on":
        if final_status != "connected":
            return False, "Graphify treatment did not finish with connected MCP status"
        return True, None
    if graphify_invocations:
        return False, "Graphify tool was invoked in the disabled control condition"
    if final_status not in (None, "disabled"):
        return False, "Graphify control condition ended with MCP status %r" % final_status
    return True, None


def _prepare_skill_condition(
    config: Dict[str, Any],
    worktree_path: Path,
    condition: str,
) -> Tuple[List[str], Dict[str, Any]]:
    skill_name = config.get("_graphify_skill_name")
    skill_source_value = config.get("_resolved_graphify_skill_source")
    configured = bool(skill_name and skill_source_value)
    excluded_paths = list(config.get("worktree_exclude_paths", []))
    if configured:
        destination = str(skill_destination(skill_name))
        if destination not in excluded_paths:
            excluded_paths.append(destination)
    removed = _remove_excluded_paths(worktree_path, excluded_paths)

    staged = False
    destination_path = None
    discovery = None
    if configured and condition == "graphify_on":
        destination_path = stage_skill(
            Path(skill_source_value), worktree_path, skill_name
        )
        staged = True
    if configured:
        discovery = inspect_skill_discovery(
            config["copilot_command"], worktree_path, skill_name
        )
    valid, invalid_reason = validate_skill_condition(
        condition, configured, staged, discovery
    )
    status = {
        "configured": configured,
        "skill_name": skill_name,
        "source": skill_source_value,
        "destination": str(destination_path) if destination_path else None,
        "staged": staged,
        "loaded": discovery["project_discovered"] if discovery else None,
        "runtime_loaded": None,
        "runtime_loaded_note": (
            "Copilot skill list confirms discovery before the run; runtime skill "
            "selection is not observable without a prompted model session."
            if configured
            else None
        ),
        "discovery_sections": discovery["sections"] if discovery else {},
        "matching_sections": discovery["matching_sections"] if discovery else [],
        "non_project_matches": (
            discovery["non_project_matches"] if discovery else []
        ),
        "skill_list_exit_code": (
            discovery["command_exit_code"] if discovery else None
        ),
        "valid": valid,
        "invalid_reason": invalid_reason,
    }
    if discovery:
        status["_skill_list_stdout"] = discovery["stdout"]
        status["_skill_list_stderr"] = discovery["stderr"]
    return removed, status


def _prepare_graph_condition(
    config: Dict[str, Any],
    worktree_path: Path,
    condition: str,
) -> Dict[str, Any]:
    configured = config.get("treatment_mode") == "forced_graphify_skill_cli"
    destination = worktree_path / "graphify-out" / "graph.json"
    source_value = config.get("_resolved_graphify_graph_source")
    staged = False
    source_sha256 = config.get("_graphify_graph_sha256")
    destination_sha256 = None
    read_only = False
    if configured and condition == "graphify_on":
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_value, str(destination))
        destination_sha256 = file_sha256(destination)
        if destination_sha256 != source_sha256:
            raise BenchmarkRunError("Staged Graphify graph SHA-256 does not match source")
        destination.chmod(0o444)
        read_only = destination.stat().st_mode & 0o222 == 0
        if not read_only:
            raise BenchmarkRunError("Staged Graphify graph is not read-only")
        staged = True
    present = destination.exists()
    valid = (
        not configured
        or (condition == "graphify_on" and staged and present and read_only)
        or (condition == "graphify_off" and not present)
    )
    return {
        "configured": configured,
        "source": source_value,
        "destination": "graphify-out/graph.json",
        "source_sha256": source_sha256,
        "destination_sha256": destination_sha256,
        "size_bytes": config.get("_graphify_graph_size_bytes"),
        "build_duration_seconds": config.get(
            "graphify_graph_build_duration_seconds"
        ),
        "build_cost_usd": config.get("graphify_graph_build_cost_usd"),
        "staged": staged,
        "present": present,
        "read_only": read_only if present else None,
        "valid": valid,
        "invalid_reason": (
            None
            if valid
            else "Treatment graph staging failed"
            if condition == "graphify_on"
            else "Control worktree contains Graphify graph"
        ),
    }


def _skill_status_for_artifact(status: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in status.items() if not key.startswith("_")}


def _merge_condition_validity(
    mcp_valid: bool,
    mcp_reason: Optional[str],
    skill_status: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    if not mcp_valid:
        return False, mcp_reason
    if not skill_status["valid"]:
        return False, skill_status["invalid_reason"]
    return True, None


def _forced_condition_validity(
    condition: str,
    skill_status: Dict[str, Any],
    graph_status: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    if not skill_status["valid"]:
        return False, skill_status["invalid_reason"]
    if not graph_status["valid"]:
        return False, graph_status["invalid_reason"]
    connected_mcp_events = [
        event
        for event in metrics["graphify_mcp_events"]
        if str(event.get("status", "")).lower() not in ("", "disabled")
    ]
    if metrics["graphify_invocation_count"] or connected_mcp_events:
        return False, (
            "Graphify MCP connected or was invoked in forced_graphify_skill_cli mode"
        )
    cli_count = metrics["graphify_cli_invocation_count"]
    cli_success = metrics["graphify_cli_success_count"]
    if condition == "graphify_on":
        if cli_count == 0 or cli_success == 0:
            return False, "Treatment did not successfully invoke Graphify CLI"
    elif cli_count:
        return False, "Control invoked Graphify CLI"
    return True, None


def _effective_prompt(
    config: Dict[str, Any],
    condition: str,
    base_prompt: str,
) -> Tuple[str, bool]:
    if (
        config.get("treatment_mode") != "forced_graphify_skill_cli"
        or condition != "graphify_on"
    ):
        return base_prompt, False
    return config["forced_graphify_directive"].strip() + "\n\n" + base_prompt, True


def _graphify_mcp_args(config: Dict[str, Any], condition: str) -> List[str]:
    server = config.get("graphify_server")
    if config.get("treatment_mode") == "forced_graphify_skill_cli":
        return ["--disable-mcp-server", server] if server else []
    option = "--enable-mcp-server" if condition == "graphify_on" else "--disable-mcp-server"
    return [option, server]


class BenchmarkRunner:
    def __init__(
        self,
        config: Dict[str, Any],
        repo_root: Path,
        tasks_dir: Path,
        results_dir: Path,
    ) -> None:
        self.config = config
        self.repo_root = repo_root
        self.tasks_dir = tasks_dir
        self.results_dir = results_dir

    def run(
        self,
        pilot: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Path:
        tasks = load_tasks(self.tasks_dir)
        if task_ids:
            requested = set(task_ids)
            tasks = [task for task in tasks if task["id"] in requested]
            missing = sorted(requested - set(task["id"] for task in tasks))
            if missing:
                raise BenchmarkRunError("Unknown task ids: %s" % ", ".join(missing))
        if pilot:
            tasks = choose_pilot_tasks(tasks)
        repetitions = 1 if pilot else int(self.config["repetitions"])

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_root = self.results_dir / timestamp
        suffix = 1
        while run_root.exists():
            run_root = self.results_dir / ("%s-%d" % (timestamp, suffix))
            suffix += 1
        run_root.mkdir(parents=True)

        task_by_id = {task["id"]: task for task in tasks}
        treatment_mode = self.config.get("treatment_mode", "mcp_only")
        plan = (
            forced_graphify_skill_cli_plan(task_by_id)
            if treatment_mode == "forced_graphify_skill_cli"
            else balanced_plan(task_by_id, repetitions, int(self.config["seed"]))
        )
        order_limitation = (
            "All controls run first in task-file order, followed by all "
            "Graphify treatments in task-file order. This phase order is not "
            "counterbalanced and may confound condition with time/order."
            if treatment_mode == "forced_graphify_skill_cli"
            else None
        )
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repo_ref": self.config["repo_ref"],
            "model": self.config["model"],
            "reasoning_effort": self.config["reasoning_effort"],
            "graphify_server": self.config.get("graphify_server"),
            "treatment_mode": treatment_mode,
            "forced_graphify_directive": self.config.get(
                "forced_graphify_directive"
            )
            if treatment_mode == "forced_graphify_skill_cli"
            else None,
            "order_limitation": order_limitation,
            "graphify_graph_setup": {
                "source": self.config.get("_resolved_graphify_graph_source"),
                "treatment_destination": "graphify-out/graph.json",
                "sha256": self.config.get("_graphify_graph_sha256"),
                "size_bytes": self.config.get("_graphify_graph_size_bytes"),
                "build_duration_seconds": self.config.get(
                    "graphify_graph_build_duration_seconds"
                ),
                "build_cost_usd": self.config.get(
                    "graphify_graph_build_cost_usd"
                ),
                "included_in_run_timing": False,
            }
            if treatment_mode == "forced_graphify_skill_cli"
            else None,
            "graphify_skill": {
                "configured": bool(self.config.get("graphify_skill_source")),
                "source": self.config.get("_resolved_graphify_skill_source"),
                "skill_name": self.config.get("_graphify_skill_name"),
                "treatment_destination": (
                    str(skill_destination(self.config["_graphify_skill_name"]))
                    if self.config.get("_graphify_skill_name")
                    else None
                ),
                "runtime_loaded_observable": False,
            },
            "copilot_version": self.config.get("copilot_version", "unknown"),
            "seed": self.config["seed"],
            "pilot": pilot,
            "repetitions": repetitions,
            "metrics": self.config["metrics"],
            "worktree_exclude_paths": self.config.get("worktree_exclude_paths", []),
            "plan": plan,
            "task_sources": {
                task["id"]: task["_source_path"] for task in tasks
            },
        }
        _write_json(run_root / "manifest.json", manifest)

        raw_runs = []
        for item in plan:
            task = task_by_id[item["task_id"]]
            try:
                raw_runs.append(self._run_one(run_root, item, task))
            except Exception as error:
                raw_runs.append(self._failed_run(run_root, item, task, error))
        manifest["skill_status_by_run"] = {
            run["run_id"]: {
                "skill_staged": run.get("graphify_skill_staged"),
                "skill_loaded": run.get("graphify_skill_loaded"),
                "skill_runtime_loaded": run.get("graphify_skill_runtime_loaded"),
                "skill_valid": run.get("graphify_skill_valid"),
                "skill_invalid_reason": run.get("graphify_skill_invalid_reason"),
            }
            for run in raw_runs
        }
        _write_json(run_root / "manifest.json", manifest)

        report_metadata = {
            key: manifest[key]
            for key in (
                "created_at",
                "repo_ref",
                "model",
                "reasoning_effort",
                "graphify_server",
                "treatment_mode",
                "copilot_version",
                "seed",
                "pilot",
                "repetitions",
                "forced_graphify_directive",
                "order_limitation",
                "graphify_graph_setup",
            )
        }
        report = build_report(
            raw_runs,
            report_metadata,
            float(self.config.get("score_tie_tolerance", 0.01)),
        )
        write_json(run_root / "report.json", report)
        write_csv(run_root / "runs.csv", raw_runs)
        write_markdown(run_root / "REPORT.md", report)
        return run_root

    def preflight(self) -> Path:
        if not self.config.get("graphify_skill_source"):
            raise BenchmarkRunError(
                "Skill preflight requires graphify_skill_source in configuration"
            )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = self.results_dir / ("skill-preflight-%s" % timestamp)
        output_dir.mkdir(parents=True)
        statuses = {}
        for condition in ("graphify_off", "graphify_on"):
            temp_parent = Path(tempfile.mkdtemp(prefix="graphify-skill-preflight-"))
            worktree_path = temp_parent / "worktree"
            registered = False
            try:
                add = _run_capture(
                    [
                        "git",
                        "worktree",
                        "add",
                        "--detach",
                        str(worktree_path),
                        self.config["repo_ref"],
                    ],
                    cwd=self.repo_root,
                    timeout=120,
                )
                if add.returncode != 0:
                    raise BenchmarkRunError(add.stderr.strip())
                registered = True
                removed, status = _prepare_skill_condition(
                    self.config, worktree_path, condition
                )
                graph_status = _prepare_graph_condition(
                    self.config, worktree_path, condition
                )
                status["removed_worktree_paths"] = removed
                status["graph"] = graph_status
                status["valid"] = status["valid"] and graph_status["valid"]
                if not graph_status["valid"]:
                    status["invalid_reason"] = graph_status["invalid_reason"]
                (output_dir / ("%s-skill-list.txt" % condition)).write_text(
                    status.pop("_skill_list_stdout", "")
                    + status.pop("_skill_list_stderr", ""),
                    encoding="utf-8",
                )
                statuses[condition] = status
            finally:
                if registered:
                    _run_capture(
                        ["git", "worktree", "remove", "--force", str(worktree_path)],
                        cwd=self.repo_root,
                        timeout=120,
                    )
                shutil.rmtree(str(temp_parent), ignore_errors=True)
        result = {
            "mode": "model_free_skill_preflight",
            "treatment_mode": self.config.get("treatment_mode", "mcp_only"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repo_ref": self.config["repo_ref"],
            "graphify_skill": {
                "source": self.config.get("_resolved_graphify_skill_source"),
                "skill_name": self.config.get("_graphify_skill_name"),
                "runtime_loaded_observable": False,
            },
            "forced_graphify_directive": self.config.get(
                "forced_graphify_directive"
            ),
            "graphify_graph_setup": {
                "source": self.config.get("_resolved_graphify_graph_source"),
                "sha256": self.config.get("_graphify_graph_sha256"),
                "size_bytes": self.config.get("_graphify_graph_size_bytes"),
                "build_duration_seconds": self.config.get(
                    "graphify_graph_build_duration_seconds"
                ),
                "build_cost_usd": self.config.get(
                    "graphify_graph_build_cost_usd"
                ),
                "included_in_run_timing": False,
            }
            if self.config.get("treatment_mode") == "forced_graphify_skill_cli"
            else None,
            "order_limitation": (
                "Controls are executed before treatments; phase order is not "
                "counterbalanced."
                if self.config.get("treatment_mode") == "forced_graphify_skill_cli"
                else None
            ),
            "conditions": statuses,
            "valid": all(status["valid"] for status in statuses.values()),
        }
        _write_json(output_dir / "skill-preflight.json", result)
        if not result["valid"]:
            raise BenchmarkRunError(
                "Skill preflight failed; inspect %s" % (output_dir / "skill-preflight.json")
            )
        return output_dir

    def smoke(self, task_id: str) -> Path:
        tasks = {task["id"]: task for task in load_tasks(self.tasks_dir)}
        if task_id not in tasks:
            raise BenchmarkRunError("Unknown task id: %s" % task_id)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_root = self.results_dir / ("treatment-smoke-%s" % timestamp)
        run_root.mkdir(parents=True)
        plan_item = {
            "task_id": task_id,
            "repetition": 1,
            "pair_id": "non-scored-smoke-%s" % task_id,
            "position": 1,
            "condition": "graphify_on",
        }
        manifest = {
            "mode": "treatment_only_smoke",
            "scored": False,
            "treatment_mode": self.config.get("treatment_mode", "mcp_only"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repo_ref": self.config["repo_ref"],
            "graphify_server": self.config.get("graphify_server"),
            "graphify_skill_source": self.config.get(
                "_resolved_graphify_skill_source"
            ),
            "forced_graphify_directive": self.config.get(
                "forced_graphify_directive"
            )
            if self.config.get("treatment_mode") == "forced_graphify_skill_cli"
            else None,
            "graphify_graph_setup": {
                "source": self.config.get("_resolved_graphify_graph_source"),
                "treatment_destination": "graphify-out/graph.json",
                "sha256": self.config.get("_graphify_graph_sha256"),
                "size_bytes": self.config.get("_graphify_graph_size_bytes"),
                "build_duration_seconds": self.config.get(
                    "graphify_graph_build_duration_seconds"
                ),
                "build_cost_usd": self.config.get(
                    "graphify_graph_build_cost_usd"
                ),
                "included_in_run_timing": False,
            }
            if self.config.get("treatment_mode") == "forced_graphify_skill_cli"
            else None,
            "task_id": task_id,
            "plan": [plan_item],
        }
        _write_json(run_root / "manifest.json", manifest)
        metrics = self._run_one(run_root, plan_item, tasks[task_id], scored=False)
        manifest["skill_status"] = {
            "skill_staged": metrics.get("graphify_skill_staged"),
            "skill_loaded": metrics.get("graphify_skill_loaded"),
            "skill_runtime_loaded": metrics.get("graphify_skill_runtime_loaded"),
            "skill_valid": metrics.get("graphify_skill_valid"),
        }
        _write_json(run_root / "manifest.json", manifest)
        _write_json(run_root / "smoke.json", metrics)
        (run_root / "SMOKE.md").write_text(
            "# Non-scored Graphify treatment smoke\n\n"
            "This directory contains exactly one `graphify_on` run. It is not "
            "included in paired benchmark summaries or win/tie/loss scoring.\n\n"
            "- Task: `%s`\n"
            "- Condition valid: `%s`\n"
            "- Skill staged: `%s`\n"
            "- Skill discovered before run: `%s`\n"
            "- Runtime skill selection: `not observable from free preflight`\n"
            % (
                task_id,
                metrics["condition_valid"],
                metrics.get("graphify_skill_staged"),
                metrics.get("graphify_skill_loaded"),
            ),
            encoding="utf-8",
        )
        return run_root

    def _failed_run(
        self,
        run_root: Path,
        plan_item: Dict[str, Any],
        task: Dict[str, Any],
        error: Exception,
    ) -> Dict[str, Any]:
        run_id = "%s-%s-p%d" % (
            plan_item["pair_id"],
            plan_item["condition"],
            plan_item["position"],
        )
        artifact_dir = run_root / "runs" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        message = "%s: %s" % (type(error).__name__, error)
        (artifact_dir / "run-error.log").write_text(message + "\n", encoding="utf-8")
        skill_event = {}
        events_path = artifact_dir / "events.jsonl"
        if events_path.exists():
            try:
                first_event = json.loads(
                    events_path.read_text(encoding="utf-8").splitlines()[0]
                )
                if first_event.get("type") == "harness.skill_status":
                    skill_event = first_event.get("data", {})
            except (IndexError, json.JSONDecodeError, OSError):
                pass
        metrics = {
            "run_id": run_id,
            "pair_id": plan_item["pair_id"],
            "task_id": task["id"],
            "category": task["category"],
            "condition": plan_item["condition"],
            "scored": True,
            "condition_valid": False,
            "condition_invalid_reason": message,
            "position": plan_item["position"],
            "repetition": plan_item["repetition"],
            "objective_pass": False,
            "correctness_score": 0.0,
            "wall_time_seconds": 0.0,
            "session_duration_ms": None,
            "ai_credits_nano": None,
            "input_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 0,
            "graphify_invocation_count": 0,
            "graphify_skill_staged": skill_event.get("staged", False),
            "graphify_skill_loaded": skill_event.get("loaded"),
            "graphify_skill_runtime_loaded": skill_event.get("runtime_loaded"),
            "graphify_skill_valid": skill_event.get("valid", False),
            "graphify_skill_invalid_reason": skill_event.get(
                "invalid_reason", message
            ),
            "graphify_targeted_follow_up_count": 0,
            "graphify_cli_calls": [],
            "graphify_cli_invocation_count": 0,
            "graphify_cli_success_count": 0,
            "graphify_cli_targeted_follow_up_count": 0,
            "search_call_count": 0,
            "broad_search_count": 0,
            "targeted_search_count": 0,
            "unique_files_read_count": 0,
            "exploration_before_first_correct_target": None,
            "tool_failure_count": 0,
            "model_failure_count": 0,
            "mcp_failure_count": 0,
            "validation_exit_code": None,
            "copilot_exit_code": None,
            "artifact_directory": str(artifact_dir.relative_to(run_root)),
            "run_error": message,
        }
        _write_json(artifact_dir / "metrics.json", metrics)
        return metrics

    def _run_one(
        self,
        run_root: Path,
        plan_item: Dict[str, Any],
        task: Dict[str, Any],
        scored: bool = True,
    ) -> Dict[str, Any]:
        run_id = "%s-%s-p%d" % (
            plan_item["pair_id"],
            plan_item["condition"],
            plan_item["position"],
        )
        artifact_dir = run_root / "runs" / run_id
        artifact_dir.mkdir(parents=True)
        _write_json(artifact_dir / "task.json", {
            key: value for key, value in task.items() if not key.startswith("_")
        })
        treatment_mode = self.config.get("treatment_mode", "mcp_only")
        base_prompt = task["prompt"]
        effective_prompt, directive_applied = _effective_prompt(
            self.config, plan_item["condition"], base_prompt
        )
        (artifact_dir / "base-prompt.txt").write_text(
            base_prompt + "\n", encoding="utf-8"
        )
        (artifact_dir / "prompt.txt").write_text(
            effective_prompt + "\n", encoding="utf-8"
        )

        temp_parent = Path(tempfile.mkdtemp(prefix="graphify-benchmark-"))
        worktree_path = temp_parent / "worktree"
        worktree_registered = False
        copilot_exit_code = None
        timed_out = False
        wall_seconds = 0.0
        try:
            add = _run_capture(
                [
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    str(worktree_path),
                    self.config["repo_ref"],
                ],
                cwd=self.repo_root,
                timeout=120,
            )
            if add.returncode != 0:
                raise BenchmarkRunError(
                    "Unable to create clean worktree for %s: %s"
                    % (run_id, add.stderr.strip())
                )
            worktree_registered = True
            removed_exclusions, skill_status = _prepare_skill_condition(
                self.config, worktree_path, plan_item["condition"]
            )
            graph_status = _prepare_graph_condition(
                self.config, worktree_path, plan_item["condition"]
            )
            skill_status_artifact = _skill_status_for_artifact(skill_status)
            (artifact_dir / "skill-list.txt").write_text(
                skill_status.pop("_skill_list_stdout", "")
                + skill_status.pop("_skill_list_stderr", ""),
                encoding="utf-8",
            )
            events_path = artifact_dir / "events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "type": "harness.skill_status",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": skill_status_artifact,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with events_path.open("a", encoding="utf-8") as events_handle:
                events_handle.write(
                    json.dumps(
                        {
                            "type": "harness.graph_status",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "data": graph_status,
                        }
                    )
                    + "\n"
                )
            if not skill_status_artifact["valid"]:
                raise BenchmarkRunError(
                    "Graphify skill condition is invalid: %s"
                    % skill_status_artifact["invalid_reason"]
                )
            if not graph_status["valid"]:
                raise BenchmarkRunError(
                    "Graphify graph condition is invalid: %s"
                    % graph_status["invalid_reason"]
                )
            session_id = str(uuid.uuid4())
            usage_path = artifact_dir / "usage.json"
            share_path = artifact_dir / "session.md"
            logs_dir = artifact_dir / "debug-logs"
            logs_dir.mkdir()
            command = [
                self.config["copilot_command"],
                "-C",
                str(worktree_path),
                "-p",
                effective_prompt,
                "--model",
                self.config["model"],
                "--reasoning-effort",
                self.config["reasoning_effort"],
                "--session-id",
                session_id,
                "--no-ask-user",
                "--allow-all-tools",
                "--output-format",
                "json",
                "--log-level",
                "all",
                "--log-dir",
                str(logs_dir),
                "--usage-output-file",
                str(usage_path),
                "--share",
                str(share_path),
                "--no-remote",
                "--no-remote-export",
                "--no-auto-update",
            ]
            command.extend(
                _graphify_mcp_args(self.config, plan_item["condition"])
            )
            command.extend(self.config.get("copilot_extra_args", []))
            _write_json(
                artifact_dir / "command.json",
                {
                    "argv": command,
                    "session_id": session_id,
                    "cwd": str(worktree_path),
                    "copilot_version": self.config.get("copilot_version", "unknown"),
                    "removed_worktree_paths": removed_exclusions,
                    "graphify_skill": skill_status_artifact,
                    "graphify_graph": graph_status,
                    "base_prompt": base_prompt,
                    "effective_prompt": effective_prompt,
                    "forced_directive_applied": directive_applied,
                },
            )

            environment = os.environ.copy()
            otel = self.config.get("otel", {})
            if otel.get("enabled"):
                environment["COPILOT_OTEL_FILE_EXPORTER_PATH"] = str(
                    artifact_dir / "otel.jsonl"
                )
                if otel.get("capture_message_content"):
                    environment[
                        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
                    ] = "true"

            started = time.monotonic()
            with events_path.open("a", encoding="utf-8") as stdout_handle, (
                artifact_dir / "stderr.log"
            ).open("w", encoding="utf-8") as stderr_handle:
                try:
                    completed = subprocess.run(
                        command,
                        cwd=str(worktree_path),
                        env=environment,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                        timeout=int(self.config["run_timeout_seconds"]),
                        check=False,
                    )
                    copilot_exit_code = completed.returncode
                except subprocess.TimeoutExpired:
                    timed_out = True
                    copilot_exit_code = 124
            wall_seconds = time.monotonic() - started
            if not usage_path.exists():
                usage_path.write_text("{}\n", encoding="utf-8")
            if not share_path.exists():
                share_path.write_text(
                    "Session export was not produced by Copilot CLI.\n",
                    encoding="utf-8",
                )
            _write_json(
                artifact_dir / "wall-time.json",
                {
                    "seconds": round(wall_seconds, 6),
                    "source": "Python time.monotonic",
                    "timed_out": timed_out,
                },
            )

            status = _run_capture(
                ["git", "status", "--short"], cwd=worktree_path
            )
            diff = _run_capture(
                ["git", "--no-pager", "diff", "--binary", "--no-ext-diff"],
                cwd=worktree_path,
            )
            injected_paths = []
            if skill_status_artifact.get("staged"):
                injected_paths.append(
                    str(skill_destination(skill_status_artifact["skill_name"]))
                )
            if graph_status["configured"]:
                injected_paths.append(str(Path(graph_status["destination"]).parent))
            filtered_status = _filtered_status(status.stdout, injected_paths)
            full_diff = _append_untracked_diffs(
                worktree_path, diff.stdout, injected_paths
            )
            (artifact_dir / "git.status").write_text(
                filtered_status, encoding="utf-8"
            )
            (artifact_dir / "git.diff").write_text(full_diff, encoding="utf-8")

            validation_exit_code = None
            validation_command = task.get("validation", {}).get("command")
            if validation_command:
                validation_started = time.monotonic()
                try:
                    validation = subprocess.run(
                        validation_command,
                        cwd=str(worktree_path),
                        shell=True,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=int(self.config["validation_timeout_seconds"]),
                        check=False,
                    )
                    validation_exit_code = validation.returncode
                    validation_output = validation.stdout
                    validation_timed_out = False
                except subprocess.TimeoutExpired as error:
                    validation_exit_code = 124
                    timeout_output = error.stdout or ""
                    if isinstance(timeout_output, bytes):
                        timeout_output = timeout_output.decode("utf-8", errors="replace")
                    validation_output = timeout_output + "\nValidation timed out\n"
                    validation_timed_out = True
                (artifact_dir / "validation.log").write_text(
                    validation_output, encoding="utf-8"
                )
                _write_json(
                    artifact_dir / "validation.json",
                    {
                        "command": validation_command,
                        "exit_code": validation_exit_code,
                        "seconds": round(time.monotonic() - validation_started, 6),
                        "timed_out": validation_timed_out,
                    },
                )

            events, malformed_events = load_events(events_path)
            final_answer = extract_final_answer(events)
            (artifact_dir / "final-answer.md").write_text(
                final_answer + ("\n" if final_answer else ""), encoding="utf-8"
            )
            task_for_metrics = dict(task)
            task_for_metrics["_graphify_server"] = self.config.get(
                "graphify_server"
            )
            derived = calculate_metrics(
                events, usage_path, task_for_metrics, self.config["metrics"]
            )
            if scored:
                grade = grade_task(
                    task,
                    final_answer,
                    events_path.read_text(encoding="utf-8", errors="replace"),
                    full_diff,
                    filtered_status,
                    validation_exit_code,
                )
            else:
                grade = {
                    "correctness_score": None,
                    "objective_pass": None,
                    "found_expected_targets": [],
                    "missing_expected_targets": [],
                    "false_positives": [],
                    "validation_passed": validation_exit_code == 0,
                }
            _write_json(artifact_dir / "tool-timeline.json", derived["tool_timeline"])
            derived_without_timeline = {
                key: value for key, value in derived.items() if key != "tool_timeline"
            }
            metrics = {
                "run_id": run_id,
                "pair_id": plan_item["pair_id"],
                "task_id": task["id"],
                "category": task["category"],
                "condition": plan_item["condition"],
                "position": plan_item["position"],
                "repetition": plan_item["repetition"],
                "wall_time_seconds": round(wall_seconds, 6),
                "copilot_exit_code": copilot_exit_code,
                "copilot_timed_out": timed_out,
                "malformed_event_count": malformed_events,
                "validation_exit_code": validation_exit_code,
                "artifact_directory": str(artifact_dir.relative_to(run_root)),
                "scored": scored,
                "graphify_skill_staged": skill_status_artifact["staged"],
                "graphify_skill_loaded": skill_status_artifact["loaded"],
                "graphify_skill_runtime_loaded": skill_status_artifact[
                    "runtime_loaded"
                ],
                "graphify_skill_valid": skill_status_artifact["valid"],
                "graphify_skill_invalid_reason": skill_status_artifact[
                    "invalid_reason"
                ],
                "graphify_graph_staged": graph_status["staged"],
                "graphify_graph_present": graph_status["present"],
                "graphify_graph_read_only": graph_status["read_only"],
                "graphify_graph_sha256": graph_status["destination_sha256"],
                "forced_directive_applied": directive_applied,
            }
            metrics.update(grade)
            metrics.update(derived_without_timeline)
            if treatment_mode == "forced_graphify_skill_cli":
                condition_valid, invalid_reason = _forced_condition_validity(
                    plan_item["condition"],
                    skill_status_artifact,
                    graph_status,
                    metrics,
                )
            else:
                mcp_valid, mcp_invalid_reason = _condition_validity(
                    plan_item["condition"],
                    metrics["graphify_mcp_statuses"],
                    metrics["graphify_invocation_count"],
                )
                condition_valid, invalid_reason = _merge_condition_validity(
                    mcp_valid, mcp_invalid_reason, skill_status_artifact
                )
            metrics["condition_valid"] = condition_valid
            metrics["condition_invalid_reason"] = invalid_reason
            usage = metrics.pop("usage", {})
            metrics.update(usage)
            metrics["tool_failure_count"] = len(metrics["tool_failures"])
            metrics["model_failure_count"] = len(metrics["model_failures"])
            metrics["mcp_failure_count"] = len(metrics["mcp_failures"])
            metrics["run_error"] = None
            _write_json(artifact_dir / "metrics.json", metrics)
            return metrics
        finally:
            if worktree_registered:
                remove = _run_capture(
                    ["git", "worktree", "remove", "--force", str(worktree_path)],
                    cwd=self.repo_root,
                    timeout=120,
                )
                if remove.returncode != 0:
                    _run_capture(["git", "worktree", "prune"], cwd=self.repo_root)
            if worktree_path.exists():
                shutil.rmtree(str(worktree_path), ignore_errors=True)
            if temp_parent.exists():
                shutil.rmtree(str(temp_parent), ignore_errors=True)
