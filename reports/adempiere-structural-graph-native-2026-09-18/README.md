# Adempiere structural graph-native benchmark

**Official generated result: 0 Graphify wins / 0 ties / 2 losses.**
The original harness output is preserved byte-for-byte in
[`generated-report.md`](generated-report.md).

**Audited correctness result: 0 wins / 2 ties / 0 losses.** A post-run grader
audit found that every false-positive penalty actually applied was caused by a
regex spanning unrelated sections of the structured JSON answers. Before those
penalties, target coverage was 1.000 versus 1.000 for process launch paths and
0.850 versus 0.850 for shipment blast radius. The generated 0W/0T/2L must
therefore remain part of the record but is invalid evidence for Graphify
effectiveness.

## Provenance

| Field | Value |
|---|---|
| Target | [adempiere/adempiere](https://github.com/adempiere/adempiere) |
| Target commit | [`59557cc2ee85ac938cd4f31a246d891bc2b15b8f`](https://github.com/adempiere/adempiere/commit/59557cc2ee85ac938cd4f31a246d891bc2b15b8f) |
| Harness commit | [`412195089ddcd6eade34a948e5c6ffdc3613e634`](https://github.com/joshjohanning-org/squad-memory-demo/commit/412195089ddcd6eade34a948e5c6ffdc3613e634) |
| Result ID | `20260918T204927Z` |
| Treatment mode | `forced_graphify_skill_cli` |
| Model command | `claude-opus-5`, medium reasoning |
| Copilot CLI | `1.0.86-2` |
| Paid runs | 4; no reruns |
| Graph SHA-256 | `1b35f44b0060984e3a69382cec8ebaba78c564439dad9f975012e88c453d27c6` |
| Graph size | 219,914,487 bytes |
| Graph setup overhead | 1,604.460 seconds, $0.00; excluded from run metrics |
| Graphify MCP | `graphify_adempiere` disabled in every run; zero MCP events/calls |

The compact machine-readable audit is [`summary.json`](summary.json). Exact
task definitions and frozen graders are in [`tasks/`](tasks/). Raw model
answers, events, session exports, logs, the 219 MB graph, temporary worktree
paths, and authentication material are intentionally not committed.

Frozen preregistration hashes:

| Input | SHA-256 |
|---|---|
| Benchmark config | `42c0018d45b3e8dfc5fe3ec294c12aa440da360b9157424c6ec387c4d9e68eff` |
| Process task | `9e2b3d910d0c698b9ae95e1000a406815e192abfb0f1b40590c0c2b23ce5eeb0` |
| Shipment task | `2428c6d7b73be8d15e36c4277f22124122a3e61fee5a9d66da35326f686130a8` |
| Gold answers | `085c762c2250acbb5920edaf8c83937213584a13b91a5fe8ec2b0e05d3fb1232` |
| Treatment directive | `25d836c7cc8d10aa77c6e09d2499153e2a95db4d55d24db39acaf0c06018171b` |
| Graphify skill tree | `805cfd5487d10d4bac6b7e4fef55ebde17ec8e5b2edad1d589697f75f1857205` |

## Experiment design

The preregistered order was:

1. Process launch paths, control
2. Shipment blast radius, control
3. Process launch paths, Graphify treatment
4. Shipment blast radius, Graphify treatment

Every run used a clean detached worktree at the pinned target commit and a
unique Copilot session.

- **Control:** unchanged task prompt; no Graphify skill, graph, forced
  directive, CLI calls, or MCP.
- **Treatment:** project Graphify skill plus immutable read-only
  `graphify-out/graph.json`; Graphify MCP disabled; task-specific directive
  required `graphify path` or `graphify affected` before ordinary navigation.
- **Validity:** the free preflight passed; frozen input hashes did not change;
  treatments loaded the project skill at runtime; controls had no skill or
  graph; no source files were modified.

The treatment directive required at least four path invocations for process
launch analysis and an initial
`graphify affected "MInOut.completeIt" --depth 4` for shipment analysis. A
narrow `graphify query` was allowed only to resolve an endpoint before returning
to the structural operation.

## Exact prompts and frozen graders

The following are the exact base prompts. The linked JSON files are byte-for-
byte copies of the frozen task inputs and contain the **full** answer keys,
expected paths and symbols, target regexes, weights, thresholds, metric aliases,
and false-positive penalties.

### Multi-entry process launch paths

> For desktop, server-thread, servlet, and mobile launches of a Java-backed
> application process, determine the shortest ordered source path from each
> channel's public launch entry to the ProcessCall callback and then to managed
> transaction commit, rollback, and close behavior. State one explicit
> edge-count convention, identify exact convergence and divergence nodes,
> distinguish shared utility reflection from channel-local reflection, and
> exclude remote-server, workflow, database-procedure, script, and
> reporting-fallback paths. Return only valid JSON with keys `edge_convention`,
> `paths_by_channel`, `path_lengths`, `convergence`, `divergence`, `reflection`,
> `transaction_outcomes`, `excluded_paths`, and `evidence`; every evidence item
> must contain a source path and symbol. Do not modify files.

Full contract:
[`multi-entry-process-launch-paths.json`](tasks/multi-entry-process-launch-paths.json)
(SHA-256 `9e2b3d910d0c698b9ae95e1000a406815e192abfb0f1b40590c0c2b23ce5eeb0`).

- Objective threshold: **0.84**
- Expected source paths: 6
- Expected symbols: 14
- Weighted targets: 11, total weight 20
- Target weights: callback 1; desktop 2; server 2; servlet 2; mobile 2;
  desktop/server convergence 2; shared reflection 2; servlet/mobile divergence
  2; managed transaction 2; path lengths 2; exclusions 1
- False-positive penalties: servlet/mobile through `ProcessUtil` 0.20;
  workflow/database/script reaching `ProcessCall` 0.20; remote-process path
  presented as local 0.15; all `SvrProcess` subclasses described as direct
  implementers 0.15

### Transitive shipment inventory blast radius

> A proposed refactor moves the inventory quantity mutation performed while
> completing a material shipment or receipt. Determine the exhaustive
> source-level change impact from the public document action through
> preparation and completion. Separate direct callees from transitive
> dependents and validator/observer hooks, identify module boundaries, and
> distinguish customer-shipment, vendor-receipt, confirmation, matching,
> downstream-document, and accounting consequences. Return only valid JSON
> with keys `entry_flow`, `direct_mutations`, `transitive_dependents`,
> `observers_and_hooks`, `conditional_branches`, `module_boundaries`,
> `false_positive_exclusions`, and `evidence`; every evidence item must contain
> a source path and symbol. Do not modify files.

Full contract:
[`transitive-shipment-inventory-blast-radius.json`](tasks/transitive-shipment-inventory-blast-radius.json)
(SHA-256 `2428c6d7b73be8d15e36c4277f22124122a3e61fee5a9d66da35326f686130a8`).

- Objective threshold: **0.82**
- Expected source paths: 11
- Expected symbols: 14
- Weighted targets: 12, total weight 20
- Target weights: document entry 2; shipment model 2; ordered flow 2;
  inventory mutation 3; order-line effects 1; RMA effect 1; confirmations 1;
  receipt matching 2; downstream documents 1; validator hooks 2; accounting
  boundary 1; branch distinction 2
- False-positive penalties: `createFrom` as inventory mutation 0.20;
  `Doc_InOut` as inventory mutation 0.20; material policy as final on-hand
  mutation 0.15; commented asset deactivation as active dependency 0.15;
  customer shipment creating receipt matching records 0.15

## Official generated result

This table is unchanged from the generated result:

| Task | Control score/pass | Treatment score/pass | Official outcome |
|---|---:|---:|---|
| Multi-entry process launch paths | 0.800 / fail | 0.450 / fail | Graphify loss |
| Shipment inventory blast radius | 0.700 / fail | 0.500 / fail | Graphify loss |

Official aggregate: **0W / 0T / 2L / 0 invalid**.

## Grader audit

The frozen task contracts were not changed and the generated report was not
rewritten. The audit separates weighted expected-target coverage from the
false-positive penalty layer.

| Task | Control pre-penalty coverage | Treatment pre-penalty coverage | Threshold | Audited outcome |
|---|---:|---:|---:|---|
| Process launch paths | 1.000 | 1.000 | 0.840 | tie; both pass |
| Shipment blast radius | 0.850 | 0.850 | 0.820 | tie; both pass |

### Why every applied penalty is an artifact

- **Process control and treatment:** the regex
  `(?:servlet|mobile)[\s\S]*ProcessUtil.startJavaProcess` crossed from the
  servlet/mobile JSON sections into a later desktop/server section. Both
  answers correctly stated that servlet and mobile do **not** use
  `ProcessUtil`.
- **Process treatment:** the workflow/database/script penalty crossed from the
  answer's explicit exclusions into a later correct `ProcessCall` discussion.
- **Process treatment:** the `DB.isRemoteProcess` penalty likewise crossed from
  an exclusion into later local callback material.
- **Shipment control and treatment:** the shipment-to-`MMatchInv`/`MMatchPO`
  regex crossed from a customer-shipment section into a later vendor-receipt
  section. Both answers explicitly described matching as receipt-only.
- **Shipment treatment:** the `Doc_InOut` mutation regex crossed from the
  downstream accounting section into a later inventory section. The answer
  explicitly said accounting consumes completed state and does not mutate
  stock.

Because these are all cross-section matches against correct distinctions, the
official W/T/L is invalid for effectiveness conclusions. The defensible audited
correctness result is **0W / 2T / 0L**.

## Per-task metrics

| Task | Arm | Audited target score | Wall | Session | AIC | Model input | Output | Files | Search B/T | Failures |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Process paths | Control | 1.000 | 192.916 s | 189.828 s | 96.721075 | 510,907 | 15,738 | 14 | 2/0 | 0 |
| Process paths | Treatment | 1.000 | 272.559 s | 269.572 s | 133.683175 | 1,050,967 | 18,858 | 15 | 0/0 | 0 |
| Shipment blast radius | Control | 0.850 | 563.502 s | unavailable | 287.810780 | 3,116,073 | 67,288 | 98 | 2/44 | 9 |
| Shipment blast radius | Treatment | 0.850 | 312.810 s | 310.795 s | 157.951175 | 1,568,509 | 17,159 | 13 | 0/0 | 1 |

### Aggregate metrics

| Metric | Control | Treatment | Treatment delta |
|---|---:|---:|---:|
| Summed wall time | 756.418 s | 585.369 s | -171.048 s (-22.6%) |
| AI credits | 384.531855 | 291.634350 | -92.897505 (-24.2%) |
| Total model-input tokens | 3,626,980 | 2,619,476 | -1,007,504 (-27.8%) |
| Output tokens | 83,026 | 36,017 | -47,009 |
| Reasoning tokens, all models | 6,808 | 6,326 | -482 |
| Heuristic unique-file entries | 112 | 28 | -84 |
| Broad/targeted search counters | 4/44 | 0/0 | -4/-44 |
| Tool failures | 9 | 1 | -8 |

Total benchmark usage was 676.166205 AIC, 6,246,456 model-input tokens,
119,043 output tokens, and 13,134 reasoning tokens. Actual suite elapsed time
was 1,429.517 seconds; summed run wall time was 1,341.787 seconds. Complete
session-time aggregation is impossible because the shipment control has no
session-duration telemetry.

## Graphify commands and behavior

Harness metrics count shell tool calls containing Graphify, not each CLI
process launched inside a loop. Process treatment records 3 CLI-containing
shell calls but launched 6 processes: 5 path traversals and one help command.
Shipment treatment records 6 shell calls but launched 19 processes: 17
traversals and two help commands.

Normalized process commands included:

```text
graphify path "ProcessCtl.startProcess" "ProcessCall.startProcess" --graph graphify-out/graph.json
graphify path "<desktop-node>" "<ProcessCall.startProcess-node>" --graph graphify-out/graph.json --directed
graphify path "<server-node>" "<ProcessCall.startProcess-node>" --graph graphify-out/graph.json --directed
graphify path "<servlet-node>" "<ProcessCall.startProcess-node>" --graph graphify-out/graph.json --directed
graphify path "<mobile-node>" "<ProcessCall.startProcess-node>" --graph graphify-out/graph.json --directed
```

The returned shortest paths were semantically unrelated reference/import
routes: desktop, servlet, and mobile traversed printing/payment nodes and
`MPayment implements ProcessCall`; server traversed a 15-hop
accounting/payment route. A calls-only direct BFS found no path for any channel.
Source verification rescued the final answer, but Graphify increased time by
79.643 seconds, AIC by 36.962100, model input by 540,060 tokens, and file
entries by one.

**Process classification: harmful guidance and operationally expensive.**

Normalized shipment commands included:

```text
graphify affected "MInOut.completeIt" --depth 4 --graph graphify-out/graph.json
graphify affected "<MInOut.completeIt-node>" --depth 4 --graph graphify-out/graph.json
graphify affected "<MStorage.add-node>" --depth 3 --graph graphify-out/graph.json
graphify affected "<MInOut.checkMaterialPolicy-node>" --depth 3 --graph graphify-out/graph.json
graphify affected "<MInOut.prepareIt-node>" --depth 3 --graph graphify-out/graph.json
graphify affected "<MInOut.processIt-node>" --depth 3 --graph graphify-out/graph.json
graphify affected "<StorageEngine.createTransaction-node>" --graph graphify-out/graph.json
graphify path "<candidate-entry>" "<MStorage.add-or-MInOut.completeIt>" --graph graphify-out/graph.json --directed
```

The natural-language `MInOut.completeIt` endpoint was ambiguous, and exact
reverse traversal surfaced only two test callers. The `MStorage.add` affected
traversal was productive: it exposed the direct `MInOut.completeIt` call and
high-fan-in callers across inventory, manufacturing, distribution, project,
cleanup, client, and test modules. Material-policy, preparation, and storage-
transaction reverse traversals also supplied useful leads. Directed paths
frequently returned no path, while undirected paths often represented imports
or references rather than execution.

**Shipment classification: productive but operationally mixed.** Treatment
inspected 13 file entries versus 98 in control, but the control anomaly makes
the dramatic time, cost, and token difference unsuitable for attribution.

## Control anomaly

The shipment control completed a final JSON answer and `assistant.turn_end`
before a terminal session-host error. It then had:

- 9 permission/terminal-host tool failures
- no session-duration telemetry or session export
- 37 internal `gpt-5.4-mini` requests in addition to 25 pinned
  `claude-opus-5` requests
- 48.723930 AIC attributed to those internal mini-model requests

The harness retained the completed answer and did not rerun it under the frozen
rerun policy. This means shipment timing, cost, token, failure, and file-count
comparisons are not model-pure or infrastructure-equivalent.

## Interpretation

The process-path experiment is the cleanest efficiency comparison. Graphify's
structural path results were misleading and expensive, while source
verification produced the same complete target coverage as control.

The shipment experiment shows credible navigation value from reverse
high-fan-in traversal and dramatically less file exploration. It cannot
establish efficiency gains because the control was affected by permission and
terminal failures, missing telemetry, and mixed-model internal requests.

Across both tasks, the audited evidence supports **two correctness ties**. It
does not support the generated two-loss conclusion, nor does it establish that
Graphify is generally beneficial or harmful.

## Limitations

- **Frozen grader defect:** cross-section regexes invalidated the generated
  W/T/L as an effectiveness conclusion.
- **Sample size:** two task pairs, one repetition each.
- **Phase order:** all controls preceded treatments, confounding condition with
  time, cache warming, and service variance.
- **Forced use:** treatment measured required Graphify use, not spontaneous
  Copilot routing.
- **Control infrastructure:** the shipment control had nine host failures,
  missing session telemetry, and 37 internal `gpt-5.4-mini` requests despite
  the pinned Claude command.
- **Graph directionality:** graph metadata is corpus-level `directed: false`.
  Requesting `--directed` cannot reconstruct missing source-level call
  direction and limits shortest execution-path fidelity.
- **CLI success semantics:** exit code 0 proves command completion, not a unique,
  relevant, or semantically correct graph result.
- **Call counting:** harness counts shell calls containing Graphify and
  undercounts processes launched inside loops.
- **Search/file heuristics:** shell-contained searches are undercounted and
  unique-file entries are approximate.
- **Setup overhead:** the reused graph took 1,604.460 seconds to build; that
  one-time cost is separate from treatment runtime.
