# Graphify forced skill + CLI Copilot CLI benchmark

- Treatment mode: `forced_graphify_skill_cli`
- Repository commit: `59557cc2ee85ac938cd4f31a246d891bc2b15b8f`
- Model: `claude-opus-5`
- Reasoning effort: `medium`
- Graphify MCP server disabled in both arms: `graphify_adempiere`
- Copilot CLI: `GitHub Copilot CLI 1.0.86-2.
Run 'copilot update' to check for updates.`
- Reproducible ordering seed: `20260918`
- Runs: `4`
- Forced treatment directive: `Mandatory treatment instruction: Before using grep, ripgrep, find, glob, bash-based source search, or opening source files, invoke the staged Graphify skill and use the existing immutable read-only graph at graphify-out/graph.json. For the shipment/receipt inventory blast-radius task, first run `graphify affected "MInOut.completeIt" --depth 4 --graph graphify-out/graph.json`; use additional `graphify affected` commands for specific mutation or dependency nodes when useful. For the multi-channel Java process-launch task, run `graphify path` for each of the four requested channels to the shared callback/convergence targets, for at least four successful path invocations total, using `--graph graphify-out/graph.json` and directed paths where supported. Do not use a broad `graphify query` unless an affected/path endpoint cannot be resolved; if endpoint discovery is necessary, use only a narrow query to resolve the exact node label and then return to `affected` or `path`. Use Graphify output to choose subsequent source verification. Do not rebuild, update, cluster, or modify the graph. Then complete the unchanged task and return only its requested JSON.`
- Graph setup SHA-256: `1b35f44b0060984e3a69382cec8ebaba78c564439dad9f975012e88c453d27c6`
- Graph setup size: `219914487` bytes
- Graph build duration (separate setup overhead): `1604.460` seconds
- Graph build cost (separate setup overhead): `$0.000`
- Phase-order limitation: All controls run first in task-file order, followed by all Graphify treatments in task-file order. This phase order is not counterbalanced and may confound condition with time/order.

## Correctness win/tie/loss

A Graphify win or loss is based only on objective pass and correctness score. Duration, credits, and tool-use metrics are reported separately.

| Graphify wins | Ties | Graphify losses | Invalid pairs |
|---:|---:|---:|---:|
| 0 | 0 | 2 | 0 |

## Task comparison

| Task | W/T/L/I | On pass rate | Off pass rate | On score | Off score | On median wall s | Off median wall s |
|---|---:|---:|---:|---:|---:|---:|---:|
| multi-entry-process-launch-paths | 0/0/1/0 | 0.0% | 0.0% | 0.450 | 0.800 | 272.559 | 192.916 |
| transitive-shipment-inventory-blast-radius | 0/0/1/0 | 0.0% | 0.0% | 0.500 | 0.700 | 312.810 | 563.502 |

## Category comparison

| Category | Condition | Valid/invalid | Pass rate | Mean score | Median wall s | Mean AI credits (nano) | Mean broad/targeted searches | Never found target |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| analysis | graphify_on | 2/0 | 0.0% | 0.475 | 292.685 | 145817175000.000 | 0.000/0.000 | 0 |
| analysis | graphify_off | 2/0 | 0.0% | 0.750 | 378.209 | 192265927500.000 | 2.000/22.000 | 0 |

## Raw runs

| Run | Task | Condition | Valid | Pass | Score | Wall s | MCP calls | CLI calls/success | CLI -> targeted follow-up | Files read | Failures |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| multi-entry-process-launch-paths-r01-graphify_off-p1 | multi-entry-process-launch-paths | graphify_off | yes | no | 0.800 | 192.916 | 0 | 0/0 | 0 | 14 | 0 |
| transitive-shipment-inventory-blast-radius-r01-graphify_off-p1 | transitive-shipment-inventory-blast-radius | graphify_off | yes | no | 0.700 | 563.502 | 0 | 0/0 | 0 | 98 | 9 |
| multi-entry-process-launch-paths-r01-graphify_on-p2 | multi-entry-process-launch-paths | graphify_on | yes | no | 0.450 | 272.559 | 0 | 3/3 | 0 | 15 | 0 |
| transitive-shipment-inventory-blast-radius-r01-graphify_on-p2 | transitive-shipment-inventory-blast-radius | graphify_on | yes | no | 0.500 | 312.810 | 0 | 6/6 | 1 | 13 | 1 |

## Metric cautions

- `graphify_targeted_follow_up_count` is a sequence heuristic: a configured Graphify tool call was followed within the configured window by a targeted search/read. It does not prove that Graphify caused or improved that action.
- Broad versus targeted search is classified using the regex rules recorded in the run manifest. Review the tool timeline before making causal claims.
- A Graphify-enabled run can connect successfully without invoking a Graphify tool. Connection status and invocation count are reported separately.
- Invalid treatment/control pairs are excluded from win/tie/loss and aggregate condition metrics rather than being counted as Graphify evidence.
- `graphify_cli_targeted_follow_up_count` is the corresponding heuristic for successful or failed CLI commands found only in shell tool arguments. It does not infer causality from output or answer text.

Machine-readable details are in `report.json`; flat raw metrics are in `runs.csv`; each run directory retains the source artifacts and ordered tool timeline.
