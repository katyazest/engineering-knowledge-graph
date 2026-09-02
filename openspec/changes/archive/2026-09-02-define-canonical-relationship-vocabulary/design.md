## Context

Plane task `EKG-38` requires the relationship vocabulary to become an executable canonical contract rather than a set of incidental `EdgeKind` strings. Current project-owned models contain structural, semantic, source-scoped, and candidate labels in one enum. OpenSpec extraction produces `CONTAINS`, `ASSERTS`, `RELATED_TO`, and a source-specific artifact edge; derivation produces `TRACES_TO`; PR candidate extraction produces an `observed-pr-change` claim. Validation currently has only narrow traceability checks. Consequently the same relationship semantics can have multiple labels and candidate records can carry values that are not governed by canonical edge validation.

This affects only local Python schemas, extractors, derivation, validation, persistence/readback, DTO rendering, tests, and relationship documentation. Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, llmwiki-cli, and MkDocs are integration boundaries and are not modified or called. Existing first-class provenance and candidate lifecycle records remain the source of explainability and trust state.

## Goals / Non-Goals

**Goals:**
- Establish one versioned catalog containing semantic definitions, directed endpoint sets, cardinality, and source mappings for the EKG-38 vocabulary.
- Enforce the catalog uniformly for canonical semantic edges and trusted cross-graph links while retaining asserted support and candidate observations as non-semantic records.
- Make current extraction and derivation outputs conform, verify canonical-format persistence/readback, and publish a payload-free catalog reference.
- Preserve deterministic identities whenever an existing canonical kind and ordered endpoints do not change.

**Non-Goals:**
- Infer relationships from names, text, code, external payloads, or confidence scores; create provider adapters; or call external infrastructure.
- Define a trust actor, approval workflow, or automatic candidate promotion.
- Populate every catalog relationship from an existing source. `IMPLEMENTS`, `VERIFIED_BY`, `DEPENDS_ON`, `OWNED_BY`, and `PROVIDES` have no new producer in this change.
- Create inverse relationships, code nodes, source bodies, or provider-specific relationship models.
- Provide legacy compatibility, migration, backup, or rollback work. EKG has no historical deployment or persisted graph data; any future compatibility work requires an explicit approved requirement supported by concrete evidence of pre-canonical data.

## Decisions

### 1. Use a catalog object as the only semantic relationship authority

Add an immutable internal catalog (for example `relationship_vocabulary.py`) keyed by the canonical enum values. Each entry includes a human-readable semantic definition, directed node-to-node and node-to-`CodeLocator` endpoint alternatives, maximum target cardinality, and classification. The catalog has nine entries: the eight Plane-requested semantic kinds plus existing structural `CONTAINS`; its data is exported into the repository relationship reference and test fixtures in deterministic order.

`ASSERTS` is retained as a non-semantic source-support record for the existing OpenSpec derivation input, not as catalog truth. Candidate claims and observations remain separate graph collections. This avoids conflating “an adapter observed/asserted this” with “the graph trusts this semantic fact.”

Alternative: retain a string enum and document values only. Rejected because extraction, derivation, validation, persistence/readback, and trusted-link projection would continue to have independent interpretation rules.

### 2. Normalize current source names at source boundaries and fail closed thereafter

Change OpenSpec artifact membership from `OPENSPEC_CHANGE_HAS_ARTIFACT` to `CONTAINS`; map `RELATED_TO` to non-confident `REFERENCES`; keep `ASSERTS` only as derivation support; and retain derived `TRACES_TO`. Change PR changed-symbol candidates from source-specific `observed-pr-change` to `TOUCHES`; they still start in `candidate` lifecycle state and do not create an edge.

`ASSERTS` is retained as support data. EKG is greenfield with no historical deployment or persisted graph data, so no legacy relationship aliases, reversed `OWNS` edges, or source-specific historical claims are accepted, migrated, backed up, or rolled back. A record outside the current canonical representation fails closed at the applicable admission or integrity-validation boundary. Compatibility work may be introduced only by an explicit future requirement supported by concrete evidence of actual pre-canonical data.

Alternative: accept aliases forever. Rejected because it makes the vocabulary non-canonical. Alternative: silently select an owner or reverse arbitrary edges. Rejected because that loses semantic certainty and is unnecessary without historical data.

### 3. Centralize admission and validation without leaking source types

Provide reusable catalog validation helpers accepting only canonical node kinds, relationship kind, ordered endpoints, and optional `CodeLocator`; source adapters supply normalized canonical records before invoking them. Extraction and derivation use the helper before emitting records. `validate_graph_integrity` performs the final complete-snapshot check: every semantic edge is catalog valid, asserted support has the restricted OpenSpec shape, a `TOUCHES`/other trusted cross-graph link has a catalog-valid subject and complete locator, and `OWNED_BY` has at most one distinct target per source.

Candidate, rejected, and superseded claims are validated for record integrity but excluded from semantic edge/trusted-link counts and projections. Only lifecycle `trusted` invokes catalog trusted-link validation. All rejection and skipped-output diagnostics use stable IDs and rule identifiers; no source content is retained.

Alternative: validate only writers. Rejected because persisted/merged records and future adapters could bypass source-specific writers.

### 4. Preserve provenance, determinism, and compatibility at serialization boundaries

Relationship IDs continue to use existing stable-ID construction from canonical kind, direction, endpoints, and existing explicit identity parts. Provenance/evidence stays outside identity. Catalog validation happens before persistence; merge remains ID-based and deterministic. Persist the catalog revision alongside graph metadata or schema metadata so readback verifies the current canonical representation, but do not copy the catalog into individual edges.

The local query/projection DTOs expose only catalog-valid semantic edges and trusted links, distinguish non-confident `REFERENCES`, and continue to expose candidate/evidence records separately. Existing no-cross-graph snapshots remain readable. Documentation is generated or maintained from the catalog and includes the approved verification matrix and the durable greenfield constraint; it contains no provider payloads.

Alternative: bake endpoint rules into every extractor/query. Rejected because changes would drift and consumers could observe invalid semantic relations.

## Data Flow

`normalized source input` → `source mapping table` → `asserted support, candidate observation, or catalog-valid semantic edge` → `snapshot merge` → `catalog/provenance integrity validation` → `persistence/readback` → `trusted semantic projection and documentation`.

For OpenSpec, hierarchy maps directly to `CONTAINS`; an evidenced `ASSERTS` support record feeds deterministic `TRACES_TO`; `related` maps to non-confident `REFERENCES`. For PR changed symbols, the source produces candidate `TOUCHES` claim plus evidence; only a later explicit trusted lifecycle revision permits trusted projection.

## Risks / Trade-offs

- [A persisted record is not in the current canonical representation] → fail validation/readback with stable diagnostics; no historical conversion is attempted. The approved verification matrix is anchored to the greenfield baseline: there is no historical deployment or persisted graph data. A compatibility, migration, backup, or rollback case is outside this revision's matrix and is a change candidate unless a future explicit requirement is supported by concrete evidence of pre-canonical data.
- [Broad endpoint catalog could accidentally bless future producer data] → source mapping remains explicit and unsupported inputs fail closed even when their kind is catalog valid.
- [Catalog/schema drift in docs] → derive or test documentation against the catalog and verification matrix.
- [Cardinality checks need whole-snapshot context] → enforce them centrally after merge and before persistence/query.

## Persistence and Readback

1. Introduce the catalog, validation helpers, documentation reference, and unit verification matrix.
2. Update ontology values, OpenSpec mapping, derivation, PR candidate extraction, trusted-link projection, and validation; cover valid and rejected matrix cases.
3. Persist only catalog-valid current canonical records and validate the complete snapshot on readback.
4. Verify deterministic canonical-format round trips and no automatic candidate trust using fixtures only. Record the greenfield baseline in `docs/engineering-kg-project-constraints-mvp.md` and the canonical vocabulary reference. No migration, backup, rollback, or compatibility path for historical aliases is required; such work requires a future explicit requirement supported by concrete evidence of pre-canonical data.

## Open Questions

None. The catalog intentionally specifies no source producer for the relationship kinds that EKG-38 names but current supported sources cannot prove.
