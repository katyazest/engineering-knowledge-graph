## ADDED Requirements

### Requirement: EKG exposes a compact OpenLore semantic-bridge contract
The system SHALL provide a reusable, project-owned semantic bridge with two operations: (1) resolve a set of implementation-evidence changed-file references into symbol-resolution outcomes and (2) construct a navigation handoff for a complete `CodeLocator`. A changed-file resolution request SHALL contain only a stable implementation-evidence reference, exact repository identity, immutable revision, and one or more stable changed-file identities with repository-relative paths. A navigation handoff SHALL contain only the complete `CodeLocator` identity (`repository`, `revision`, `file`, and `symbol`) and the selected compact routing reference needed to route it. The routing reference SHALL identify either the registered repository's applicable federation `index_location` or its repository-index registered local path. The bridge SHALL use an injected project-owned OpenLore provider port; provider-specific request/response models SHALL NOT become bridge, canonical graph, or persistence models.

#### Scenario: Compact changed-file request is routed through the provider port
- **WHEN** EKG supplies a complete, registry-admitted implementation-evidence changed-file request and a compatible injected provider port
- **THEN** the bridge sends the provider only the validated repository identity, immutable revision, selected routing reference, and sorted changed-file identities/paths needed for symbol resolution
- **THEN** it returns a project-owned resolution result without exposing a provider-specific model

#### Scenario: Complete locator creates a navigation handoff
- **WHEN** EKG supplies a complete, bridge-admitted `CodeLocator`
- **THEN** the bridge returns a compact navigation handoff that preserves the exact repository, revision, file, and symbol values and identifies the selected federation or repository-index routing reference
- **THEN** the handoff does not contain a code-analysis conclusion or OpenLore response content

### Requirement: Bridge requests bind repository and revision to the registry and implementation evidence
The bridge SHALL admit a resolution request or navigation handoff only when its repository identity exactly matches one repository in the loaded workspace registry. Federation membership (`include_in_federation`) SHALL NOT be an admission prerequisite. For a registered repository included in an enabled federation, the bridge SHALL use its non-empty configured `index_location` as the routing reference; an applicable federation entry with a missing or blank index location SHALL be rejected as invalid routing context. When no applicable federation configuration exists because federation is disabled or the registered repository is not included in it, the bridge SHALL use that repository's registered resolved local path as the routing reference. A resolution request's repository and revision SHALL exactly match the repository and immutable merged revision in its implementation-evidence reference; the revision SHALL be a complete immutable Git object identifier, not a branch name, tag, abbreviated revision, or mutable pull-request reference. The bridge SHALL reject an unknown, mismatched, incomplete, mutable, or invalid-federation-route context before calling the provider, and SHALL return a deterministic context diagnostic without producing a `CodeLocator` or handoff.

#### Scenario: Federated registered evidence context is admitted
- **WHEN** a changed-file request names a registered repository included in an enabled federation with a non-empty index location and the same complete immutable revision recorded by its implementation evidence
- **THEN** the bridge admits that exact repository/revision context for provider resolution using the federation index routing reference
- **THEN** any `CodeLocator` returned by the bridge uses the same exact repository and revision values

#### Scenario: Registered repository is admitted through the repository-index fallback
- **WHEN** a changed-file request names a registry repository that is not included in federation, or names any registered repository while federation is disabled, and supplies the same complete immutable revision recorded by its implementation evidence
- **THEN** the bridge admits that exact repository/revision context using the repository's registered resolved local path as its routing reference
- **THEN** it does not require `include_in_federation` or `index_location` for that fallback route

#### Scenario: Repository or revision inconsistency is rejected before resolution
- **WHEN** a request names a repository absent from the registry or different from implementation evidence, supplies a revision that differs from the evidence revision or is mutable/incomplete, or selects an applicable federation entry with a blank index location
- **THEN** the bridge returns a deterministic invalid-context outcome identifying the failed condition
- **THEN** it does not call the provider and emits no locator, navigation handoff, graph record, or persisted record

### Requirement: Symbol resolution is exact and conservative
For each admitted changed file, the bridge SHALL accept a resolved outcome only when the provider port reports exactly one complete deterministic symbol identity for that same repository, immutable revision, and repository-relative file. It SHALL construct a `CodeLocator` solely from those exact values. A provider result with no symbol SHALL produce an explicit `unresolved` outcome; more than one candidate SHALL produce an explicit `ambiguous` outcome; and a provider failure, unavailable provider, malformed response, conflicting returned context, or unsupported response status SHALL produce an explicit non-resolved diagnostic outcome. The bridge SHALL not choose a first candidate, infer a symbol from a file name, path similarity, line range, branch, current checkout, or another repository/revision, and SHALL not replace a non-resolved result with an inferred match.

#### Scenario: One exact symbol resolves to a stable locator
- **WHEN** the provider reports exactly one complete symbol for an admitted changed file at the request repository and immutable revision
- **THEN** the bridge returns `resolved` with one `CodeLocator` containing exactly the request repository, revision, file, and returned symbol
- **THEN** repeated equivalent requests produce the same resolution outcome and locator identity

#### Scenario: No result or multiple results remains explicit
- **WHEN** the provider reports zero symbols or multiple symbols for an admitted changed file
- **THEN** the bridge returns respectively `unresolved` or `ambiguous` for that file with a stable diagnostic reason
- **THEN** it returns no `CodeLocator` for that file and does not substitute a probable symbol

#### Scenario: Provider failure cannot become a code match
- **WHEN** the provider is unavailable or returns an unsupported, malformed, repository-mismatched, revision-mismatched, or file-mismatched result
- **THEN** the bridge returns an explicit non-resolved diagnostic outcome for every affected file
- **THEN** it creates no partial locator and does not retry against another repository, revision, or broad workspace search

### Requirement: Navigation is handed off to OpenLore without importing code intelligence
The bridge SHALL construct a navigation handoff only from an admitted complete `CodeLocator` and its selected registry routing reference, and SHALL delegate deeper code navigation, architecture analysis, impact analysis, call/dependency-graph reasoning, and source retrieval to OpenLore. The bridge SHALL retain and expose only compact request identities, resolution statuses, locator identities, federation-index or repository-index-path routing reference, and payload-safe deterministic diagnostics. It SHALL NOT read or ingest the OpenLore code graph; persist source code, file or symbol bodies, call graphs, dependency graphs, semantic-analysis or navigation responses; or create a canonical semantic relationship, trusted implementation projection, or implementation conclusion from a resolution result.

#### Scenario: Navigation response remains owned by OpenLore
- **WHEN** a caller uses a bridge-generated navigation handoff with an OpenLore integration
- **THEN** EKG supplies the compact locator and its selected federation-index or repository-index-path routing reference to that integration
- **THEN** any deeper navigation or reasoning result remains outside the bridge result, canonical graph snapshot, persistence store, and EKG query projection

#### Scenario: Unsafe bridge data is not admitted or retained
- **WHEN** a bridge request, provider response, or diagnostic contains source content, a symbol/file body, code graph data, credentials, tokens, provider payload, or external navigation response rather than an approved compact identity or status
- **THEN** the bridge rejects or classifies the input as an explicit invalid-response outcome before it crosses the bridge boundary
- **THEN** none of that unsafe value is serialized, persisted, or exposed by EKG

### Requirement: Bridge results are deterministic, idempotent, and verification-bounded
The bridge SHALL deterministically sort changed-file outcomes and diagnostics by stable changed-file identity and SHALL coalesce repeated equivalent request entries without changing a resolved `CodeLocator` identity. It SHALL not write directly to `GraphSnapshot`, persistence, derivation, or query surfaces; a caller that later uses an existing cross-graph candidate flow remains responsible for that separate evidence and lifecycle admission. The change SHALL document and exercise the following verification matrix. Cases outside this matrix SHALL be reported as change candidates unless they violate another approved requirement or applicable baseline.

| Input class | Expected admission or outcome | Compatibility anchor |
| --- | --- | --- |
| Registered repository included in an enabled federation with a non-empty index location, matching implementation-evidence repository and complete immutable revision, valid changed file, exactly one matching complete provider symbol | Admit using the federation index routing reference and return one exact `CodeLocator` | EKG-46 intent; existing `CodeLocator`, EKG-14 implementation-evidence identity, and workspace OpenLore-source baseline |
| Registered repository not included in federation, or any registered repository when federation is disabled, matching implementation-evidence repository and complete immutable revision, valid changed file | Admit using the repository's registered resolved local-path routing reference; do not require `include_in_federation` or `index_location` | EKG-46 federation-optional revision; workspace registry repository-path baseline |
| Same valid request/file repeated | Coalesce deterministically; preserve the same outcome and locator identity | Existing stable-ID/idempotency baseline |
| Unknown registry repository, evidence-repository mismatch, evidence-revision mismatch, branch/tag/abbreviated revision, or an applicable federation entry with a missing/blank index location | Reject before provider invocation; return invalid-context diagnostic and no locator/handoff | EKG-46 repository/revision consistency; workspace OpenLore-source baseline |
| Valid context with zero provider symbols | Return explicit `unresolved` and no locator | EKG-46 no inferred match; EKG-14 unresolved-symbol baseline |
| Valid context with multiple provider symbols | Return explicit `ambiguous` and no locator | EKG-46 no inferred match; EKG-14 ambiguity baseline |
| Provider unavailable, malformed/unsupported response, or response whose repository/revision/file conflicts with the request | Return explicit non-resolved diagnostic and no locator; do not broaden or retry resolution | EKG-46 explicit failure boundary |
| Admitted complete `CodeLocator` for a registered repository with an applicable federation index or repository-index fallback path | Return compact navigation handoff with exact locator identity and the selected federation-index or repository-index-path routing reference only | EKG-46 federation-optional navigation boundary; existing `CodeLocator` contract |
| Source bodies, code-graph/analysis/navigation payloads, credentials, tokens, or provider-specific response models | Reject or classify as invalid response before serialization or graph admission | Existing payload-free OpenLore and query baselines |

#### Scenario: Verification matrix is exercised
- **WHEN** automated bridge contract, provider-port fake, registry, and integration-boundary tests exercise each applicable matrix row
- **THEN** each row has the documented admission, resolution, rejection, or non-emission behavior
- **THEN** tests verify that no OpenLore code graph or response payload is persisted and that no unresolved, ambiguous, or failed resolution is represented as a resolved locator
