# Adempiere Graphify benchmarks

This repository contains reproducible reports from Graphify evaluations against
the open source [Adempiere](https://github.com/adempiere/adempiere) repository.

## Reports

- [Forced Graphify skill and CLI benchmark](reports/adempiere-forced-skill-cli-2026-09-18/)
  compares four source-analysis tasks with and without forced Graphify usage.
- [Structural graph-native follow-up](reports/adempiere-structural-graph-native-2026-09-18/)
  evaluates multi-entry execution paths and transitive inventory blast-radius
  analysis.

Each report includes its exact prompts, grading contract, metrics, provenance,
limitations, and machine-readable summary.

## Main findings

- Graphify did not improve objectively graded answer correctness in this sample.
- It was useful for reverse dependency and high-fan-in blast-radius discovery.
- It reduced file exploration substantially during the shipment impact task.
- The undirected graph was not reliable for executable shortest-path tracing.
- Graphify results should guide source verification rather than replace it.

The repository contains reports and task definitions only. It does not include
Adempiere source code, generated answers, raw session logs, graph data, or
credentials.
