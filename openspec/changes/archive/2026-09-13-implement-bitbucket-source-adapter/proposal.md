## Why

Plane task `EKG-45` (source backlog item `EKG-13`, P0) needs a project-owned boundary that can turn selected Bitbucket pull-request source observations into the revision-bounded implementation evidence established by `EKG-44`. The repository has that canonical evidence model and an empty `ingest/bitbucket.py`, so PR identity, repository/revision evidence, changed-file observations, and explicit traceability declarations currently have to be hand-assembled rather than obtained deterministically from the source boundary.

## What Changes

- Add a reusable Bitbucket source adapter with an injected source port that isolates Bitbucket transport, API, and MCP response shapes from the canonical ontology and persistence model.
- Normalize a selected merged PR's source-qualified identity, canonical repository reference, immutable base/head commit revisions, and source-backed observed repository relation into the existing pull-request implementation-evidence model with complete, payload-free external provenance.
- Normalize available changed-file observations into compact, revision-bound file references with per-observation source/provenance references so they can be handed to the existing OpenLore resolution and PR-candidate seams without diff parsing or symbol guessing.
- Materialize a declared PR-to-OpenSpec-change/Jira-story association only from a structured explicit-reference record supplied through the adapter's supported source contract and only when its exact canonical target is available. The adapter will not derive traceability from titles, descriptions, issue-like tokens, branch names, commits, changed paths, or textual similarity.
- Return deterministic, payload-safe admission metadata and diagnostics for unsupported, incomplete, conflicting, unavailable, or unresolvable source observations. Valid PR identity/revision evidence remains representable when no explicit association is supplied; no scoped code candidate is created until a later exact symbol-resolution flow supplies one.

## Capabilities

### New Capabilities
- `bitbucket-source-adapter`: Acquire selected Bitbucket PR observations through an isolated port and normalize revision-bounded PR evidence, explicit declarations, changed-file references, and provenance deterministically.

### Modified Capabilities
- None.

## Impact

Affected project-owned areas are `engineering_kg.ingest.bitbucket`, source-artifact/provenance construction, adapters to the existing PR implementation-evidence and OpenLore changed-file contracts, safe result metadata, documentation, and fixture-based tests. Existing canonical PR records, relationship vocabulary, graph persistence, query APIs, and the opt-in local PR-candidate stage are reused rather than given a provider-specific schema or persistence migration.

Bitbucket MCP/API/transport implementations remain external behind the injected port; this change does not modify Bitbucket, Jira, OpenLore, Graphify, or LadybugDB internals, add credentials or network requirements to ordinary pipeline runs, retain provider payloads/URLs/diffs/source bodies, parse diffs, resolve symbols, or infer trusted `IMPLEMENTS`/requirement coverage.
