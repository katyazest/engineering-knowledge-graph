## Context

The Engineering KG MVP pipeline is local-first and deterministic. Current stages can load the workspace registry, validate workspace OpenLore and OpenSpec sources, extract OpenSpec graph facts, and persist/read back canonical `GraphSnapshot` data through an adapter-compatible LadybugDB boundary. The documented MVP sequence places deterministic derivation and validation after persistence merge/readback and before reusable API, script wrappers, and MCP query wrappers.

The current Python shape already has clear boundaries:

- `engineering_kg.ontology` owns canonical nodes, edges, evidence, locators, deterministic IDs, and snapshot serialization.
- `engineering_kg.persistence` owns adapter-compatible graph persistence and readback integrity.
- `engineering_kg.pipeline` owns stage ordering and deterministic run metadata.
- `engineering_kg.ingest.*` modules own source-specific extraction and validation.
- `scripts/build.py` delegates to `run_pipeline`; `scripts/derive.py` exists but is currently empty.

This change should extend those boundaries rather than introduce a new runtime, external service, or storage API.

## Goals / Non-Goals

**Goals:**

- Derive deterministic relationships from canonical graph snapshots after source graph facts are merged and, when configured, persisted/read back.
- Validate graph integrity before downstream query wrappers or consumers use the graph.
- Report derivation and validation metadata deterministically through `PipelineResult.as_dict()`.
- Keep derived facts traceable to existing source evidence or explicit derivation metadata without embedding source bodies, OpenLore analysis details, or generated storage records.
- Preserve existing bootstrap, registry-only, source-validation-only, extraction-only, and persistence behavior when the new stages are not configured.
- Make derivation and validation independently testable through reusable Python functions and pipeline-level tests.

**Non-Goals:**

- No semantic extraction, LLM reasoning, cloud calls, Jira/Bitbucket/Confluence fetching, OpenLore MCP queries, or generated documentation publishing.
- No replacement of the adapter-compatible LadybugDB persistence boundary with a native LadybugDB bridge.
- No inference of implementation ownership from manually maintained hints alone.
- No mixing of service-specific implementation logic across repositories.
- No destructive migration of existing local graph stores.

## Decisions

### Decision: Add dedicated graph processing modules

Create dedicated reusable modules for graph processing, for example:

- `engineering_kg.derivation` for `derive_graph_relationships(snapshot) -> GraphDerivationResult`
- `engineering_kg.validation` for `validate_graph_integrity(snapshot) -> GraphValidationResult`

Rationale: derivation and validation are graph-wide behavior, not source ingestion or persistence behavior. Keeping them separate prevents `pipeline.py` from accumulating graph business logic and keeps storage internals replaceable.

Alternative considered: put derivation and validation directly in `pipeline.py`. This would be faster initially, but it would make unit testing weaker and mix orchestration with graph rules.

### Decision: Derivation consumes and returns canonical snapshots

Derivation should consume a canonical `GraphSnapshot` and return a result containing:

- the derived or merged `GraphSnapshot`;
- deterministic metadata such as status, derived edge count, skipped relationship count, unresolved input count, and graph counts;
- optional diagnostics for derivation inputs that were present but not sufficient to create a relationship.

Derived edges should use `stable_id()` with explicit identity parts: edge kind, source node ID, target node ID, and derivation rule ID where needed. Output order should be deterministic by stable identity, not filesystem traversal side effects.

Rationale: callers, persistence, scripts, and future MCP wrappers should continue to depend on canonical graph contracts, not derivation-specific structures.

Alternative considered: emit only a list of derived edges. That would make reuse harder because callers would need to duplicate merge behavior and metadata accounting.

### Decision: Use explicit derivation rules for MVP relationships

The MVP should implement a small deterministic rule set rather than broad inference. Initial candidates are:

- connect OpenSpec change-scoped specs to durable specs for the same capability when both exist;
- connect active or archived changes to durable specs they touch when a durable spec target exists;
- preserve manually maintained `related` relationships as non-confident and do not upgrade them to authoritative traceability;
- derive only relationships whose source and target nodes already exist in the canonical snapshot.

Rationale: this gives useful traceability while respecting the existing source ownership rules. OpenSpec structure can prove OpenSpec-local relationships; OpenLore remains responsible for code graph details.

Alternative considered: derive service-to-requirement or code-to-requirement mappings from names and repository hints. That is too weak for deterministic MVP behavior and risks mixing service logic.

### Decision: Validation reports structured diagnostics and blocks later stages on errors

Graph integrity validation should return a deterministic result with:

- status: `valid` or `invalid`;
- diagnostics sorted by severity, rule ID, affected object ID, and message;
- counts by severity and graph counts;
- no source bodies, code, external payloads, credentials, or generated graph records.

Validation errors should stop later stages. Warnings may be reported without stopping the pipeline, but the MVP should start conservative: broken edge endpoints, duplicate canonical IDs with conflicting serialized values, missing evidence references, invalid traceability endpoints, and required unresolved references are errors.

Rationale: the user's core need is to detect broken links and invalid traceability before use. A structured result can be surfaced by scripts and future MCP wrappers without parsing free-form text.

Alternative considered: raise an exception for the first validation problem. That gives a hard failure but hides the full defect set from analysts.

### Decision: Pipeline stage order follows the documented MVP sequence

When configured, stage ordering should be:

`workspace-registry` -> source validation/extraction stages -> `ladybugdb-persistence` -> `graph-derivation` -> `graph-integrity-validation` -> future query wrappers.

If `graph-derivation` is configured without a graph-producing stage, it may run on an empty snapshot and report zero derived relationships. If `graph-integrity-validation` is configured, it validates the current snapshot after all prior configured graph mutations, including derivation. If persistence is configured, derivation runs on the readback snapshot.

Rationale: validation should check the graph that downstream users will actually consume. Running derivation after readback also catches persistence reconstruction issues before derived relationships are added.

Alternative considered: derive before persistence so derived edges are stored in the first write. The documented MVP sequence and persistence integrity contract favor deriving after readback; a later change can add a second persistence write for derived graphs if the storage lifecycle requires it.

### Decision: Keep script wrappers thin

`scripts/build.py` should continue to delegate to `run_pipeline` and only expose configuration inputs. `scripts/derive.py` can become a thin wrapper around derivation or the full pipeline when the implementation reaches script-wrapper tasks.

Rationale: script wrappers should not contain graph rules. This matches the existing build script pattern and keeps the reusable Python API authoritative.

Alternative considered: implement derivation as a standalone script first. That would duplicate pipeline configuration behavior and weaken stage-order guarantees.

## Risks / Trade-offs

- Derivation rules may be too conservative -> Prefer explicit unresolved/skipped metadata over speculative links; broaden rules only when specs define authoritative inputs.
- Validation may block useful exploratory runs -> Keep validation configurable by pipeline stage and make diagnostics complete enough to fix defects quickly.
- Derived graph data may need persistence later -> Keep derivation output as a canonical snapshot so a future stage can persist it without changing callers.
- Existing ontology edge kinds may be insufficient -> Add only minimal new edge kinds required by specs, and keep stable IDs compatible with existing serialization.
- Diagnostic messages can become non-deterministic -> Sort diagnostics and avoid embedding absolute runtime-only details unless they are already deterministic configured paths.

## Migration Plan

1. Add derivation and validation result models and reusable functions without enabling them by default.
2. Add delta specs for `graph-derivation`, `graph-integrity-validation`, and `pipeline-runner`.
3. Add focused unit tests for deterministic derivation and validation diagnostics.
4. Extend pipeline stage handling and `PipelineResult.as_dict()` metadata.
5. Extend script-level tests only after reusable behavior is stable.
6. Rollback is removing the new configured stages from `repo-index.yaml`; existing bootstrap, extraction, and persistence behavior remains unchanged.

## Open Questions

- Should the first MVP validation treat unresolved non-confident `related` frontmatter references as warnings or errors?
- Should derived relationships be persisted in the same run, or should the MVP keep them in the returned snapshot only until a later persistence lifecycle change?
- Which exact traceability relationship kinds should be canonical for OpenSpec change-to-durable-spec links: reuse existing OpenSpec edge kinds or add a more general traceability edge kind?
