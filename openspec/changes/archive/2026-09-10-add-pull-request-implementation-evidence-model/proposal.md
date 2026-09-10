## Why

Plane task `EKG-44` requires a pull request to be represented as attributable engineering evidence from an intended change to a particular repository revision. The current PR code-candidate flow retains a PR identifier and one merged revision only inside candidate provenance; it cannot model the PR's base/head revision pair, its explicit source-backed association to an OpenSpec change or work item, or distinguish that declared scope from observed code-change evidence.

## What Changes

- Add a canonical, payload-free pull-request implementation-evidence model with stable PR identity, repository identity, immutable base and head revisions, explicit source references, and complete first-class provenance.
- Represent an explicitly sourced PR-to-intended-change association for an active/archived OpenSpec change or existing work item, and record the association as declared rather than inferred from names, branches, commits, or changed paths.
- Represent PR-to-repository revision and resolved changed-symbol evidence as observed, scoped cross-graph `TOUCHES` candidates; require the candidate's code revision and PR/repository references to agree with the observed PR evidence.
- Preserve the trust boundary: a declared association narrows the candidate scope only. It does not establish that every PR change, file, or symbol implements the intended change or any contained requirement, and it never emits or promotes an `IMPLEMENTS` relation.
- Persist, validate, and expose deterministic, payload-safe PR evidence, declared associations, and observed candidate references through the existing local graph boundaries.
- **BREAKING:** incomplete, mutable, conflicting, unprovenanced, or payload-bearing PR identity/revision/source-reference input is rejected before graph emission. The versioned persisted catalog advances for the new relation mappings and record collections; prior persisted PR candidates are not backfilled with base/head revisions or explicit associations. New-format snapshots that contain no records from this model remain readable with empty PR-evidence collections.

## Capabilities

### New Capabilities
- `pull-request-implementation-evidence`: Normalizes and represents explicit PR-to-intended-change evidence and its declared/observed relation semantics.

### Modified Capabilities
- `canonical-ontology`: Adds deterministic canonical records and references for PR implementation evidence and scoped cross-graph observations.
- `canonical-relationship-vocabulary`: Defines declared PR-to-intended-change and observed PR/repository and code-candidate mappings, including permitted intended-change endpoints.
- `source-artifact-identity`: Admits payload-safe PR source-artifact identity and navigation references without treating provider URLs or payloads as graph data.
- `cross-graph-link-evidence`: Requires PR-scoped observations to retain the observed PR reference and preserves their non-implementation trust boundary.
- `pr-code-candidate-extraction`: Replaces the merged-revision-only normalized PR input with the explicit PR evidence and declared-scope contract.
- `graph-integrity-validation`: Validates PR identity, revision, source/provenance, association, repository, and cross-graph scope consistency.
- `ladybugdb-persistence`: Deterministically serializes and reads the new PR evidence records and references.
- `local-ekg-query-api`: Exposes represented PR evidence and declared/observed relation status without source payloads or implementation conclusions.
- `pipeline-runner`: Accepts and reports the enriched normalized PR evidence input while preserving unconfigured local runs.

## Impact

Affected project-owned areas are ontology schemas and stable identities, source-artifact/provenance adapters, PR candidate extraction, relationship admission, graph validation, local persistence, query DTOs, pipeline metadata, documentation, and fixture-based tests. Bitbucket, Jira MCP, Graphify, OpenLore, and LadybugDB remain external identity-level boundaries: this change does not call them, change their implementations, retain their payloads, or configure their infrastructure. The Plane traceability source is `EKG-44`; the source backlog item `EKG-12` and listed dependency keys are descriptive context only.
