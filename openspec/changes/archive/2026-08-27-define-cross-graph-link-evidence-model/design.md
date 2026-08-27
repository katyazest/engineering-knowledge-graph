## Context

Plane task `98f0f78a-5d98-40b2-8cd2-21d6b924c201` (`EKG-09`) introduces the data contract required before any EKG-to-OpenLore linking strategy can be implemented. The current in-memory `GraphSnapshot` contains nodes, node-to-node edges, and generic evidence. `CodeLocator` already provides the correct four-part stable reference to code, but an `Edge` cannot point at a locator without inventing a code node that Engineering KG does not own.

OpenLore remains the authority for code graph, symbol resolution, and semantic analysis. Engineering KG must therefore preserve only a code locator and attributable observations, rather than query OpenLore or copy its facts. The model must permit deterministic local persistence and validation alongside legacy snapshots that do not contain cross-graph records.

## Goals / Non-Goals

**Goals:**

- Model a stable, proposed relationship from one existing EKG fact to a `CodeLocator` target.
- Keep candidate observations, lifecycle history, and the trusted semantic-link view distinct and auditable.
- Attribute each observation to an opaque linking-strategy identifier and existing provenance evidence.
- Support deterministic snapshot merging, local persistence/readback, integrity validation, and tests without a live OpenLore service.

**Non-Goals:**

- Implement a linker, semantic extraction, scoring/threshold policy, automatic trust promotion, or lifecycle-authorisation workflow.
- Resolve `CodeLocator` values; create OpenLore code nodes; call OpenLore, Graphify, or any external service; or persist source code or OpenLore analysis payloads.
- Treat candidates as ordinary `Edge` records, add public query/MCP operations, or retrofit existing extraction stages to emit links.
- Define business ownership or permitted human/agent actors for lifecycle changes; the task provides no such policy.

## Decisions

### Decision: Use three immutable canonical record families plus a derived trusted view

Add the following frozen ontology records and corresponding `GraphSnapshot` collections:

- `CrossGraphLinkClaim`: immutable link identity: `subject_id`, non-empty `relation_kind`, and `target: CodeLocator`. Its ID is `stable_id("cross-graph-link", subject_id, relation_kind, repository, revision, file, symbol)`.
- `CrossGraphLinkEvidence`: immutable observation: `claim_id`, non-empty opaque `strategy_id`, and `provenance_evidence_id` referencing a normal `Evidence` record. Its stable ID additionally includes an explicit observation identity supplied by the producing strategy; it does not include lifecycle or display content.
- `CrossGraphLinkLifecycle`: append-only state entry: `claim_id`, positive integer `revision`, one of the four specified states, and `provenance_evidence_id`. Its ID derives from claim ID and revision. The current state is the unique entry with the greatest revision.

Expose `trusted_cross_graph_links` as a deterministic projection of claims whose current lifecycle state is `trusted`; this value has the semantic relation, EKG subject, `CodeLocator` target, and supporting evidence IDs. It is deliberately not stored as an `Edge`, because no canonical code node exists at the OpenLore end of the relationship.

Rationale: separating the immutable claim from evidence and state histories allows observations to accumulate and state to change without a merge conflict or a false semantic edge. A projection gives consumers an explicit trusted-only surface.

Alternative considered: attach a `CodeLocator` to a normal edge property. Rejected because it would require a fabricated target node, would blur candidate and trusted state, and would weaken endpoint validation. Alternative considered: store candidates as generic `Evidence` only. Rejected because generic evidence has no stable semantic claim identity or lifecycle aggregation.

### Decision: Define IDs and provenance without strategy-specific schema

The relationship kind and strategy identifier remain validated non-empty strings, not a closed enum. Strategies provide their own opaque observation identity, while provenance is a required reference to an existing generic `Evidence` object. This permits manual, deterministic, heuristic, or future external-adapter strategies without provider models entering the ontology.

Rationale: EKG-09 establishes a model, not a set of linking algorithms. Stable IDs are based only on canonical identity fields; revisions, evidence volume, labels, and source-code positions cannot change a claim ID.

Alternative considered: predefine strategies such as `manual` and `openlore`. Rejected because the Plane task requests support for future strategies and does not define their vocabulary or behaviour.

### Decision: Lifecycle is append-only, explicit, and not a promotion engine

Each claim must have at least one lifecycle entry. Revisions are positive and unique per claim; records are sorted by claim ID then revision, and the greatest revision is current. Persistence and validation reject missing claims, missing provenance evidence, duplicate conflicting revisions, non-positive revisions, and unknown state values. They do not impose a transition matrix or infer trust from evidence count, confidence, or strategy.

Rationale: lifecycle history preserves attribution and provides deterministic updates. A transition-policy matrix would be product governance not present in the normalized task; an append-only revision history permits future policies without rewriting the evidence model.

Alternative considered: mutate a status field on the claim. Rejected because snapshots merge by stable ID and would either lose audit history or create conflicts on a legitimate promotion.

### Decision: Extend snapshot, persistence, and validation at the canonical boundary

`GraphSnapshot.as_dict`, JSON serialization, counts, and `merged_with` will include claims, observations, and lifecycle entries in stable-ID order. Merge coalesces identical records, unions compatible evidence and lifecycle histories, and rejects immutable-record conflicts. The integrity validator will add duplicate, claim-reference, provenance-reference, lifecycle-revision, target-completeness, and trusted-projection checks, with deterministic diagnostics and counts.

The LadybugDB-compatible JSON adapter will add three record maps and order arrays. Missing new keys in an existing valid graph file read as empty collections; write/read validates the new shapes and continues applying the existing forbidden-payload scan. No database migration is required because the adapter owns a JSON schema with additive absent-key defaults; malformed supplied cross-graph sections fail rather than being silently discarded.

Rationale: the existing ontology, persistence, and integrity-validation boundaries own graph shape and idempotence. The change must not create a parallel file format or an adapter-specific model.

### Decision: Preserve existing pipeline and API behaviour

No pipeline stage emits link records in this change. Existing extractors and derivation continue producing only their current facts. The trusted projection is an ontology-level collection/property for future callers; no query or MCP contract changes are introduced.

Rationale: this limits EKG-09 to the requested foundation and prevents a strategy or external dependency from being implied by the model.

## Risks / Trade-offs

- [Consumers may mistake raw claims for trusted relationships] → Keep candidates outside `Edge` and expose a named trusted-only projection; test that candidate/rejected/superseded claims do not appear in it.
- [Unbounded evidence/lifecycle histories increase snapshot size] → Store only locator identity and evidence references, maintain deterministic ordering, and defer retention policy until a producer has a demonstrated volume requirement.
- [A future actor needs transition governance] → Preserve an append-only attributed history now; add an explicit authorization/transition policy only with a future product requirement.
- [Legacy or hand-edited graph files may omit/add malformed sections] → Default absent additive sections to empty, validate present sections strictly, and retain existing atomic write behaviour.
- [Provenance evidence might itself contain prohibited data] → Reuse the persistence forbidden-field scan and avoid strategy payload fields in the new models.

## Migration Plan

1. Add and test ontology records, stable-ID helpers, snapshot collections, serialization, merge, and trusted projection.
2. Extend graph-integrity validation and deterministic diagnostics/counts for the new collections.
3. Extend persistence serialization/deserialization and merge/readback; verify legacy graph JSON loads with empty cross-graph collections and new invalid data is rejected.
4. Run focused unit tests plus the full existing test suite. Rollback is code rollback: legacy files remain valid because no destructive on-disk migration is performed.

## Open Questions

- The task does not define who may create lifecycle revisions or which lifecycle transitions are authorised. This plan deliberately stores ordered states without an authorisation or transition-policy API.
- The task does not name semantic relationship-kind vocabulary. This plan treats it as an opaque non-empty canonical string; a controlled vocabulary requires a separate requirement.
