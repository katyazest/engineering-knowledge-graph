## Context

Plane task `EKG-40` (`187aacee-af3b-4965-b936-15962dc50523`) makes explainability a graph contract: facts need source identity/revision, observation time, useful content hash, extractor identity/version, and derivation rule when they are derived. The repository already has `SourceArtifactIdentity`, payload-safe locators, evidence IDs, deterministic merge, persistence, local queries, and cross-graph evidence references. Those mechanisms establish part of the boundary but do not provide a uniform first-class provenance record or chain for all external and derived facts.

The change is wholly in project-owned modules. Provider adapters normalize identity-level inputs; Graphify, Jira MCP, Bitbucket MCP, OpenLore, and LadybugDB are not changed or called to resolve provenance. No source or provider content is retained.

## Goals / Non-Goals

**Goals:**
- Make complete, immutable, payload-free provenance independently addressable and linkable from facts and evidence.
- Preserve external observation and derived-rule chains deterministically across merge, validation, persistence, query, and cross-graph records.
- Preserve canonical fact, source-artifact, and cross-graph-claim identity contracts while providing guarded legacy compatibility.

**Non-Goals:**
- Store, retrieve, or reconstruct source bodies/provider payloads from their hashes.
- Define provider response models, query external systems, create semantic links, add derivation rules, or change trust lifecycle policy.
- Infer a missing timestamp, hash, extractor version, rule, or input provenance from filesystem state, names, current time, or content.

## Decisions

### 1. Add an immutable, separately persisted `ProvenanceRecord`

Introduce an ontology value object/record collection that is referenced by evidence and, through existing evidence IDs, by nodes, edges, cross-graph observations, and lifecycle entries. Its common immutable fields are `kind` (`external` or `derived`), source-artifact ID plus retained source revision for external observations, `observed_at`, `content_hash_algorithm`, `content_hash`, `extractor_id`, and `extractor_version`. Derived records also carry `derivation_rule_id` and sorted `input_provenance_ids`; derived records retain the deterministic input representation's hash, extractor identity/version for the derivation producer, and its observation/production instant.

The stable provenance ID is a field-delimited canonical serialization of these immutable fields. External observations of the same artifact at distinct instants or content fingerprints intentionally remain distinct provenance records. `SourceArtifactIdentity` remains the authoritative artifact identity; `content_hash` is a fingerprint for explainability and change detection, not a source identity or navigable locator.

Alternative: expand `Evidence` only. Rejected because evidence is a fact-support container and cross-graph records already reference evidence; an independently addressable provenance collection enables one provenance record to explain multiple facts and explicit derived-input chains without duplicating metadata.

### 2. Normalize and validate provenance before graph construction

Adapters/extractors construct external provenance after source-artifact identity validation and before producing evidence. The useful content hash is computed from the adapter's permitted useful source representation before it is discarded, using an explicitly supported algorithm (initially SHA-256) and a lowercase hexadecimal digest; only algorithm and digest are retained. The adapter supplies an offset-aware UTC/offset ISO-8601 observation time plus its stable extractor ID/version. Provider models remain outside the ontology.

Derivation builds a derived provenance record from the configured rule ID, sorted existing input provenance IDs, and deterministic local input representation. A derived output with absent/invalid input provenance is rejected rather than given a synthetic external observation. Input provenance remains referenced, not copied.

Alternative: let persistence fill provenance or use write time. Rejected because it makes facts depend on pipeline order/current clock and permits partial graph output.

### 3. Preserve associations and enforce consistency centrally

Extend `GraphSnapshot` with a deterministically ordered provenance collection and add provenance-ID references to evidence (or an equivalent evidence-to-provenance association serialized in the canonical snapshot). Keep node/edge evidence references unchanged, so canonical fact IDs and consumer traversal remain stable. Merge indexes provenance by stable ID, coalesces equivalent records, unions compatible references in sorted order, and deterministically rejects immutable conflicts or dangling associations.

`validate_graph_integrity` becomes the shared enforcement point for ID recomputation, required fields, allowed external/derived combinations, hash/timestamp format, payload-safe values, fact/evidence associations, and derived input chains. Persistence calls this validation before committing; query entry points retain their existing optional validation behavior.

Alternative: duplicate provenance fields in every node/edge/cross-graph record. Rejected because it causes drift, complicates conflict handling, and unnecessarily copies provenance across the graph.

### 4. Thread provenance through persistence and migration atomically

Extend the local persistence schema with provenance records and stable ordering. Readers recognize the current representation and, for historical snapshots, use a dedicated migration adapter: migrate only if all required provenance fields already exist in retained authoritative metadata and their IDs can be recomputed. Rewrite evidence/provenance associations and cross-graph provenance references together, validate the candidate snapshot, back up the prior graph, and atomically replace it. Missing fields yield a deterministic diagnostic/integrity failure; neither current time nor source content is used to fill them.

Alternative: permissive migration with placeholder values. Rejected because placeholders falsely claim explainability and violate EKG-40 completeness.

### 5. Expose provenance through local query DTOs and cross-graph references

Query serialization resolves fact evidence to its provenance records and returns only stable IDs, validated identity/revision, timestamps, hash algorithm/digest, extractor metadata, derivation rule, and input-provenance IDs in deterministic order. The existing recursive payload-field sanitizer remains a defense in depth; provenance's strict schema is the primary admission barrier.

Cross-graph candidate observations and lifecycle records continue to refer to evidence, whose complete provenance association forms the explanation chain. No source bodies, provider responses, source code, code intelligence, or hash preimages are copied into cross-graph records. Cross-graph claim identity and lifecycle/trust semantics remain unchanged.

Alternative: add duplicate provenance fields to `CrossGraphLinkEvidence`. Rejected because it would make cross-graph records an authoritative payload store and permit divergence from supporting evidence.

## Data Flow

`provider-normalized identity-level input` → `SourceArtifactIdentity` + external `ProvenanceRecord` validation → `Evidence`/canonical fact association → `GraphSnapshot` merge and integrity validation → local persistence/readback → query DTO or cross-graph provenance reference.

`validated canonical input provenance` → `deterministic derivation rule` → derived `ProvenanceRecord` with input IDs → derived edge/evidence association → same merge/persist/query path.

## Risks / Trade-offs

- [Existing fixtures and stores lack observation/hash/extractor metadata] → migrate only complete records; add explicit invalid-legacy fixtures and retain backup/rollback behavior.
- [Hashing useful source representations can be ambiguous across providers] → hash the normalized, extractor-defined useful representation before discard; retain algorithm and extractor version so results are explainable, never compare raw provider payloads in the canonical model.
- [Provenance collection increases snapshot size and query joins] → deduplicate by stable ID and use deterministic in-memory indexes; no source content is stored.
- [Stricter admission can break current internal/generated evidence] → apply complete-contract requirements only to external and derived records; preserve explicitly classified internal fixture/review records without falsely labeling them external observations.

## Migration Plan

1. Add provenance schema, stable ID, validators, and model-level verification matrix tests.
2. Update project-owned source adapters/extractors and derivation to emit complete external/derived provenance before graph construction.
3. Add graph merge/integrity validation and cross-graph association checks; verify canonical fact and claim IDs are unchanged.
4. Extend persistence serialization/readback and guarded atomic migration; test complete migration, incomplete failure, backup, and repeated read/write.
5. Extend query DTOs and cross-graph query coverage; test payload-free deterministic explanation chains.
6. Roll back a failed persisted migration by restoring the pre-migration backup. No partial provenance migration is committed.

## Open Questions

None.
