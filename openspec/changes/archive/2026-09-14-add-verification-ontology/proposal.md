## Why

EKG-48 requires verification facts to be navigable and auditable across the graph without coupling the canonical model to a test framework or CI vendor. The current ontology has `VERIFIED_BY` in its relationship vocabulary but no source-neutral test, run, or verification-evidence entities, so verification support cannot safely participate in traceability or cross-graph lifecycle decisions.

## What Changes

- Add a source-neutral verification ontology for `test-case`, optional `test-suite`, `test-run`, and `verification-evidence` facts, with deterministic identities and existing first-class provenance/evidence requirements.
- Define the directed verification relationships `VERIFIED_BY`, `EXECUTED_IN`, and `VALIDATES`, including their permitted endpoint kinds and provenance requirements.
- Extend cross-graph support records so an admitted verification-evidence fact can be cited as auditable support for a verification claim without changing claim identity or automatically promoting any claim.
- Preserve the strict implementation-trust boundary: a test/test-code association or verification evidence is not an `IMPLEMENTS` assertion and cannot independently produce trusted implementation truth.
- **BREAKING** Advance the versioned canonical relationship/persistence format for the expanded ontology and relationship catalog. Persisted data at an earlier catalog revision remains rejected rather than silently converted; no historical verification-data migration has been approved.
- Do not add a test-framework adapter, CI-vendor adapter, test execution runner, network integration, or automatic assertion/promotion policy.

## Capabilities

### New Capabilities
- `verification-ontology`: Source-neutral test, run, and verification-evidence facts; stable identity/provenance rules; and verification-specific relation semantics.

### Modified Capabilities
- `canonical-ontology`: Represent and merge the new verification node kinds and verification-evidence support references deterministically.
- `canonical-relationship-vocabulary`: Define verification relationship endpoint contracts and source mappings in the versioned catalog.
- `cross-graph-link-evidence`: Permit verification evidence to support `VERIFIED_BY` claims while retaining explicit lifecycle and implementation-trust boundaries.
- `graph-integrity-validation`: Validate verification identities, relationship shapes, provenance, and cross-graph evidence references before persistence or query.
- `ladybugdb-persistence`: Round-trip the expanded canonical snapshot format deterministically and reject prior catalog revisions.
- `local-ekg-query-api`: Expose represented verification facts and support context without source payloads or inferred implementation conclusions.

## Impact

- **Project-owned code:** canonical ontology models, relationship catalog, graph validation, persistence serialization/readback, and local query projections; corresponding local unit fixtures and tests.
- **Pipeline stages:** normalized graph admission, persistence/readback, graph integrity validation, and query projection. No new source-extraction or execution stage is introduced.
- **Integration boundary:** future test-management, test-framework, CI, and manual-verification sources may normalize into the source-neutral contract; their provider models and payloads remain outside the canonical graph.
- **External infrastructure:** no internal change to Graphify, Jira MCP, Bitbucket MCP, LadybugDB, OpenLore, test frameworks, CI vendors, llmwiki-cli, or MkDocs. LadybugDB remains behind the existing project-owned persistence adapter.
- **Canonical/persisted data:** canonical schemas and the persisted graph format/catalog revision are affected; migration, backup, and rollback for prior catalog revisions are explicitly out of scope for this greenfield change.
- **Traceability:** the proposal is for Plane task EKG-48 (source backlog item EKG-25, P0 urgent).
