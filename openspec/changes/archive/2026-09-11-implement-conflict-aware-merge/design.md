## Context

Plane task `EKG-42` (source backlog item `EKG-06`) closes an integrity gap in the project-owned canonical graph merge path. `GraphSnapshot.merged_with` currently builds per-ID maps while merging record collections, unions selected support references, and has a special lexical selection for differing node display names. Persistence merges the current snapshot with the incoming snapshot and serializes the result into ID-keyed maps. Consequently, an implementation must ensure that a same-identity cohort is completely evaluated before a map, presentation preference, or later boundary can hide a conflicting assertion.

The completed dependencies provide fixed boundaries: EKG-37 defines source-artifact identity and EKG-41 defines declared/observed/inferred classification and trusted-projection eligibility. Neither defines a generic ranking among independently authoritative sources. This design therefore preserves those models and fails closed rather than inventing a source hierarchy.

Affected code is limited to project-owned Python ontology merge helpers, integrity validation, persistence, and tests. Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, and LLM providers remain external inputs/targets; no provider payload or external call is added.

## Goals / Non-Goals

**Goals:**

- Evaluate every same-identity assertion cohort before creating a merged canonical record.
- Preserve independently supplied source/evidence/provenance references through compatibility evaluation, coalesce only compatible records, and make valid repeated writes idempotent.
- Replace implicit display-name/order selection with deterministic, payload-free conflict outcomes and validation diagnostics.
- Prevent a conflict from being serialized, persisted, or exposed as a trusted fact.
- State the authority boundary precisely: EKG-41 authority affects only trusted cross-graph projection after a valid merge, not generic record conflict resolution.

**Non-Goals:**

- Define a ranking, scoring system, recency rule, or automatic winner among source types, source artifacts, revisions, trust dispositions, or confidence values.
- Redefine `SourceArtifactIdentity`, first-class provenance, EKG-41 classification/trust semantics, canonical stable IDs, or relationship vocabulary.
- Persist invalid conflict records, retain competing payload values, migrate historical data, modify external systems, or add a conflict-resolution UI/workflow.
- Treat a trusted lifecycle or an observed merged PR as permission to overwrite a conflicting canonical assertion.

## Decisions

### 1. Use a shared cohort evaluator before collection maps or serialization

Introduce one internal conflict-aware merge evaluator used by `GraphSnapshot` merge and validation. It buckets all left/right records by `(collection, stable ID)`, retains every candidate while comparing it, and only then emits a coalesced record or a conflict diagnostic. The evaluator will retain the existing permitted reference-union behavior for equivalent node/edge evidence IDs and evidence provenance IDs, using sorted unique references; immutable/non-reference fields must otherwise match.

Node display names are retained canonical record values in the current serialized contract. A difference is therefore an assertion conflict, not a reason to choose the lexical minimum. This deliberately removes the current special-case name selection. The evaluator covers nodes, edges, evidence, provenance, cross-graph claims, observations, lifecycle entries, and typed PR collections. After all collections are conflict-free, existing cross-collection reference checks run against the proposed merged snapshot.

An internal `GraphMergeConflictError` (a `ValueError`-compatible failure) will carry one or more normalized safe conflict descriptors. This preserves compatibility for callers already handling merge `ValueError` while giving persistence and pipeline code structured, deterministic diagnostics. The evaluator processes and sorts the full cohort/collection set before returning an aggregate failure, so reversed input order does not choose a different first error.

Alternative: retain the ID-keyed map and add a validation pass later. Rejected because the map or display-name preference can already have discarded a candidate before validation. Alternative: store every candidate as a persistent alternate fact. Rejected because EKG-42 requires conflict reporting before a value becomes a trusted canonical fact and does not authorize a user-facing conflict state or alternate-fact data model.

### 2. Compare asserted values strictly and keep safe references separate from payload values

The evaluator will derive a comparison view from each record's deterministic serialization: it removes only the existing mergeable reference arrays (`evidence_ids` for nodes/edges and `provenance_ids` for evidence) and compares all remaining retained values, including node `name`. It will not compare or publish source bodies. Equivalent values coalesce; different record types, retained properties, source-artifact identity, immutable provenance fields, classified-support fields, lifecycle state/revision/provenance binding, or presentation fields conflict.

The conflict descriptor contains only a stable rule ID, collection, canonical ID, and sorted contributor record/evidence/provenance IDs. It does not contain competing property values, raw locators beyond already admitted IDs, source/provider payloads, URLs, code, secrets, or tokens. The IDs are enough to join with admitted evidence/provenance in a local diagnostic context while retaining existing payload-free boundaries.

Alternative: compare only natural-key fields and let non-key fields choose a deterministic winner. Rejected because an independently asserted retained value would still be silently erased, and EKG-42 explicitly closes silent last-write-wins behavior.

### 3. Treat source authority as a scoped projection policy, not a merge precedence rule

EKG-41 already permits a trusted `IMPLEMENTS` projection only through qualifying declared authoritative support and an explicit trusted lifecycle decision. This implementation retains that behavior but makes projection contingent on a conflict-free graph. The trusted-link projector and validation-required query/persistence boundaries will not expose a trusted link if the shared conflict evaluator reports an unresolved cohort.

No generic canonical assertion receives a source-authority override in this change. In particular, source type, artifact identity/revision, observed-at time, declared/observed/inferred origin, authoritative/derived status, trust disposition, lifecycle state, confidence, support count, and arrival order cannot break a tie. This is the only conservative behavior supported by existing contracts: `authoritative` describes the status of an individual support record but does not rank two independent authorities. A future ranking or an explicit domain-specific resolution record requires a separately approved change.

Alternative: favor declared/authoritative/trusted records over observed or inferred records. Rejected because EKG-41 requires valid conflicting classified support to remain auditable and expressly prohibits source-precedence winner selection. Alternative: favor newest source revision or timestamp. Rejected because source revisions identify artifacts, not a cross-source canonical authority order.

### 4. Make validation diagnostic-only over direct snapshots and authoritative at trust/persistence boundaries

`validate_graph_integrity` will reuse the cohort evaluator in diagnostic mode for snapshots constructed directly with duplicate records. It will emit an error per unresolved cohort with deterministic safe references, preserve existing duplicate counts, and never synthesize a resolved object. Validation metadata will gain only structured payload-free conflict context; its existing status/severity behavior remains unchanged.

Trusted projection must consult the same result (or an equivalent conflict-free precondition), so a manually constructed invalid snapshot cannot use a dictionary lookup to turn a conflicting candidate into trusted truth. Validation-required local queries already reject an invalid graph; non-validation projection helpers must likewise return no trusted projection when a conflict is present. This avoids an ontology-to-validation import cycle by locating the shared conflict evaluator in the ontology/merge layer rather than in the validator.

Alternative: rely exclusively on persistence validation. Rejected because in-memory pipeline, direct query, and trusted-link projection paths may use a snapshot before persistence.

### 5. Preserve persistence format while making write replacement transactional with conflict evaluation

`LadybugDbStore.write_snapshot` will deserialize the existing canonical snapshot, use the shared `GraphSnapshot` merge evaluator with the incoming snapshot, validate the prospective result, and only then call the existing temporary-file-and-replace write path. A conflict becomes `PersistenceIntegrityError` carrying the safe diagnostic and leaves the current graph file unchanged. Serialization into ID-keyed maps occurs only after a successful conflict-free merge, eliminating overwrite as a conflict-resolution mechanism.

No catalog/schema revision or data migration is needed because this change adds no persisted canonical record field. Existing valid records remain readable and repeated compatible writes remain stable. A malformed legacy/current raw store that cannot be reconstructed continues to fail under the existing readback/integrity contract; the adapter must not fabricate candidates or persist a conflict collection.

Alternative: add a persistent conflict collection and expose the selected primary record. Rejected because it changes the canonical storage/query contract and introduces a resolution workflow not requested by EKG-42. Alternative: rollback by rewriting the prior snapshot after a failed write. Rejected because conflict detection happens before the atomic replacement, so no write occurs and the existing file is already preserved.

## Data Flow

`left snapshot + incoming snapshot` → `same-identity cohort evaluator` → `compatible reference union OR aggregate payload-free conflict` → `cross-collection reference checks` → `conflict-free GraphSnapshot` → `integrity validation / trusted projection eligibility` → `persistence temporary serialization and atomic replacement` → `readback/query`.

For direct invalid snapshots: `snapshot` → `cohort evaluator in diagnostic mode` → `invalid validation metadata` → no validation-required query, persistence write, or trusted projection. Existing declared-authoritative lifecycle rules are evaluated only after this conflict-free gate.

## Risks / Trade-offs

- [Existing callers/tests expect lexical node-name selection] → Treat the behavioral change as intentionally breaking; update fixtures to use compatible values or assert the deterministic conflict.
- [Full-cohort aggregation costs more than early map replacement] → Collections are local in-memory graph snapshots; group once per collection and sort only conflict descriptors/reference sets. Correctness and auditability take precedence over a micro-optimization.
- [Safe diagnostics can be less immediately descriptive without field values] → Include collection, canonical ID, and source/evidence/provenance references; users can inspect admitted payload-free provenance without leaking competing source content.
- [A future domain legitimately has two authorities with a known order] → Do not encode an ad hoc priority now; propose an explicit source-authority/rule contract with its own acceptance criteria.
- [Malformed direct objects bypass constructors] → Reuse serialization/admission validation and conflict evaluation at snapshot, validation, persistence, and projection boundaries; do not trust frozen dataclass construction alone.

## Migration Plan

1. Implement the shared cohort comparison/diagnostic primitives and replace implicit node-name/order selection in `GraphSnapshot` merge; preserve stable IDs and allowed reference unions.
2. Integrate diagnostic-mode cohort evaluation into graph integrity validation and conflict-free gating into trusted projection.
3. Route persistence write merge through the same evaluator before temporary serialization/replacement; retain the current file on all conflicts.
4. Update focused ontology, validation, cross-graph, and persistence fixtures for every verification-matrix row, including reversed ordering and payload-free diagnostics.
5. Run the complete local suite. No datastore migration or rollback is required: valid stores are unchanged, and a rejected write performs no replacement. Rolling back the code restores previous behavior only; it must not be used to accept a conflict rejected by this integrity contract.

## Open Questions

None. The absence of a generic source-authority ranking is an explicit fail-closed decision based on EKG-37/EKG-41; adding one is a future change candidate, not an implementation decision for EKG-42.
