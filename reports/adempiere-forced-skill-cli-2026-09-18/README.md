# Adempiere forced Graphify skill + CLI benchmark

**Result:** Graphify tied the control on all four tasks. All eight runs passed
their objective graders. Forced Graphify use reduced the heuristic unique-file
count from 47 to 38 and the summed wall time by 29.861 seconds, but increased AI
credits by 33.2% and total model-input tokens by 66.0%. Because all controls ran
before all treatments and each task ran once, the timing difference is not
causal evidence.

## Experiment record

| Field | Value |
|---|---|
| Target | [adempiere/adempiere](https://github.com/adempiere/adempiere) |
| Target commit | [`59557cc2ee85ac938cd4f31a246d891bc2b15b8f`](https://github.com/adempiere/adempiere/commit/59557cc2ee85ac938cd4f31a246d891bc2b15b8f) |
| Harness commit | [`3b046d6d3b5d6deb155033637bcb511296418463`](https://github.com/joshjohanning-org/squad-memory-demo/commit/3b046d6d3b5d6deb155033637bcb511296418463) |
| Result ID | `20260918T195005Z` |
| Treatment mode | `forced_graphify_skill_cli` |
| Model | `claude-opus-5` |
| Reasoning effort | `medium` |
| Copilot CLI | `1.0.86-2` |
| Repetitions | One per task and condition |
| Graph SHA-256 | `1b35f44b0060984e3a69382cec8ebaba78c564439dad9f975012e88c453d27c6` |
| Graph size | 219,914,487 bytes |
| Graph build overhead | 1,604.460 seconds, $0.00; excluded from run timing and cost |
| Graphify MCP | `graphify_adempiere` explicitly disabled in both arms; zero MCP status events and calls |

The original private artifact bundle remains outside git. Its conceptual layout
is `manifest.json`, `report.json`, `runs.csv`, and
`runs/<run-id>/{events.jsonl,tool-timeline.json,command.json,metrics.json,answer.json}`.
This directory preserves only reviewed, non-sensitive evidence:
[`summary.json`](summary.json) and the exact [task contracts](tasks/).

## Design

The four control runs executed first in task-file order, followed by the four
treatment runs in the same order. Every run used a clean detached worktree at
the pinned target commit and a unique Copilot session.

- **Control:** unchanged base prompt, no project Graphify skill, no
  `graphify-out/graph.json`, and Graphify MCP disabled.
- **Treatment:** the project Graphify skill and immutable read-only graph were
  staged only in the disposable worktree. The prompt prepended this
  preregistered instruction:

> Mandatory treatment instruction: Before using grep, ripgrep, find, glob,
> bash-based source search, or opening source files, invoke the staged Graphify
> skill and run at least one Graphify CLI query against the existing immutable
> graph at graphify-out/graph.json. Use the Graphify CLI output to choose
> subsequent source verification. Do not rebuild, update, cluster, or modify
> the graph. Then complete the unchanged task and return only its requested
> JSON.

Treatment validity required a discovered and successfully loaded project skill,
a hash-matching read-only graph, no Graphify MCP connection or call, and at
least one successful Graphify CLI invocation. Control validity required the
skill and graph to be absent, no MCP activity, and zero Graphify CLI calls. All
eight runs were valid.

## Exact prompts and grading

The verbatim source task definitions, including answer keys, weighted grader
targets, thresholds, regex criteria, and false-positive penalties, are:

- [`exact-db-connection-literal.json`](tasks/exact-db-connection-literal.json)
- [`java-process-contract-impact.json`](tasks/java-process-contract-impact.json)
- [`order-completion-state-flow.json`](tasks/order-completion-state-flow.json)
- [`routing-service-resolution.json`](tasks/routing-service-resolution.json)

The exact base prompts were:

1. **Exact database literal**

   > Determine every Java source location that uses the exact text `No Database
   > Connection` as a string literal. Exclude comments, partial matches, and
   > longer variants. Return only valid JSON with keys `occurrences` (an array
   > of objects with `path`, `class`, `method`, and `behavior`),
   > `total_occurrences`, and `excluded_near_matches`. Do not modify files.

   Objective threshold: 0.85. The grader required the two login servlet paths,
   `DB.java`, four named DB methods, and exactly six occurrences. It penalized
   `HttpServletCM` and `isPostgreSQL` false positives.

2. **Java process callback impact**

   > A proposed API change adds a checked exception to the callback contract
   > used to launch Java-backed application processes. Assess the direct source
   > impact across core, desktop, server, mobile, reporting, and utility code.
   > Return only valid JSON with keys `contract`, `direct_implementers`,
   > `launchers_by_module`, `reflection_path`, and `transaction_behavior`.
   > Distinguish direct interface implementers from subclasses that inherit an
   > implementation, and do not modify files.

   Objective threshold: 0.80. The grader required the contract, three direct
   implementers, launchers across desktop/server/servlet/mobile/model modules,
   and the reflection/commit/rollback path. It penalized claims that all
   `SvrProcess` subclasses directly implement the interface or that the
   callback is desktop-only.

3. **Order completion state flow**

   > A sales order is asked to complete but remains In Progress. Trace the
   > runtime path from the public order-model action request through the
   > document state engine and back into order preparation/completion. Explain
   > the valid reasons the result can be In Progress, Invalid, Waiting Payment,
   > or Completed, including validator hooks and the final status/action
   > mutation. Return only valid JSON with keys `ordered_flow`,
   > `state_selection`, `validator_hooks`, `outcomes`, and `evidence`; every
   > evidence item must contain a source path and symbol. Do not modify files.

   Objective threshold: 0.82. The grader required the `DocAction`,
   `DocumentEngine`, and `MOrder` paths; ordered prepare/complete flow; four
   validator timings; each requested outcome; successful mutation; and status
   writeback. It penalized direct `MOrder.processIt` to `MOrder.completeIt`,
   always-completed, and invalid-status explanations for Waiting Payment.

4. **Routing service resolution**

   > Explain how manufacturing code obtains the runtime service used to
   > estimate routing and work-center duration. Return only valid JSON with keys
   > `contract`, `implementation`, `factory_resolution`, and
   > `production_callers`. The contract and implementation must include source
   > paths and symbols; factory resolution must describe default selection,
   > client-specific fallback, construction mechanism, and caching; production
   > callers must include at least three distinct call sites with path, symbol,
   > and requested operation. Do not modify files.

   Objective threshold: 0.80. The grader required the contract, implementation,
   factory, implementation relation, reflective client-specific factory
   mechanism, and three production callers. It penalized Spring/ServiceLoader
   claims and direct production construction of `DefaultRoutingServiceImpl`.

### Hidden grader detail

All targets were matched against the answer artifact. The task JSON files linked
above are the authoritative verbatim contracts; this appendix makes their
hidden criteria reviewable in the report itself.

#### Exact database literal

- Expected occurrence count: **6**
- Expected paths (3):
  `serverApps/src/main/servlet/org/compiere/www/WLogin.java`;
  `org.compiere.mobile/WEB-INF/src/org/compiere/mobile/WLogin.java`;
  `base/src/org/compiere/util/DB.java`
- Expected symbols (6):
  `org.compiere.www.WLogin.doPost`;
  `org.compiere.mobile.WLogin.doPost`;
  `org.compiere.util.DB.getDatabase`;
  `org.compiere.util.DB.isOracle`;
  `org.compiere.util.DB.isMySQL`;
  `org.compiere.util.DB.isMariaDB`
- Objective threshold: **0.85**

| Target | Exact value or regex | Weight |
|---|---|---:|
| `server-login` | `serverApps/src/main/servlet/org/compiere/www/WLogin.java` | 1 |
| `mobile-login` | `org.compiere.mobile/WEB-INF/src/org/compiere/mobile/WLogin.java` | 1 |
| `db-utility` | `base/src/org/compiere/util/DB.java` | 1 |
| `get-database` | `getDatabase` | 1 |
| `oracle-check` | `isOracle` | 1 |
| `mysql-check` | `isMySQL` | 1 |
| `mariadb-check` | `isMariaDB` | 1 |
| `exact-count` | regex `"total_occurrences"\s*:\s*6` | 2 |

| False-positive regex | Penalty |
|---|---:|
| `"class"\s*:\s*"org\.compiere\.cm\.HttpServletCM"` | 0.15 |
| `"method"\s*:\s*"isPostgreSQL"` | 0.15 |

The answer key additionally identified `No Database Connection!` as an excluded
near match.

#### Java process callback impact

- Expected paths (10):
  `base/src/org/compiere/process/ProcessCall.java`;
  `base/src/org/compiere/process/SvrProcess.java`;
  `base/src/org/compiere/model/MPayment.java`;
  `JasperReports/src/org/compiere/jr/report/ReportStarter.java`;
  `base/src/org/adempiere/util/ProcessUtil.java`;
  `client/src/org/compiere/apps/ProcessCtl.java`;
  `base/src/org/compiere/process/ServerProcessCtl.java`;
  `serverApps/src/main/servlet/org/compiere/www/WProcessCtl.java`;
  `org.compiere.mobile/WEB-INF/src/org/compiere/mobile/WProcessCtl.java`;
  `base/src/org/compiere/model/MProcess.java`
- Expected symbols (9):
  `ProcessCall.startProcess`; `SvrProcess.startProcess`;
  `MPayment.startProcess`; `ReportStarter.startProcess`;
  `ProcessUtil.startJavaProcess`; `ProcessCtl.startProcess`;
  `ServerProcessCtl.startProcess`; `WProcessCtl.startProcess`;
  `MProcess.startClass`
- Objective threshold: **0.80**

| Target | Exact value or regex | Weight |
|---|---|---:|
| `contract` | `base/src/org/compiere/process/ProcessCall.java` | 2 |
| `svrprocess-implementer` | `base/src/org/compiere/process/SvrProcess.java` | 1 |
| `payment-implementer` | `base/src/org/compiere/model/MPayment.java` | 1 |
| `report-implementer` | `JasperReports/src/org/compiere/jr/report/ReportStarter.java` | 1 |
| `utility-launcher` | `base/src/org/adempiere/util/ProcessUtil.java` | 2 |
| `desktop-launcher` | `client/src/org/compiere/apps/ProcessCtl.java` | 1 |
| `server-launcher` | `base/src/org/compiere/process/ServerProcessCtl.java` | 1 |
| `servlet-launcher` | `serverApps/src/main/servlet/org/compiere/www/WProcessCtl.java` | 1 |
| `mobile-launcher` | `org.compiere.mobile/WEB-INF/src/org/compiere/mobile/WProcessCtl.java` | 1 |
| `model-launcher` | `base/src/org/compiere/model/MProcess.java` | 1 |
| `reflection-and-transaction` | regex `(?:getDeclaredConstructor\|newInstance\|reflect).*(?:startProcess).*(?:commit).*(?:rollback)` | 2 |

| False-positive regex | Penalty |
|---|---:|
| `(?i)(?:all\|every).*SvrProcess subclass.*direct(?:ly)? implements` | 0.20 |
| `(?i)only.*desktop` | 0.20 |

#### Order completion state flow

- Expected paths (3):
  `base/src/org/compiere/process/DocAction.java`;
  `base/src/org/compiere/process/DocumentEngine.java`;
  `base/src/org/compiere/model/MOrder.java`
- Expected symbols (7):
  `MOrder.processIt`; `DocumentEngine.processIt`;
  `DocumentEngine.prepareThenCompleteIt`; `DocumentEngine.prepareIt`;
  `DocumentEngine.completeIt`; `MOrder.prepareIt`; `MOrder.completeIt`
- Objective threshold: **0.82**

| Target | Exact value or regex | Weight |
|---|---|---:|
| `doc-action-contract` | `base/src/org/compiere/process/DocAction.java` | 1 |
| `engine-path` | `base/src/org/compiere/process/DocumentEngine.java` | 2 |
| `order-path` | `base/src/org/compiere/model/MOrder.java` | 2 |
| `ordered-flow` | regex `MOrder(?:\.processIt)?.*DocumentEngine(?:\.processIt)?.*prepareThenCompleteIt.*MOrder(?:\.prepareIt)?.*MOrder(?:\.completeIt)?` | 2 |
| `validator-hooks` | regex `TIMING_BEFORE_PREPARE.*TIMING_AFTER_PREPARE.*TIMING_BEFORE_COMPLETE.*TIMING_AFTER_COMPLETE` | 2 |
| `in-progress-reason` | regex `(?:DocAction\|document action).*(?:Prepare\|DOCACTION_Prepare).*(?:In Progress\|STATUS_InProgress)` | 1 |
| `waiting-payment` | regex `(?:prepay\|PrepayOrder).*(?:no payment\|C_Payment_ID.*0).*(?:Waiting Payment\|STATUS_WaitingPayment)` | 1 |
| `successful-mutation` | regex `setProcessed.*(?:true).*(?:DOCACTION_Close\|action.*Close).*(?:STATUS_Completed\|Completed)` | 2 |
| `engine-status-writeback` | regex `document\.completeIt.*document\.setDocStatus` | 1 |

| False-positive regex | Penalty |
|---|---:|
| `(?i)MOrder\.processIt.*directly calls.*MOrder\.completeIt` | 0.20 |
| `(?i)completion always (?:returns\|sets).*Completed` | 0.20 |
| `(?i)Waiting Payment.*(?:validation failure\|invalid status)` | 0.15 |

#### Routing service resolution

- Expected paths (6):
  `base/src/org/eevolution/model/RoutingService.java`;
  `base/src/org/eevolution/model/RoutingServiceFactory.java`;
  `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/model/impl/DefaultRoutingServiceImpl.java`;
  `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/process/CRP.java`;
  `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/model/MPPOrderNode.java`;
  `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/services/StandardCostCollector.java`
- Expected symbols (7):
  `RoutingService`; `RoutingServiceFactory`; `DefaultRoutingServiceImpl`;
  `RoutingServiceFactory.getRoutingService`; `CRP.doIt`;
  `MPPOrderNode.setQtyOrdered`; `StandardCostCollector`
- Objective threshold: **0.80**

| Target | Exact value or regex | Weight |
|---|---|---:|
| `contract-path` | `base/src/org/eevolution/model/RoutingService.java` | 1 |
| `implementation-path` | `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/model/impl/DefaultRoutingServiceImpl.java` | 1 |
| `factory-path` | `base/src/org/eevolution/model/RoutingServiceFactory.java` | 1 |
| `implementation-relation` | regex `DefaultRoutingServiceImpl.*implements.*RoutingService` | 1 |
| `factory-mechanism` | regex `(?:loadClass\|reflection\|reflective).*(?:newInstance\|instantiate).*(?:AD_Client_ID\|client)` | 2 |
| `process-caller` | `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/process/CRP.java` | 1 |
| `model-caller` | `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/model/MPPOrderNode.java` | 1 |
| `accounting-caller` | `org.eevolution.manufacturing/src/main/java/base/org/eevolution/manufacturing/services/StandardCostCollector.java` | 1 |

| False-positive regex | Penalty |
|---|---:|
| `(?i)Spring(?: Boot)? dependency injection\|ServiceLoader` | 0.20 |
| `(?i)production callers? (?:use\|call).*new DefaultRoutingServiceImpl` | 0.20 |

## Results

| Task | Control | Treatment | Wall seconds off/on | AIC off/on | Model input off/on | Files off/on | Graphify CLI | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Exact database literal | 1.0 pass | 1.0 pass | 41.855 / 42.933 | 26.493 / 36.275 | 98,781 / 270,370 | 6 / 4 | 1/1 successful | Broad graph neighborhood found `DB.java`, but exact grep supplied the decisive lexical evidence; low-yield for this task. |
| Java callback impact | 0.8 pass | 0.8 pass | 247.004 / 204.649 | 94.636 / 110.293 | 681,194 / 924,566 | 26 / 21 | 1/1 successful | Graph output surfaced `ProcessCall`, `SvrProcess`, and `startProcess` before verification; productive navigation with higher cost. |
| Order completion flow | 1.0 pass | 1.0 pass | 105.773 / 140.151 | 48.013 / 73.326 | 229,778 / 454,078 | 4 / 3 | 2/2 successful | Graph queries identified the core engine, model, action, and validator symbols, but truncated neighborhoods added time and context. |
| Routing service resolution | 1.0 pass | 1.0 pass | 97.893 / 74.930 | 35.076 / 52.076 | 213,016 / 380,150 | 11 / 10 | 1/1 successful | Clearest graph-guided case: factory, interface, implementation, and a duration call site led to direct source verification. |

Both Java callback runs found every expected target but received 0.8 because the
unchanged broad false-positive regex `only.*desktop` matched their otherwise
correct answers. This was symmetric and did not change the paired outcome.

### Aggregate

| Metric | Control | Graphify treatment | Treatment delta |
|---|---:|---:|---:|
| Objective passes | 4/4 | 4/4 | 0 |
| Mean correctness | 0.950 | 0.950 | 0 |
| Summed wall time | 492.524 s | 462.663 s | -29.861 s (-6.1%) |
| Summed Copilot session time | 482.885 s | 452.778 s | -30.107 s (-6.2%) |
| AI credits | 204.217600 | 271.969400 | +67.751800 (+33.2%) |
| Total model-input tokens | 1,222,769 | 2,029,164 | +806,395 (+66.0%) |
| Output tokens | 32,901 | 30,844 | -2,057 |
| Reasoning tokens | 3,779 | 3,681 | -98 |
| Graphify CLI calls | 0 | 5, all successful | +5 |
| Heuristic unique-file entries | 47 | 38 | -9 |
| Tool failures | 0 | 0 | 0 |

Actual suite elapsed time was 1,128.008 seconds. Across both conditions, the
eight sessions accumulated 955.188 seconds of wall time, 935.663 seconds of
Copilot session time, 476.187 AIC, 3,251,933 total model-input tokens, and
63,745 output tokens.

## Interpretation

This run demonstrates that the forced treatment was isolated and operational:
all treatment timelines loaded the project skill and issued successful Graphify
queries before ordinary source navigation, while controls had no skill, graph,
CLI use, or MCP access. Ordered timelines showed three productive or partially
productive uses and one largely decorative lexical use.

It does **not** demonstrate a correctness improvement. Both arms reached the
same scores, and treatment increased credit/context consumption materially.
The lower treatment wall time and file count are useful hypotheses for a larger
study, not conclusions.

## Limitations

- All controls ran before all treatments, confounding condition with cache
  warming, service variance, and time.
- There was one repetition per task and four pairs; no statistical inference is
  justified.
- Every run passed, creating a correctness ceiling.
- The treatment directive forced skill/CLI use; this measures enforced use, not
  spontaneous Copilot tool selection.
- Every Graphify neighborhood was broad and truncated.
- Shell-contained grep/find calls are undercounted by the broad/targeted search
  heuristic, and unique-file counts are approximate.
- The isolated empty `COPILOT_HOME` was necessary to avoid an existing
  disabled-by-name/global skill preference contaminating the experiment.
- No Graphify MCP was available in either arm, by design.
- This committed report omits raw prompts/events beyond the task contracts,
  model answers, session exports, logs, temporary worktree paths, and auth.

## Fair follow-up scenarios

These graph-native scenarios could reveal traversal value without presuming
Graphify will win:

1. **Persistence validation pipeline:** trace a model mutation through
   `beforeSave`/`afterSave`, model validators, document validators, and
   persistence side effects, grading exact order and alternate exits.
2. **Polymorphic accounting posting:** begin at an accounting contract and
   require concrete posting implementations, factory/dispatch selection,
   overridden methods, and downstream ledger mutations.
3. **Workflow execution propagation:** trace a workflow action through engine,
   process, document, callback, and status propagation paths, including failure
   and retry branches.
4. **Shipment/receipt transitive blast radius:** ask for the bounded transitive
   callers and affected document/accounting paths of a shipment or receipt API
   change, penalizing unrelated inventory code.
5. **Authorization high-fan-in paths:** identify all distinct production entry
   paths that converge on a shared role/access check, preserving module and
   caller context and detecting bypasses.
6. **Four-channel process-launch shortest paths:** require the shortest valid
   launch path from desktop, server, servlet, and mobile entry points to the
   shared callback, reflection, and transaction boundary.
7. **Generated-model inheritance/override analysis:** separate generated base
   models, handwritten subclasses, inherited behavior, and true overrides, then
   grade the exact impact of changing a generated method or field contract.

Each scenario should use multiple repetitions and counterbalanced condition
order, while retaining lexical negative controls where grep should remain
competitive.
