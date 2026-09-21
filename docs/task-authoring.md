# Task authoring

Each task is a JSON file. Both conditions receive the same base prompt. The
harness adds Graphify instructions only to treatment.

## Analysis task

Use analysis tasks for dependency impact, unfamiliar-code orientation, or
cross-module relationships.

Define:

- a prompt that describes the engineering question without mentioning
  Graphify or expected symbols
- exact expected paths and symbols
- ordered relationships when execution order matters
- objective weights and a pass threshold
- narrow false-positive rules

Do not use one broad regular expression across an entire JSON response. It can
accidentally connect unrelated sections. Prefer explicit path and symbol
targets or patterns anchored to one output field.

## Implementation task

Use implementation tasks to determine whether Graphify improves delivered code.

In addition to expected files and diff content, provide a deterministic
validation command:

```json
{
  "validation": {
    "command": "YOUR_BUILD_AND_TEST_COMMAND"
  }
}
```

Require validation success for objective pass. Add focused assertions for the
specific contract being changed instead of relying only on a broad test suite.

## Establishing the answer key

1. Inspect the source independently of Graphify.
2. Freeze expected paths, symbols, relationships, and validation commands.
3. Hash or commit task definitions before paid runs.
4. Do not revise the grader after seeing treatment output.
5. If a grader defect is discovered, preserve the original score and publish a
   separate audit.

## Selecting useful tasks

Strong Graphify candidates:

- transitive change impact
- reverse dependency analysis
- shared API or component migration
- interface implementations and callers
- high-fan-in architectural hubs
- cross-module implementation work

Weak candidates:

- exact string lookup
- one-file edits
- tasks where the prompt already names every relevant symbol
- execution-path questions when the graph lacks directed, typed call edges

The example files under `examples/tasks/` demonstrate the supported task
structure. Replace every placeholder before running a benchmark.
