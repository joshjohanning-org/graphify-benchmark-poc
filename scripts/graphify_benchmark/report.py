"""Markdown, JSON, and CSV benchmark report generation."""

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    return round(statistics.mean(clean), 3) if clean else None


def _median(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    return round(statistics.median(clean), 3) if clean else None


def _condition_summary(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid_runs = [run for run in runs if run.get("condition_valid", True)]
    return {
        "runs": len(runs),
        "valid_runs": len(valid_runs),
        "invalid_runs": len(runs) - len(valid_runs),
        "objective_pass_rate": round(
            sum(1 for run in valid_runs if run["objective_pass"]) / len(valid_runs), 4
        )
        if valid_runs
        else 0.0,
        "mean_correctness_score": _mean(
            run["correctness_score"] for run in valid_runs
        ),
        "median_wall_time_seconds": _median(
            run["wall_time_seconds"] for run in valid_runs
        ),
        "median_session_duration_ms": _median(
            run.get("session_duration_ms") for run in valid_runs
        ),
        "mean_ai_credits_nano": _mean(
            run.get("ai_credits_nano") for run in valid_runs
        ),
        "mean_input_tokens": _mean(run.get("input_tokens") for run in valid_runs),
        "mean_output_tokens": _mean(run.get("output_tokens") for run in valid_runs),
        "mean_graphify_invocations": _mean(
            run.get("graphify_invocation_count") for run in valid_runs
        ),
        "mean_graphify_cli_invocations": _mean(
            run.get("graphify_cli_invocation_count") for run in valid_runs
        ),
        "mean_successful_graphify_cli_invocations": _mean(
            run.get("graphify_cli_success_count") for run in valid_runs
        ),
        "mean_broad_searches": _mean(
            run.get("broad_search_count") for run in valid_runs
        ),
        "mean_targeted_searches": _mean(
            run.get("targeted_search_count") for run in valid_runs
        ),
        "mean_unique_files_read": _mean(
            run.get("unique_files_read_count") for run in valid_runs
        ),
        "mean_exploration_before_target": _mean(
            run.get("exploration_before_first_correct_target") for run in valid_runs
        ),
        "never_found_target_count": sum(
            1
            for run in valid_runs
            if run.get("exploration_before_first_correct_target") is None
        ),
    }


def _pair_outcome(on_run: Dict[str, Any], off_run: Dict[str, Any], tolerance: float) -> str:
    if on_run["objective_pass"] != off_run["objective_pass"]:
        return "win" if on_run["objective_pass"] else "loss"
    delta = on_run["correctness_score"] - off_run["correctness_score"]
    if delta > tolerance:
        return "win"
    if delta < -tolerance:
        return "loss"
    return "tie"


def build_report(
    runs: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    tie_tolerance: float,
) -> Dict[str, Any]:
    by_task_condition = defaultdict(list)
    by_category_condition = defaultdict(list)
    by_pair = defaultdict(dict)
    for run in runs:
        by_task_condition[(run["task_id"], run["condition"])].append(run)
        by_category_condition[(run["category"], run["condition"])].append(run)
        by_pair[run["pair_id"]][run["condition"]] = run

    pair_results = []
    totals = {"win": 0, "tie": 0, "loss": 0, "invalid": 0}
    task_totals = defaultdict(
        lambda: {"win": 0, "tie": 0, "loss": 0, "invalid": 0}
    )
    for pair_id, conditions in sorted(by_pair.items()):
        if "graphify_on" not in conditions or "graphify_off" not in conditions:
            continue
        on_run = conditions["graphify_on"]
        off_run = conditions["graphify_off"]
        if not on_run.get("condition_valid", True) or not off_run.get(
            "condition_valid", True
        ):
            outcome = "invalid"
        else:
            outcome = _pair_outcome(on_run, off_run, tie_tolerance)
        totals[outcome] += 1
        task_totals[on_run["task_id"]][outcome] += 1
        pair_results.append(
            {
                "pair_id": pair_id,
                "task_id": on_run["task_id"],
                "category": on_run["category"],
                "outcome_for_graphify": outcome,
                "graphify_on_score": on_run["correctness_score"],
                "graphify_off_score": off_run["correctness_score"],
                "graphify_on_pass": on_run["objective_pass"],
                "graphify_off_pass": off_run["objective_pass"],
            }
        )

    tasks = {}
    for task_id in sorted(set(run["task_id"] for run in runs)):
        tasks[task_id] = {
            "win_tie_loss": task_totals[task_id],
            "graphify_on": _condition_summary(
                by_task_condition[(task_id, "graphify_on")]
            ),
            "graphify_off": _condition_summary(
                by_task_condition[(task_id, "graphify_off")]
            ),
        }
    categories = {}
    for category in sorted(set(run["category"] for run in runs)):
        categories[category] = {
            "graphify_on": _condition_summary(
                by_category_condition[(category, "graphify_on")]
            ),
            "graphify_off": _condition_summary(
                by_category_condition[(category, "graphify_off")]
            ),
        }
    return {
        "metadata": metadata,
        "summary": {
            "win_tie_loss_for_graphify": totals,
            "tasks": tasks,
            "categories": categories,
        },
        "paired_results": pair_results,
        "runs": runs,
    }


def write_json(path: Path, report: Dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


CSV_FIELDS = [
    "run_id",
    "pair_id",
    "task_id",
    "category",
    "condition",
    "scored",
    "condition_valid",
    "condition_invalid_reason",
    "position",
    "repetition",
    "objective_pass",
    "correctness_score",
    "wall_time_seconds",
    "session_duration_ms",
    "ai_credits_nano",
    "input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "output_tokens",
    "graphify_invocation_count",
    "graphify_cli_invocation_count",
    "graphify_cli_success_count",
    "graphify_cli_targeted_follow_up_count",
    "graphify_skill_staged",
    "graphify_skill_loaded",
    "graphify_skill_runtime_loaded",
    "graphify_skill_valid",
    "graphify_skill_invalid_reason",
    "graphify_targeted_follow_up_count",
    "search_call_count",
    "broad_search_count",
    "targeted_search_count",
    "unique_files_read_count",
    "exploration_before_first_correct_target",
    "tool_failure_count",
    "model_failure_count",
    "mcp_failure_count",
    "validation_exit_code",
    "copilot_exit_code",
    "artifact_directory",
    "run_error",
]


def write_csv(path: Path, runs: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for run in runs:
            writer.writerow(run)


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def write_markdown(path: Path, report: Dict[str, Any]) -> None:
    metadata = report["metadata"]
    summary = report["summary"]
    treatment_mode = metadata.get("treatment_mode", "mcp_only")
    titles = {
        "mcp_only": "# Graphify MCP-only Copilot CLI benchmark",
        "skill_and_mcp": "# Graphify skill + MCP Copilot CLI benchmark",
        "forced_graphify_skill_cli": "# Graphify forced skill + CLI Copilot CLI benchmark",
    }
    title = titles.get(treatment_mode, titles["mcp_only"])
    lines = [
        title,
        "",
        "- Treatment mode: `%s`" % treatment_mode,
        "- Repository commit: `%s`" % metadata["repo_ref"],
        "- Model: `%s`" % metadata["model"],
        "- Reasoning effort: `%s`" % metadata["reasoning_effort"],
        (
            "- Graphify MCP server disabled in both arms: `%s`"
            if treatment_mode == "forced_graphify_skill_cli"
            else "- Graphify MCP server: `%s`"
        )
        % (metadata.get("graphify_server") or "none configured"),
        "- Copilot CLI: `%s`" % metadata.get("copilot_version", "unknown"),
        "- Reproducible ordering seed: `%s`" % metadata["seed"],
        "- Runs: `%d`" % len(report["runs"]),
    ]
    if treatment_mode == "forced_graphify_skill_cli":
        graph_setup = metadata.get("graphify_graph_setup") or {}
        lines.extend(
            [
                "- Forced treatment directive: `%s`"
                % metadata.get("forced_graphify_directive", ""),
                "- Graph setup SHA-256: `%s`" % graph_setup.get("sha256", "n/a"),
                "- Graph setup size: `%s` bytes"
                % graph_setup.get("size_bytes", "n/a"),
                "- Graph build duration (separate setup overhead): `%s` seconds"
                % _fmt(graph_setup.get("build_duration_seconds")),
                "- Graph build cost (separate setup overhead): `$%s`"
                % _fmt(graph_setup.get("build_cost_usd")),
                "- Phase-order limitation: %s"
                % metadata.get("order_limitation", "not recorded"),
            ]
        )
    lines.extend(
        [
            "",
        "## Correctness win/tie/loss",
        "",
        "A Graphify win or loss is based only on objective pass and correctness score. "
        "Duration, credits, and tool-use metrics are reported separately.",
        "",
        "| Graphify wins | Ties | Graphify losses | Invalid pairs |",
        "|---:|---:|---:|---:|",
            "| %d | %d | %d | %d |"
        % (
            summary["win_tie_loss_for_graphify"]["win"],
            summary["win_tie_loss_for_graphify"]["tie"],
            summary["win_tie_loss_for_graphify"]["loss"],
            summary["win_tie_loss_for_graphify"]["invalid"],
        ),
        "",
            "## Task comparison",
        "",
        "| Task | W/T/L/I | On pass rate | Off pass rate | On score | Off score | "
        "On median wall s | Off median wall s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for task_id, task in summary["tasks"].items():
        on = task["graphify_on"]
        off = task["graphify_off"]
        wtl = task["win_tie_loss"]
        lines.append(
            "| %s | %d/%d/%d/%d | %.1f%% | %.1f%% | %s | %s | %s | %s |"
            % (
                task_id,
                wtl["win"],
                wtl["tie"],
                wtl["loss"],
                wtl["invalid"],
                on["objective_pass_rate"] * 100,
                off["objective_pass_rate"] * 100,
                _fmt(on["mean_correctness_score"]),
                _fmt(off["mean_correctness_score"]),
                _fmt(on["median_wall_time_seconds"]),
                _fmt(off["median_wall_time_seconds"]),
            )
        )

    lines.extend(
        [
            "",
            "## Category comparison",
            "",
            "| Category | Condition | Valid/invalid | Pass rate | Mean score | "
            "Median wall s | Mean AI credits (nano) | Mean broad/targeted searches | "
            "Never found target |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for category, conditions in summary["categories"].items():
        for condition in ("graphify_on", "graphify_off"):
            values = conditions[condition]
            lines.append(
                "| %s | %s | %d/%d | %.1f%% | %s | %s | %s | %s/%s | %d |"
                % (
                    category,
                    condition,
                    values["valid_runs"],
                    values["invalid_runs"],
                    values["objective_pass_rate"] * 100,
                    _fmt(values["mean_correctness_score"]),
                    _fmt(values["median_wall_time_seconds"]),
                    _fmt(values["mean_ai_credits_nano"]),
                    _fmt(values["mean_broad_searches"]),
                    _fmt(values["mean_targeted_searches"]),
                    values["never_found_target_count"],
                )
            )

    lines.extend(
        [
            "",
            "## Raw runs",
            "",
            "| Run | Task | Condition | Valid | Pass | Score | Wall s | MCP calls | "
            "CLI calls/success | CLI -> targeted follow-up | Files read | Failures |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for run in report["runs"]:
        failures = (
            run["tool_failure_count"]
            + run["model_failure_count"]
            + run["mcp_failure_count"]
        )
        lines.append(
            "| %s | %s | %s | %s | %s | %.3f | %.3f | %d | %d/%d | %d | %d | %d |"
            % (
                run["run_id"],
                run["task_id"],
                run["condition"],
                "yes" if run.get("condition_valid", True) else "no",
                "yes" if run["objective_pass"] else "no",
                run["correctness_score"],
                run["wall_time_seconds"],
                run["graphify_invocation_count"],
                run.get("graphify_cli_invocation_count", 0),
                run.get("graphify_cli_success_count", 0),
                run.get("graphify_cli_targeted_follow_up_count", 0),
                run["unique_files_read_count"],
                failures,
            )
        )

    lines.extend(
        [
            "",
            "## Metric cautions",
            "",
            "- `graphify_targeted_follow_up_count` is a sequence heuristic: a configured "
            "Graphify tool call was followed within the configured window by a targeted "
            "search/read. It does not prove that Graphify caused or improved that action.",
            "- Broad versus targeted search is classified using the regex rules recorded "
            "in the run manifest. Review the tool timeline before making causal claims.",
            "- A Graphify-enabled run can connect successfully without invoking a Graphify "
            "tool. Connection status and invocation count are reported separately.",
            "- Invalid treatment/control pairs are excluded from win/tie/loss and aggregate "
            "condition metrics rather than being counted as Graphify evidence.",
            "- `graphify_cli_targeted_follow_up_count` is the corresponding heuristic "
            "for successful or failed CLI commands found only in shell tool arguments. "
            "It does not infer causality from output or answer text.",
            "",
            "Machine-readable details are in `report.json`; flat raw metrics are in "
            "`runs.csv`; each run directory retains the source artifacts and ordered tool "
            "timeline.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
