# Graphify Copilot CLI benchmark

This repository provides a reusable paired benchmark for measuring whether a
Graphify integration improves GitHub Copilot CLI outcomes. It supports legacy
MCP-only, skill + MCP, and forced skill + local CLI treatments. Every run starts
from the same pinned Git commit.

The harness uses Python's standard library. Customers do not need to write or
run `jq`.

## Prerequisites

- Git
- Python 3.9 or later
- GitHub Copilot CLI, authenticated and available as `copilot`
- Access to the exact Graphify MCP server being evaluated for MCP modes
- A prebuilt `graphify-out/graph.json` and Graphify CLI for forced skill/CLI mode

The harness keeps all source, prompts, model responses, diffs, and logs local.
Do not upload benchmark artifacts when they may contain sensitive source or
prompt content.

## Discover and configure Graphify

List the MCP servers visible to Copilot CLI:

```bash
python3 scripts/graphify_benchmark.py list-servers
```

Use the exact server name shown by Copilot. The configuration command verifies
the server with `copilot mcp get`, resolves the repository ref to an immutable
commit SHA, and writes the ignored `.graphify-benchmark.json` file:

```bash
python3 scripts/graphify_benchmark.py configure \
  --graphify-server YOUR_EXACT_SERVER_NAME \
  --graphify-skill-source /ABSOLUTE/PATH/TO/graphify-skill \
  --model claude-opus-5 \
  --reasoning-effort medium
```

Configuration includes:

- exact Graphify MCP server name
- optional Graphify skill source directory; absolute paths are supported for
  benchmarking an external target repository
- pinned model and reasoning effort
- repetition count and reproducible ordering seed
- task and results directories
- pinned repository commit
- Graphify/search/read tool-name patterns
- broad and targeted argument-classification patterns
- repository paths excluded from both conditions to prevent control-arm access
  to committed Graphify outputs or skills

If Graphify's MCP tools do not contain `graphify` in their names, edit
`metrics.known_graphify_tool_names` or
`metrics.graphify_tool_name_patterns`. The harness does not assume a Graphify
tool schema.

When `graphify_skill_source` is unset or `null`, the harness preserves its
original MCP-only behavior.

### Forced Graphify skill + CLI mode

Use `forced_graphify_skill_cli` to compare ordinary Copilot against the project Graphify
skill and local Graphify CLI without exposing Graphify MCP in either arm. The
graph must be built before configuration; the harness verifies and copies it
but never rebuilds it during measured runs.

```bash
python3 scripts/graphify_benchmark.py configure \
  --treatment-mode forced_graphify_skill_cli \
  --graphify-server graphify_adempiere \
  --graphify-skill-source /ABSOLUTE/PATH/TO/graphify-skill \
  --graphify-graph-source /ABSOLUTE/PATH/TO/graphify-out/graph.json \
  --graphify-graph-build-duration-seconds 123.45 \
  --graphify-graph-build-cost-usd 1.23 \
  --model claude-opus-5 \
  --reasoning-effort medium
```

`--graphify-server` is optional in this mode. Supply the exact configured
Graphify MCP server name so the harness passes `--disable-mcp-server` in both arms. The mode
never enables that server, rejects any observed Graphify MCP connection/tool
call, and does not require `copilot mcp get` to succeed.

The default treatment-only directive is:

> You must use the Graphify skill and run Graphify CLI queries before using
> grep, find, glob, or reading source files. Use Graphify to identify the
> relevant symbols, relationships, and files, then verify them in source.

Override it with `--forced-graphify-directive`. Controls always receive the
unaltered task prompt.

Forced mode requires `repetitions=1` and deliberately runs all controls first,
in task-file order, then all treatments in the same order. This is not
counterbalanced, so the report records phase order as a limitation. The
prebuilt graph's SHA-256, byte size, and optional prior build duration/cost are
recorded as separate setup overhead and excluded from every run's metrics.

Validate configuration at any time:

```bash
python3 scripts/graphify_benchmark.py doctor
```

Before any paid benchmark, verify treatment-only skill isolation for free:

```bash
python3 scripts/graphify_benchmark.py preflight
```

The preflight creates disposable treatment and control worktrees, stages the
skill only at `.github/skills/<skill-name>` in treatment, and runs
`copilot skill list` without a prompt. It fails if treatment does not discover
the skill as a project skill, if control discovers it, or if an exact-name
personal/custom/plugin/builtin skill could contaminate either condition.
In forced mode it also hash-verifies a read-only treatment graph at
`graphify-out/graph.json` and verifies that the control has no graph.

On machines with a persisted disabled-by-name skill preference, use the same
empty isolated `COPILOT_HOME`, ephemeral authentication, and environment prefix
for `preflight`, `smoke`, and `run`; otherwise preflight intentionally fails
rather than silently contaminating the experiment.

## Quick start

After configuration, run the one-repetition pilot:

```bash
python3 scripts/graphify_benchmark.py run --pilot
```

Run the configured repetitions for all tasks:

```bash
python3 scripts/graphify_benchmark.py run
```

Limit a run to one or more task IDs:

```bash
python3 scripts/graphify_benchmark.py run \
  --task trace-trade-submission \
  --task add-repository-count
```

Run exactly one treatment-only smoke outside paired scoring:

```bash
python3 scripts/graphify_benchmark.py smoke \
  --task YOUR_TASK_ID \
  --confirm-paid-run
```

`smoke` requires the explicit acknowledgement because it invokes one Copilot
model session. It writes `SMOKE.md`, `smoke.json`, `manifest.json`, and the
normal run artifacts under `treatment-smoke-<timestamp>/`; it never enters
paired win/tie/loss summaries.

The pilot selects the first analysis task and first implementation task and
runs one on/off pair for each. A full benchmark uses every task and the
configured repetition count. Use the pilot to verify server naming, permissions,
task grading, and validation before spending credits on a full run.

## Equivalent paired runs

For every task repetition, the harness:

1. Uses the recorded seed to balance the Graphify-on/off first position
   globally across tasks. Repetitions alternate the first condition within each
   task, so four tasks with one repetition produce exactly two on-first and two
   off-first pairs; odd task counts differ by at most one.
2. Creates a new detached Git worktree at the pinned commit.
3. Marks configured Graphify artifacts as `skip-worktree` and removes them from
   both conditions without making the worktree dirty. This repository excludes
   `graphify-out/` and `.copilot/skills/graphify/` by default so the control arm
   cannot answer from the committed graph or project skill. Set
   `worktree_exclude_paths` to an empty array only when those files are an
   intentional part of both conditions.
4. When `graphify_skill_source` is configured, copies that skill only into the
   treatment worktree at `.github/skills/<skill-name>`. The control destination
   remains absent. Before the prompt, `copilot skill list` records and validates
   discovery for both arms.
5. Creates a unique Copilot session ID; sessions are never reused.
6. Runs Copilot with the pinned model/reasoning effort, `--no-ask-user`,
   `--allow-all-tools`, JSON output, usage output, debug logging, and remote
   export and CLI auto-update disabled.
7. Enables or disables only the configured Graphify server for the condition.
8. Captures repository changes and runs the task's validation command.
9. Removes the temporary worktree after copying artifacts into the ignored
   results directory.

In `forced_graphify_skill_cli`, steps 1, 4, and 7 are replaced by the preregistered
control-first phase order, treatment-only skill plus read-only graph staging,
and Graphify MCP disablement in both arms. The treatment prompt receives the
forced directive; the control prompt remains byte-for-byte equal to the task
prompt. Injected skill/graph files are excluded from source status/diff grading.

The condition order, configuration, metric rules, and task sources are recorded
in `manifest.json`. Each run also prepends a `harness.skill_status` event to
`events.jsonl` and records staging/discovery in `command.json` and
`metrics.json`.

Before any run starts, the manifest records `treatment_mode` as
`forced_graphify_skill_cli`, `skill_and_mcp`, or `mcp_only`. Existing configurations
without this field still derive the original MCP mode from
`graphify_skill_source`. `report.json` carries the same metadata and
`REPORT.md` uses a mode-specific title. This label is derived from
configuration, not outcomes.

## Task definitions and grading

Tasks are JSON files in `benchmarks/graphify/tasks/`. Prompts must describe the
customer problem without naming Graphify, expected tools, answer-key symbols,
or answer-key files.

Analysis/navigation tasks can define:

- expected paths, symbols, and ordered relationship regexes
- optional `metric_values` aliases used only to locate the first correct target
  in the tool timeline without weakening objective answer grading
- which artifacts are graded (`answer`, `events`, `diff`, or `status`)
- weighted targets and an objective pass threshold
- false-positive regexes and penalties

The `events` grading source searches the raw JSONL. Use it only when seeing a
target anywhere in tool output is itself valid evidence; it does not prove the
final answer used that evidence.

Implementation tasks add a validation command. Their score can combine expected
changes with the validation result, and objective pass can require validation
success. Validation runs inside the disposable worktree after Copilot exits.

The templates under `examples/tasks/` demonstrate both forms. They contain
placeholders and are not runnable until every path, symbol, relationship,
validation command, and false-positive rule is replaced with repository-specific
values.

## Captured artifacts

Each run writes:

- `final-answer.md`
- `events.jsonl`
- `usage.json`
- `session.md`
- `stderr.log` and `debug-logs/`
- `wall-time.json`
- `git.diff` and `git.status`
- `validation.log` and `validation.json` when configured
- `tool-timeline.json`
- `metrics.json`
- the exact task, base/effective prompts, command, session ID, and working directory

The report directory adds:

- `REPORT.md` for customers
- `report.json` for structured analysis
- `runs.csv` for spreadsheets and BI tools
- `manifest.json` for reproducibility

## Metrics and interpretation

The harness calculates correctness/pass, portable process wall time, Copilot
session duration, AI credits, token counts, Graphify MCP and CLI invocations,
search counts, unique files read, exploration before the first expected target,
and tool/model/MCP failures.

Broad and targeted search are configurable heuristics:

- **Targeted** means the search arguments match an expected task target or a
  configured file-path/symbol pattern.
- **Broad** means the arguments match a configured broad pattern, or the search
  lacks a targeted signal.

`graphify_targeted_follow_up_count` means a configured Graphify call was
followed within the configured tool-call window by a targeted search or read.
It is sequence evidence only. The report does **not** claim that Graphify caused
the later action merely because a grep/read followed it.

A treatment run is valid only when its final Graphify MCP status is
`connected`. When skill mode is configured, treatment must also stage and
discover the project skill, while control must not discover it. A control run
is valid only when Graphify is absent or `disabled`, no configured Graphify tool
was invoked, and the treatment skill is absent. Invalid pairs are retained in
raw artifacts but excluded from win/tie/loss and condition aggregates.

In `forced_graphify_skill_cli`, treatment validity instead requires the project skill,
the hash-verified read-only graph, no Graphify MCP connection/call, and at least
one successful `graphify query`, `path`, `explain`, `affected`, or `god-nodes`
command. Control requires no skill, no graph, no Graphify MCP activity, and zero
Graphify CLI commands. CLI calls are detected only from shell/bash/PowerShell
tool arguments, including absolute Graphify executable paths; answer or command
output text is never counted. Exact commands and completion success are retained
in `metrics.json`, with CLI-to-targeted-source follow-up reported separately.

`copilot skill list` proves that the skill was discoverable before the run. It
does not prove the model selected or applied the skill. Copilot does not expose
`session.skills_loaded` through a free, unprompted command, so
`graphify_skill_runtime_loaded` remains `null`; inspect prompted session/debug
artifacts when runtime selection matters.

Interpret Graphify behavior with the ordered timeline:

- **Productive:** Graphify identifies a relevant symbol/relationship, followed
  by a narrow source read or verification search, with equal or better objective
  correctness and reasonable cost.
- **Decorative:** Graphify is invoked, but its output is not followed by a
  relevant verification step or does not affect the answer.
- **Harmful:** Graphify introduces false positives, extra exploration/failures,
  lower correctness, or disproportionate latency/credit use.

Win/tie/loss compares objective pass first and correctness score second.
Performance and cost never break a correctness tie; they remain separate
trade-off metrics. Repeated paired runs are summarized by task, category, and
condition while retaining every raw run.

## Why CLI is the primary benchmark surface

Copilot CLI provides reproducible per-run MCP enable/disable controls, pinned
model/reasoning settings, unique session IDs, machine-readable JSONL events,
usage JSON, session Markdown, logs, and non-interactive execution. These make
paired automated measurement practical.

VS Code can be used as a manual validation surface. Run equivalent prompts in
Agent mode and inspect **Agent Debug Logs** for MCP connection state, tool
ordering, arguments, failures, and whether Graphify findings lead to targeted
source verification. Treat this as qualitative corroboration, not a substitute
for the CLI's controlled repeated benchmark.

## Optional OTEL file export

OTEL is off by default because native JSONL and usage JSON are sufficient. To
enable local file export, set `otel.enabled` to `true` in the configuration.
The harness sets `COPILOT_OTEL_FILE_EXPORTER_PATH` to the run artifact directory.

Capturing model message content is separately disabled. Setting
`otel.capture_message_content` to `true` enables
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`, which can record
prompts, responses, source excerpts, and other sensitive material. Enable it
only with explicit approval and appropriate local retention controls.

## Validate the harness

Run the standard-library harness tests:

```bash
python3 -m unittest discover -s tests/benchmark_harness -p 'test_*.py' -v
```
