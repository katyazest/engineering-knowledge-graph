## Why

Plane task `EKG-42` (source backlog item `EKG-06`, urgent) identifies an integrity gap: merge paths can collapse assertions sharing a canonical identity before the complete set of independently sourced values and evidence reaches integrity validation. That can turn an ingestion-order-dependent conflict into an apparently trusted fact. The completed `EKG-37` source-artifact identity and `EKG-41` declared/observed/inferred trust contracts provide the stable provenance inputs needed to close this gap without redefining either model.

## What Changes

- Add a conflict-aware canonical merge contract that groups same-identity assertions and their evidence before coalescing or rejecting them, with deterministic, payload-free conflict diagnostics.
- **BREAKING** Remove any merge-time selection of differing asserted values based on input order or presentation-value ordering. Equivalent assertions may coalesce and accumulate evidence; unresolved incompatible assertions block an otherwise valid merged snapshot and persistence replacement.
- Define a conservative authority boundary: existing declared, authoritative, explicitly trusted support may determine a trusted cross-graph projection only through its existing explicit lifecycle decision; it does not authorize replacing a conflicting canonical node, edge, evidence, provenance, PR, or support record. No source-authority ranking exists for generic canonical assertions, so such conflicts remain retained for diagnosis and are rejected rather than resolved.
- Apply the contract to `GraphSnapshot` merge, persistence write/readback merge, graph integrity validation diagnostics, and fixture-based regression tests. Preserve compatible IDs, provenance, and evidence ordering.
- Document the verification matrix for compatible duplicates, independently sourced compatible assertions, unresolved conflicts, lifecycle-resolution boundaries, malformed/conflicting persisted input, and no-last-write-wins behavior.

## Capabilities

### New Capabilities
- `conflict-aware-graph-merge`: Deterministic assertion grouping, conflict detection and diagnostics, conservative authority-resolution boundary, and verification matrix for graph merges.

### Modified Capabilities
- `canonical-ontology`: `GraphSnapshot` merge behavior preserves independently sourced evidence until compatible coalescing or deterministic conflict reporting.
- `graph-integrity-validation`: Validation reports retained same-identity assertion conflicts with deterministic, payload-free diagnostics rather than permitting an overwritten winner.
- `ladybugdb-persistence`: Persistence merge validates conflict-aware candidates before replacing stored state and never writes a silently selected conflicting value.
- `cross-graph-link-evidence`: Existing classified support/lifecycle rules remain the sole authority for trusted cross-graph projection and are made explicit as a non-override boundary for generic graph merge conflicts.

## Impact

Affected project-owned components are the canonical ontology merge helpers and snapshot construction, integrity validation metadata/diagnostics, LadybugDB-compatible persistence merge/readback, cross-graph trusted projection boundary, and local fixture tests. Canonical object IDs, `SourceArtifactIdentity`, first-class provenance, and the EKG-41 evidence classification vocabulary remain compatible; valid equivalent writes remain idempotent. Conflicting writes will now fail deterministically before persistence replaces a snapshot, rather than selecting a record by order or presentation text.

Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, and LLM providers remain external boundaries. This change neither calls nor changes them, retains no source/provider payloads, and introduces no generic source-authority ranking, automatic conflict resolution, data migration, or trust-promotion policy.
