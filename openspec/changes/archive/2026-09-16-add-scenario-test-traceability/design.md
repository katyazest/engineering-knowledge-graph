## Context

Plane task EKG-49 (source backlog item EKG-26; dependent on EKG-25) follows EKG-48's source-neutral verification ontology. The current graph can represent `TEST_CASE`, `TEST_RUN`, `VERIFICATION_EVIDENCE`, `VERIFIED_BY`, and `EXECUTED_IN`, but no component turns an OpenSpec declaration into those facts. As a result, the graph cannot distinguish a requirement/scenario with no declared test from one whose declared test simply has no represented run. It also has no scoped producer for supplying a reliable test-to-code observation to the cross-graph candidate model.

The existing implementation already has the necessary generic graph primitives: verification natural-key helpers; evidence and first-class provenance; catalog-valid verification edges; generic `CrossGraphLinkClaim`/observation/lifecycle records; persistence of those collections; and snapshot-backed query traversal. The OpenSpec extractor has authoritative validated-store and Git-revision context, while the pipeline can merge an optional local graph-producing stage before persistence and validation. The OpenLore bridge is deliberately a compact provider port and the repository has no Graphify adapter implementation, test runner, test-report adapter, CI client, or test-system integration.

## Goals / Non-Goals

**Goals:**

- Establish one deterministic, inspectable declaration convention for mapping OpenSpec requirements/scenarios to stable source-neutral test identities.
- Materialize only explicit mappings and explicitly observed executions using the existing verification ontology and provenance rules.
- Make mapping absence and missing execution separately queryable for every mapped test.
- Accept an exact, evidence-backed test-to-code result from reliable tooling as an observed cross-graph candidate without making implementation or coverage claims.
- Keep the feature local, payload-free, idempotent, reusable outside scripts/MCP wrappers, and compatible with a graph containing no traceability data.

**Non-Goals:**

- Looking for tests by test name, requirement/scenario wording, paths, filenames, conventions, AST heuristics, LLM inference, repository scanning, or source similarity.
- Running tests; parsing arbitrary framework/CI reports; collecting test output; deciding pass/fail, freshness, coverage, or completeness; or adding CI/test-framework/Graphify/OpenLore network calls.
- Extending the OpenLore bridge or implementing Graphify. A future integration may adapt a reliable tool into the normalized code-resolution input defined here.
- Creating an `IMPLEMENTS` claim, trusted implementation projection, reverse relation, test result interpretation, or verification truth from test mappings, executions, or code candidates.
- Adding a persisted-store migration, rollback, backup, schema revision, new public CLI, or new MCP tool.

## Decisions

### 1. Use one versioned mapping sidecar inside the validated OpenSpec root

Use the optional file `openspec/test-traceability.yaml` as the sole declaration source. Its version-1 records select an OpenSpec target by `capability`, normalized requirement heading, and, for scenarios, normalized scenario heading; each record declares one or more `{verification_scope_id, test_case_key}` pairs. Requirement and scenario selectors reuse the same normalized-heading and stable-ID functions used by OpenSpec extraction, so selection resolves against the in-memory result of the same validated-store extraction rather than a file path, display text, or post-hoc search.

The approved document shape is deliberately small:

```yaml
version: 1
mappings:
  - target:
      capability: payments
      requirement: Payment is submitted
      scenario: Valid payment # omit to map the requirement itself
    tests:
      - verification_scope_id: payment-service
        test_case_key: acceptance-payment-submit
```

`target`, `target.capability`, `target.requirement`, and non-empty `tests` are required; `target.scenario` is optional. The parser normalizes the heading selectors exactly as the existing OpenSpec identity helpers do, then rejects fields outside this shape. A repeated normalized target/test pair coalesces only when it is otherwise identical; any conflicting duplicate fails the delta.

The parser will reject the whole traceability delta on an unsupported version, unknown fields, malformed scalar/list shapes, unsafe verification identity, a selector resolving to zero or multiple targets, a scenario selector lacking a requirement selector, or a duplicate declaration that is not byte-for-byte compatible after normalization. The mapping file is optional: absence yields an empty delta and is the only source of an `unmapped` status. This makes malformed declarations fail visibly rather than being silently reclassified as no mapping.

Each declaration receives its own `OpenSpecLocator`/`SourceArtifactIdentity` based on the validated repository revision, `openspec/test-traceability.yaml`, the artifact type `openspec-test-traceability`, and a payload-safe mapping identity derived from its selector and test natural key. Its evidence and external provenance refer to the mapping file but retain neither YAML bodies nor test/provider payloads. The mapping source is identified from this evidence provenance, not an extensible verification edge property: EKG-48 deliberately forbids properties on verification-involved edges and evidence.

**Why:** A single sidecar gives authors a readable, source-controlled declaration without changing OpenSpec heading syntax or relying on undocumented Markdown conventions. Exact canonical target resolution and evidence-scoped classification make both mapping provenance and the absence result deterministic.

**Alternatives considered:**

- Inline Markdown comments or headings: rejected because they introduce an undocumented OpenSpec grammar, complicate requirement-versus-scenario ownership, and invite formatting-dependent parsing.
- Test discovery or naming patterns: rejected because EKG-49 explicitly says similarity is insufficient evidence.
- Mapping by generated canonical hash ID: rejected because it is not authorable or stable as an OpenSpec authoring convention; selectors map deterministically to the existing canonical IDs instead.

### 2. Add a reusable traceability-admission module while reusing generic verification records

Add a project-owned module such as `engineering_kg.ingest.scenario_test_traceability` with frozen, payload-safe input/result DTOs and one pure admission operation. A narrow OpenSpec source helper will locate the sidecar and provide its validated-store evidence context, while this optional-stage module parses/selects its declarations against the supplied OpenSpec extraction result and accepts caller-supplied normalized execution and code-resolution inputs. It returns a `GraphSnapshot` delta and deterministic counts/diagnostics. It will create test cases through `verification_node`, runs through the same verification identity factory, declaration edges as `VERIFIED_BY`, and execution edges as `EXECUTED_IN`.

The module will expose distinct DTOs for:

- a resolved mapping declaration read from the sidecar;
- an execution observation with the test scope/key, run key, exact source-artifact identity, observation instant, content hash, and extractor identity/version; and
- a test-to-code resolution with the mapped test scope/key, exact complete `CodeLocator`, payload-safe resolver/observation identifiers, declared `static-reachability` or `runtime-execution` basis, and complete source identity/evidence/provenance input.

The public normalizers reject arbitrary provider dictionaries and construct source evidence/provenance before graph facts. The execution input deliberately contains no result/outcome or coverage field. Execution admission references a test that the mapping delta has admitted; it does not manufacture standalone test facts for an unknown execution. Execution identity is therefore a represented fact, not an implicit implication from the mapping declaration.

**Why:** EKG-48 already supplies stable test/run IDs, validation, persistence, and query paths. A narrow adapter creates a single input boundary and avoids new provider-specific models or a new storage collection.

**Alternatives considered:**

- Add separate canonical mapping and execution record collections: rejected because the graph already expresses target-to-test and test-to-run facts with cataloged relationships, provenance, and deterministic IDs.
- Store status/outcome/coverage properties on a test case or run: rejected because an execution observation establishes only execution presence and EKG-48 excludes outcome/coverage semantics.
- Treat every externally supplied test execution as relevant: rejected because the task is target traceability; unknown tests cannot establish scope without a declared mapping.

### 3. Make reliable test-to-code resolution an observed `REFERENCES` candidate, never an implementation relation

The admission module will accept a code result only after the caller/integration has reduced a reliable tool result to exactly one complete revision-qualified `CodeLocator` for an already mapped test. It will create a `CrossGraphLinkClaim` with the test case as subject and `REFERENCES` as its relation kind, an observed/untrusted `CrossGraphLinkEvidence` with strategy ID `reliable-test-code-resolution`, and a derived candidate lifecycle provenance record that cites the input's external provenance. The input's `static-reachability` or `runtime-execution` basis remains an admission classification used to select/validate the adapter route and is not a free-form canonical payload field.

No result is emitted for a zero/multiple target resolution, unavailable tool, malformed context, missing source/provenance, or a locator whose repository/revision does not exactly match the supplied reliable result. The core accepts normalized results only and never invokes Graphify, OpenLore, or a test runner. A future local Graphify/OpenLore/coverage integration is responsible for using its own provider port, resolving its own response, and calling this boundary only with the compact exact result.

**Why:** The generic cross-graph model already represents auditable, attributed candidates to `CodeLocator`s. `REFERENCES` accurately states an observed association without claiming that the code is implemented, covered, passed, or trusted.

**Alternatives considered:**

- `IMPLEMENTS` from a test to a code locator: rejected by EKG-48 and the evidence-trust boundary; tests do not prove production implementation.
- A trusted `VERIFIED_BY` code claim: rejected because it conflates the explicit target-to-test mapping with code evidence and bypasses existing lifecycle boundaries.
- Store reachability/call graph or test output in EKG: rejected because code intelligence and reports remain owned by their source/tool boundaries.

### 4. Derive query status from evidenced graph facts, per mapping

Extend `EngineeringKgQuery` with a reusable traceability-status projection for a known `REQUIREMENT` or `SCENARIO`; no script, CLI, or MCP surface is added. It identifies mapping edges strictly by `VERIFIED_BY` endpoint shape plus the `openspec-test-traceability` evidence artifact type and complete provenance. For every identified test case, it finds catalog-valid, fully provenanced `EXECUTED_IN` edges and returns the test ID, mapping edge/evidence/provenance references, sorted run IDs, and an `executed`/`not-executed` state. It returns `unmapped` only when no valid mapping edge exists.

The projection separately includes only observed candidate claims using the `reliable-test-code-resolution` strategy for those mapped test IDs; all ordinary cross-graph projection rules continue to expose lifecycle and trust disposition. It does not interpret a candidate as an ordinary semantic edge. An unknown/non-target node uses the existing missing/not-found behavior rather than an invented status.

**Why:** The state is a deterministic read model over represented facts. Per-test state avoids the common false conclusion that a target is fully executed when only one of several mappings has a run.

**Alternatives considered:**

- Store a mutable aggregate coverage/status field on requirements/scenarios: rejected because it becomes stale, hides individual mappings, and cannot retain source evidence.
- Return a boolean `covered`: rejected because it conflates no declaration, missing execution, execution presence, outcomes, and coverage.

### 5. Add an optional pipeline stage; preserve persistence format and default behavior

When configured, `scenario-test-traceability` runs after `openspec-store-source` and `openspec-graph-extraction`, before persistence, derivation, and integrity validation. `run_pipeline` will accept the normalized execution/code-resolution DTO collections as explicit function inputs and return stage metadata (admitted mapping count, execution count, emitted candidate count, non-emission counts, and payload-safe diagnostics). The stage’s graph delta is merged only after parsing and input admission succeed; malformed sidecar input or invalid caller input produces no stage delta.

The change reuses existing nodes, edges, evidence, provenance, cross-graph claims, observations, and lifecycle collections, and does not change their serialized fields, relationship endpoint sets, or catalog revision. The relationship catalog only adds source-mapping table entries; it does not alter persisted relationship shape. Therefore persistence read/write requires no migration and existing revision-4 snapshots remain readable. A snapshot without the new data remains exactly compatible.

**Why:** A configurable graph-producing stage gives deployments a clear input boundary and ordering while retaining the current no-stage/default pipeline behavior. Reusing the generic persisted schema avoids an unapproved breaking revision for an additive source adapter.

**Alternatives considered:**

- Fold mapping admission into the base OpenSpec extraction stage unconditionally: rejected because execution and code-resolution inputs are optional external boundaries and should not make ordinary OpenSpec extraction depend on them. The stage instead uses an OpenSpec source helper only when `scenario-test-traceability` is configured.
- Persist before traceability admission: rejected because the stage must contribute one validated graph before persistence/readback and later integrity validation.
- Advance the catalog/persistence revision: rejected because no serialized canonical relationship or record format changes; source-mapping registration is adapter behavior, and an unapproved store-breaking migration is unnecessary.

## Affected Components and Data Flow

```text
validated OpenSpec store
  -> OpenSpec requirements/scenarios + validated Git revision
  -> openspec/test-traceability.yaml parser and exact selector resolution
  -> TEST_CASE + declared VERIFIED_BY edge (OpenSpec evidence/provenance)

caller-supplied normalized execution observation
  -> TEST_RUN + TEST_CASE EXECUTED_IN TEST_RUN (external evidence/provenance)

caller-supplied normalized exact code-resolution observation
  -> TEST_CASE REFERENCES CodeLocator candidate
  -> observed/untrusted support + candidate lifecycle

all deltas
  -> GraphSnapshot merge -> existing persistence/readback -> derivation
  -> integrity validation -> local scenario-to-test query projection
```

Affected project-owned modules are the OpenSpec source helper, the new traceability admission module, relationship source-mapping table, graph validation, pipeline result/order validation, and query DTO/traversal tests. The generic ontology and persistence codec are used but need no new serialized type or migration.

## Risks / Trade-offs

- **[Mapping authors omit a declaration]** → Query reports `unmapped`; it never guesses from a similar test name. A later approval may add linting/completeness policy, but this change does not invent one.
- **[A mapped test has no supplied execution]** → Query reports `not-executed` per test; no failure/outcome/coverage claim is made.
- **[A resolver calls an association reliable but returns incomplete/ambiguous context]** → Normalization rejects it and emits no candidate. Reliability is bounded by exact identity, provenance, and singleton-result contracts at this repository boundary, not by trusting a provider payload.
- **[Consumers mistake a code candidate for production proof]** → Use only observed/untrusted `REFERENCES` with candidate lifecycle; preserve `IMPLEMENTS` prohibition in catalog, validation, and query regression tests.
- **[New mapping parser alters ordinary OpenSpec extraction]** → Keep the file optional and place mapping admission in an optional stage; absence preserves existing output.
- **[Additional status traversal costs increase]** → Query uses bounded in-memory edge/claim lookup and deterministic sorting; it performs no source, network, tool, or code graph read.

## Migration Plan

1. Add the mapping parser/DTOs and local fixture sidecar, then verify selector and provenance behavior in isolation.
2. Implement graph-delta admission for mappings, executions, and candidate code resolutions, reusing the current revision-4 generic persistence format.
3. Register source mappings, add integrity checks, then add the optional pipeline stage and deterministic metadata.
4. Add the query projection and matrix regression coverage across admission, merge, persistence/readback, validation, pipeline, and query boundaries.
5. Existing stores require no migration. To disable or roll back use of the capability, remove `scenario-test-traceability` from the configured pipeline stages and/or the sidecar; existing generic graph data remains readable. Records already written by a valid run remain ordinary revision-4 graph facts and do not require a rewrite.

## Open Questions

None. The task does not provide an approved test-outcome, coverage, freshness, or completeness policy; those behaviors are intentionally excluded rather than decided implicitly.
