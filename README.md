# Graphify benchmark toolkit

This repository is a self-contained toolkit for comparing GitHub Copilot CLI
with and without Graphify against any Git repository.

The included Adempiere reports are examples. Teams run the harness against
their own checkout and write tasks grounded in their own source code.

## What is included

- `scripts/graphify_benchmark.py`: command-line entry point
- `scripts/graphify_benchmark/`: benchmark runner, grading, metrics, and reports
- `tests/benchmark_harness/`: model-free harness tests
- `examples/`: configuration and task-definition examples
- `docs/app-team-quick-start.md`: shortest path from checkout to first pilot
- `docs/task-authoring.md`: how to create objective repository-specific tasks
- `docs/graphify-benchmark.md`: complete reference
- `reports/`: the Adempiere sample reports and frozen task contracts

## How another team uses it

The harness repository and target repository remain separate:

```text
/work/graphify-benchmark-poc/       this repository
/work/their-application/            the code being benchmarked
```

Run the harness while the current directory is the target repository:

```bash
export HARNESS_ROOT=/work/graphify-benchmark-poc
cd /work/their-application

python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" configure \
  --treatment-mode forced_graphify_skill_cli \
  --graphify-skill-source /absolute/path/to/graphify-skill \
  --graphify-graph-source "$PWD/graphify-out/graph.json" \
  --tasks-dir "$PWD/benchmarks/graphify/tasks" \
  --results-dir "$PWD/benchmark-results/graphify" \
  --model claude-opus-5 \
  --reasoning-effort medium

python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" doctor
python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" preflight
python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" run --pilot
```

`claude-opus-5` with medium reasoning is the exact model configuration used
for the included Adempiere benchmarks.

`configure` pins the target repository's current commit. Every measured run
uses a disposable worktree at that commit. The control receives no Graphify
skill or graph. The treatment receives the skill and a read-only copy of the
prebuilt graph.

The team must replace the example tasks with task definitions for its own
source tree. Start with one cross-module impact-analysis task and one real
implementation task with an automated validation command.

See [App team quick start](docs/app-team-quick-start.md) for the complete
handoff sequence.

## Adempiere examples

- [Forced Graphify skill and CLI benchmark](reports/adempiere-forced-skill-cli-2026-09-18/)
- [Structural graph-native follow-up](reports/adempiere-structural-graph-native-2026-09-18/)

The reports show the exact prompts, grading contracts, metrics, conclusions,
and limitations from the original evaluation. They do not contain Adempiere
source code, generated answers, raw logs, graph data, credentials, or private
repository information.
