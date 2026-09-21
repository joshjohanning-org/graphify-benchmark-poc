# App team quick start

This guide runs a small Graphify comparison against the App team's own
repository. The benchmark toolkit does not contain or copy the App source.

## 1. Prepare two separate checkouts

```bash
git clone https://github.com/joshjohanning-org/graphify-benchmark-poc.git
git clone YOUR_APP_REPOSITORY_URL their-application

export HARNESS_ROOT="$PWD/graphify-benchmark-poc"
cd their-application
```

All following commands run from the App repository. This lets the harness pin
the App commit and create disposable App worktrees.

## 2. Build the App graph

Install Graphify and build `graphify-out/graph.json` from the App checkout.
Record the build duration separately. The benchmark reuses this immutable graph
and does not include graph construction in per-task time or AIC.

Confirm the graph and Graphify skill paths:

```bash
test -f "$PWD/graphify-out/graph.json"
test -f /absolute/path/to/graphify-skill/SKILL.md
```

## 3. Create App-specific tasks

```bash
mkdir -p benchmarks/graphify/tasks
cp "$HARNESS_ROOT/examples/tasks/analysis-task.template.json" \
  benchmarks/graphify/tasks/app-impact-analysis.json
cp "$HARNESS_ROOT/examples/tasks/implementation-task.template.json" \
  benchmarks/graphify/tasks/app-implementation.json
```

Edit both files so every expected path, symbol, relationship, false-positive
rule, and validation command matches the App source. Establish the answer key
from source inspection, not from Graphify output.

See [Task authoring](task-authoring.md).

## 4. Configure the paired benchmark

```bash
python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" configure \
  --treatment-mode forced_graphify_skill_cli \
  --graphify-skill-source /absolute/path/to/graphify-skill \
  --graphify-graph-source "$PWD/graphify-out/graph.json" \
  --tasks-dir "$PWD/benchmarks/graphify/tasks" \
  --results-dir "$PWD/benchmark-results/graphify" \
  --model claude-opus-5 \
  --reasoning-effort medium
```

`claude-opus-5` with medium reasoning is the exact configuration used for the
included Adempiere runs. Keep the same model and reasoning effort in every
control and treatment condition.

This writes `.graphify-benchmark.json` in the App checkout and pins the current
App commit. Do not change the commit, tasks, graph, model, or configuration
between conditions.

## 5. Run free validation

```bash
python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" doctor
python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" preflight
```

`preflight` creates disposable worktrees and verifies that only treatment can
discover the Graphify skill and graph. It does not prompt a model.

## 6. Run the paid pilot

Review the task contracts and expected cost before continuing:

```bash
python3 "$HARNESS_ROOT/scripts/graphify_benchmark.py" run --pilot
```

The pilot runs the first analysis task and first implementation task in both
conditions.

## 7. Read the output

The timestamped result directory contains:

- `REPORT.md`
- `report.json`
- `runs.csv`
- `manifest.json`
- one artifact directory for every control and treatment run

Compare correctness and validation first. Then compare wall time, AIC, tokens,
files inspected, searches, Graphify calls, and failures. Higher AIC can be
worthwhile when it produces a measurably better implementation or prevents
missed dependencies.

## Recommended first App tasks

1. Change a shared component, state contract, API type, or authorization
   decision with consumers across several modules.
2. Implement a bounded real change whose success is enforced by the App build,
   tests, and targeted structural assertions.

Do not start with exact-string lookup. Graphify has little plausible advantage
for purely lexical tasks.
