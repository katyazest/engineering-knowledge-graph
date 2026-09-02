## 1. Canonical catalog and schema

- [x] 1.1 Add the immutable versioned relationship catalog, canonical kinds, directed endpoint alternatives, cardinalities, classifications, and source-mapping records. Verify deterministic serialization exactly covers `TRACES_TO`, `IMPLEMENTS`, `VERIFIED_BY`, `TOUCHES`, `DEPENDS_ON`, `REFERENCES`, `OWNED_BY`, `PROVIDES`, and structural `CONTAINS`.
- [x] 1.2 Refactor ontology edge and trusted-cross-graph models to consume catalog validation while retaining `ASSERTS` only as non-semantic OpenSpec derivation support. Verify catalog-valid unchanged relationships retain stable IDs and candidate lifecycle/evidence does not affect identity.
- [x] 1.3 Add catalog verification-matrix unit tests for valid endpoint pairs, reversed/disallowed endpoints, missing/invalid kinds, `OWNED_BY` cardinality, complete `CodeLocator` targets, and deterministic error codes without external infrastructure.

## 2. Extraction and derivation

- [x] 2.1 Update OpenSpec extraction to emit `CONTAINS`, asserted traceability support, and non-confident `REFERENCES` according to the source mapping. Verify fixture extraction never emits unsupported semantic kinds from OpenSpec metadata.
- [x] 2.2 Update PR changed-symbol candidate extraction to create candidate `TOUCHES` claims with complete provenance and no trusted edge. Verify merged-PR fixtures produce candidate-only output and candidate/rejected/superseded states are absent from trusted projections.
- [x] 2.3 Gate graph derivation through catalog admission and preserve only valid derived `TRACES_TO` output. Verify invalid kind, endpoint, cardinality, or provenance inputs are skipped with deterministic diagnostics while valid repeated derivation is idempotent.

## 3. Validation, persistence, and projections

- [x] 3.1 Extend graph-integrity validation to check catalog kind, direction, endpoint kinds, cardinality, support classification, and trusted cross-graph projections before persistence/query. Verify each invalid matrix case returns an error diagnostic and valid candidate records are not counted as semantics.
- [x] 3.2 Ensure persistence and readback admit only the current catalog-valid canonical relationship representation. Verify canonical-format round trips preserve kinds, ordered endpoints, and stable identities deterministically, and invalid non-canonical records fail with deterministic diagnostics without conversion.
- [x] 3.3 Update local query/projection DTOs to expose catalog-valid trusted relationships separately from support and candidate records. Verify serialization is deterministic and remains payload-free.

## 4. Documentation and complete verification

- [x] 4.1 Publish the canonical relationship reference and source-mapping/verification matrix from the catalog or a tested synchronized document. Verify the published reference states semantics, direction, endpoint kinds, cardinality, mappings, current canonical-format persistence/readback behavior, and trust boundary.
- [x] 4.2 Document the durable EKG-38 greenfield constraint in `docs/engineering-kg-project-constraints-mvp.md` and the canonical relationship reference: EKG has no historical deployment or persisted graph data, and compatibility, migration, backup, or rollback work requires a future explicit requirement supported by concrete evidence of pre-canonical data. Verify the reference and verification-matrix rationale state this boundary without adding compatibility behavior.
- [x] 4.3 Run focused ontology, extraction, derivation, validation, persistence, candidate-evidence, and query tests plus the full pytest suite. Verify no test requires Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, or network access.
