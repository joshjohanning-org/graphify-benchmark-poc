"""Command-line interface for the Graphify benchmark harness."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .config import (
    CONFIG_FILENAME,
    ConfigurationError,
    DEFAULT_FORCED_GRAPHIFY_DIRECTIVE,
    TREATMENT_MODES,
    create_config,
    git_root,
    list_mcp_servers,
    load_config,
    require_mcp_server,
    validate_config,
    write_config,
)
from .runner import BenchmarkRunError, BenchmarkRunner, load_tasks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run paired GitHub Copilot CLI benchmarks with Graphify on and off."
    )
    parser.add_argument(
        "--config",
        default=CONFIG_FILENAME,
        help="configuration JSON path (default: %(default)s)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-servers",
        help="print Copilot CLI MCP servers without requiring jq",
    )

    configure = subparsers.add_parser(
        "configure",
        help="create and validate a pinned benchmark configuration",
    )
    configure.add_argument(
        "--graphify-server",
        help=(
            "Graphify MCP server name; required for MCP modes and optional as "
            "a disabled-only server name for forced_graphify_skill_cli"
        ),
    )
    configure.add_argument(
        "--treatment-mode",
        choices=TREATMENT_MODES,
        help="explicit treatment mode (default derives from skill source)",
    )
    configure.add_argument("--model", required=True)
    configure.add_argument("--reasoning-effort", default="medium")
    configure.add_argument("--repetitions", type=int)
    configure.add_argument("--tasks-dir", default="benchmarks/graphify/tasks")
    configure.add_argument("--results-dir", default="benchmark-results/graphify")
    configure.add_argument("--repo-ref", default="HEAD")
    configure.add_argument("--seed", type=int, default=20260916)
    configure.add_argument("--copilot-command", default="copilot")
    configure.add_argument(
        "--graphify-skill-source",
        help=(
            "optional Graphify skill directory; staged only in graphify_on "
            "worktrees at .github/skills/<name>"
        ),
    )
    configure.add_argument(
        "--graphify-graph-source",
        help="immutable graph.json copied read-only into forced treatment worktrees",
    )
    configure.add_argument(
        "--graphify-graph-build-duration-seconds",
        type=float,
        help="separate prebuilt graph setup overhead; excluded from run timing",
    )
    configure.add_argument(
        "--graphify-graph-build-cost-usd",
        type=float,
        help="separate prebuilt graph setup cost; excluded from run metrics",
    )
    configure.add_argument(
        "--forced-graphify-directive",
        default=DEFAULT_FORCED_GRAPHIFY_DIRECTIVE,
        help="directive prepended only to forced_graphify_skill_cli treatment prompts",
    )
    configure.add_argument(
        "--force",
        action="store_true",
        help="replace an existing configuration file",
    )

    subparsers.add_parser(
        "doctor",
        help="validate configuration, git ref, task directory, Copilot, and Graphify",
    )

    run = subparsers.add_parser("run", help="execute the paired benchmark")
    run.add_argument(
        "--pilot",
        action="store_true",
        help="run one repetition of the first task in each category",
    )
    run.add_argument(
        "--task",
        action="append",
        dest="tasks",
        help="limit execution to a task id (repeatable)",
    )

    subparsers.add_parser(
        "preflight",
        help="freely verify treatment-only skill staging without prompting a model",
    )

    smoke = subparsers.add_parser(
        "smoke",
        help="run one treatment-only, non-scored task outside paired summaries",
    )
    smoke.add_argument("--task", required=True, help="exactly one task id")
    smoke.add_argument(
        "--confirm-paid-run",
        action="store_true",
        help="required acknowledgement that this command invokes Copilot",
    )
    return parser


def _config_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _configure(args: argparse.Namespace, config_path: Path) -> int:
    if config_path.exists() and not args.force:
        raise ConfigurationError(
            "%s already exists; pass --force to replace it" % config_path
        )
    repo_root = git_root(Path.cwd())
    treatment_mode = args.treatment_mode
    if treatment_mode is None:
        treatment_mode = (
            "skill_and_mcp" if args.graphify_skill_source else "mcp_only"
        )
    repetitions = args.repetitions
    if repetitions is None:
        repetitions = 1 if treatment_mode == "forced_graphify_skill_cli" else 3
    if repetitions < 1:
        raise ConfigurationError("--repetitions must be at least 1")
    if treatment_mode != "forced_graphify_skill_cli":
        if not args.graphify_server:
            raise ConfigurationError(
                "--graphify-server is required for MCP treatment modes"
            )
        require_mcp_server(
            args.graphify_server, args.copilot_command, cwd=repo_root
        )
    config = create_config(
        repo_root=repo_root,
        graphify_server=args.graphify_server,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        repetitions=repetitions,
        tasks_dir=args.tasks_dir,
        results_dir=args.results_dir,
        repo_ref=args.repo_ref,
        seed=args.seed,
        copilot_command=args.copilot_command,
        graphify_skill_source=args.graphify_skill_source,
        treatment_mode=treatment_mode,
        graphify_graph_source=args.graphify_graph_source,
        graphify_graph_build_duration_seconds=(
            args.graphify_graph_build_duration_seconds
        ),
        graphify_graph_build_cost_usd=args.graphify_graph_build_cost_usd,
        forced_graphify_directive=args.forced_graphify_directive,
    )
    write_config(config_path, config)
    validate_config(config, config_path, check_environment=True)
    print("Wrote validated benchmark configuration to %s" % config_path)
    print("Pinned repository commit: %s" % config["repo_ref"])
    return 0


def _doctor(config_path: Path) -> int:
    config = load_config(config_path)
    repo_root, tasks_dir, results_dir = validate_config(
        config, config_path, check_environment=True
    )
    tasks = load_tasks(tasks_dir)
    print("Configuration is valid.")
    print("Repository: %s @ %s" % (repo_root, config["repo_ref"]))
    print("Tasks: %s" % tasks_dir)
    print("Results: %s" % results_dir)
    print("Treatment mode: %s" % config["treatment_mode"])
    print("Graphify server: %s" % (config.get("graphify_server") or "disabled"))
    print("Model: %s (%s)" % (config["model"], config["reasoning_effort"]))
    print("Copilot CLI: %s" % config.get("copilot_version", "unknown"))
    print("Task definitions: %d" % len(tasks))
    if config.get("graphify_skill_source"):
        print(
            "Treatment skill: %s -> .github/skills/%s"
            % (
                config["_resolved_graphify_skill_source"],
                config["_graphify_skill_name"],
            )
        )
    else:
        print("Treatment skill: disabled (MCP-only mode)")
    if config["treatment_mode"] == "forced_graphify_skill_cli":
        print(
            "Treatment graph: %s (%s bytes, SHA-256 %s)"
            % (
                config["_resolved_graphify_graph_source"],
                config["_graphify_graph_size_bytes"],
                config["_graphify_graph_sha256"],
            )
        )
        print(
            "Graph build overhead: %s seconds (excluded from run timing)"
            % config.get("graphify_graph_build_duration_seconds")
        )
        print(
            "Graph build cost: $%s (excluded from run metrics)"
            % config.get("graphify_graph_build_cost_usd")
        )
        print("Forced order: all controls, then all treatments")
    return 0


def _run(args: argparse.Namespace, config_path: Path) -> int:
    config = load_config(config_path)
    repo_root, tasks_dir, results_dir = validate_config(
        config, config_path, check_environment=True
    )
    runner = BenchmarkRunner(config, repo_root, tasks_dir, results_dir)
    report_dir = runner.run(pilot=args.pilot, task_ids=args.tasks)
    print("Benchmark complete: %s" % report_dir)
    print("Markdown report: %s" % (report_dir / "REPORT.md"))
    print("JSON report: %s" % (report_dir / "report.json"))
    print("CSV metrics: %s" % (report_dir / "runs.csv"))
    return 0


def _preflight(config_path: Path) -> int:
    config = load_config(config_path)
    repo_root, tasks_dir, results_dir = validate_config(
        config, config_path, check_environment=True
    )
    runner = BenchmarkRunner(config, repo_root, tasks_dir, results_dir)
    output = runner.preflight()
    print("Skill preflight complete: %s" % output)
    return 0


def _smoke(args: argparse.Namespace, config_path: Path) -> int:
    if not args.confirm_paid_run:
        raise ConfigurationError(
            "`smoke` invokes one Copilot model session; rerun with --confirm-paid-run"
        )
    config = load_config(config_path)
    if not config.get("graphify_skill_source"):
        raise ConfigurationError(
            "`smoke` requires graphify_skill_source; use `run` for MCP-only benchmarks"
        )
    repo_root, tasks_dir, results_dir = validate_config(
        config, config_path, check_environment=True
    )
    runner = BenchmarkRunner(config, repo_root, tasks_dir, results_dir)
    output = runner.smoke(args.task)
    print("Non-scored treatment smoke complete: %s" % output)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    config_path = _config_path(args.config)
    try:
        if args.command == "list-servers":
            print(list_mcp_servers(), end="")
            return 0
        if args.command == "configure":
            return _configure(args, config_path)
        if args.command == "doctor":
            return _doctor(config_path)
        if args.command == "run":
            return _run(args, config_path)
        if args.command == "preflight":
            return _preflight(config_path)
        if args.command == "smoke":
            return _smoke(args, config_path)
        parser.error("unknown command")
    except (ConfigurationError, BenchmarkRunError, OSError, subprocess.SubprocessError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    return 2
