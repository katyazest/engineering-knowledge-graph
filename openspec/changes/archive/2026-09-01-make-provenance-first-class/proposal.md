## Why

Plane task `EKG-40` (`187aacee-af3b-4965-b936-15962dc50523`) requires externally sourced and derived facts to be explainable end-to-end. The current source-artifact identity identifies authoritative artifacts, but provenance is not a first-class, uniform fact-level record of the source revision, observation, content fingerprint, extractor, and derivation rule across graph assembly, storage, queries, and cross-graph linking.

## What Changes

- Introduce a payload-free, immutable provenance record for externally sourced and derived Engineering KG facts.
- Require provenance to retain source-artifact identity and revision, observation time, useful content hash, extractor identity and version, and—only for derived facts—the derivation-rule identity.
- **BREAKING** Require newly admitted external and derived evidence/provenance records to satisfy the complete provenance contract; reject incomplete, inconsistent, or payload-bearing records before graph emission or persistence.
- Preserve provenance deterministically through graph merge, integrity validation, local persistence/readback, local query results, and cross-graph link observations and lifecycle evidence.
- Preserve canonical node, edge, cross-graph claim, and source-artifact identities; retain source identity rather than authoritative source content.
- Define guarded compatibility/migration behavior for persisted evidence that predates first-class provenance.

## Capabilities

### New Capabilities
- `fact-provenance`: Define first-class, payload-free provenance records, their stable identity, fact/evidence association, and the verification matrix for externally sourced and derived facts.

### Modified Capabilities
- `source-artifact-identity`: Make source-artifact identity the authoritative source component of a complete provenance record.
- `graph-derivation`: Require derived facts to retain the originating input provenance and explicit derivation-rule provenance.
- `graph-integrity-validation`: Validate provenance completeness, fact associations, identity consistency, and derived/external provenance semantics.
- `ladybugdb-persistence`: Persist, read, merge, and deterministically migrate first-class provenance without source payloads.
- `local-ekg-query-api`: Return represented provenance for queried facts and traceability without exposing authoritative source content.
- `cross-graph-link-evidence`: Preserve complete provenance references for candidate observations and lifecycle evidence without copying source content.

## Impact

- Affected project-owned components: canonical ontology/provenance schemas, source adapters and extractors, derivation, graph merge and validation, LadybugDB-compatible persistence serialization/migration, local query DTOs, cross-graph-link records, and fixture-based tests.
- Canonical schemas, persisted graph data, and query result shapes are affected. Canonical domain fact and cross-graph claim identities remain compatible.
- Graphify, Jira MCP, Bitbucket MCP, OpenLore, and LadybugDB remain external boundaries. This change adapts their identity-level inputs only; it does not change their implementations or retain their response/source payloads.
- Non-goals: source-content storage or retrieval, source resolution/network calls, provider payload schemas, semantic inference, new derivation rules, changing canonical fact identity, changing cross-graph trust policy, or retroactively fabricating provenance that legacy data cannot supply.
