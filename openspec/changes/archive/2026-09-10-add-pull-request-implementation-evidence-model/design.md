## Context

Plane task `EKG-44` extends the engineering-evidence boundary defined by source-artifact identity (`EKG-03`), cross-graph link evidence (`EKG-09`), provenance (`EKG-40`), relationship vocabulary (`EKG-38`), and evidence classification/trust (`EKG-41`). The current `pr_code_candidates` adapter accepts an explicit Jira-story/merged-PR association and a single merged revision, then keeps the PR ID only in provenance metadata for an observed `TOUCHES` candidate. `NodeKind.PULL_REQUEST` and catalog support for PR relations already exist, but there is no typed PR entity with base/head revisions, no source-backed link to an OpenSpec change, and no direct reference from a cross-graph observation to the PR that produced it.

`EKG-44` therefore adds a local, provider-neutral PR evidence model. It changes only project-owned Python models, normalization, vocabulary, validation, persistence, local projections, pipeline orchestration, documentation, and fixture tests. Bitbucket, Jira MCP, Graphify, OpenLore, and LadybugDB remain external sources or execution boundaries. Their response models, URLs, diffs, source code, credentials, and payloads do not enter the canonical graph.

## Goals / Non-Goals

**Goals:**

- Represent a merged PR as immutable, payload-free evidence with stable source-qualified identity, repository identity, base/head Git revisions, source references, and complete provenance.
- Represent an explicit declared PR association to one active/archived OpenSpec change or existing Jira-story work item, and a separately observed PR-to-repository revision relation.
- Bind resolved PR changed-symbol observations to that PR and association while retaining the existing observed, untrusted `TOUCHES` candidate semantics.
- Enforce the contract through construction, merge, vocabulary admission, integrity validation, current-format persistence/readback, pipeline metadata, and local query projections.

**Non-Goals:**

- Fetching PRs, commits, associations, diffs, Jira data, or Graphify mappings; implementing Bitbucket, Jira, Graphify, OpenLore, or LadybugDB; or modifying their configuration.
- Accepting open/unmerged PRs, mutable branch/tag references, abbreviated commits, inferred associations, fuzzy matching, diff/source parsing, or requirement-coverage analysis.
- Treating a declared PR association, a merged status, a changed file, a changed symbol, evidence count, or confidence as proof of implementation; no `IMPLEMENTS` mapping, promotion policy, or trusted implementation projection is added.
- Migrating, backfilling, or guessing base/head revisions, association source references, or PR scope for a prior persisted catalog record. The EKG-38 greenfield/current-format boundary applies.

## Decisions

### 1. Use typed PR evidence and association records, with nodes and edges as canonical projections

Add immutable project-owned records alongside existing `Node`, `Edge`, `Evidence`, `ProvenanceRecord`, and cross-graph collections:

- `PullRequestImplementationEvidence`: source-qualified PR identity, canonical repository-node ID, complete base revision, complete head revision, merged status, PR source-evidence ID, and its stable ID. The ID is derived from the source-qualified PR identity and repository identity, not revisions, titles, branches, mappings, or display values. A later record with that identity but a different immutable base/head/source value is a conflict rather than an update selected by ingestion order.
- `PullRequestDeclaredAssociation`: one PR evidence ID, one intended-change node ID, and one declared source-evidence ID. Its endpoint set is restricted to `OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, and `JIRA_STORY`.
- `PullRequestObservedRepositoryRelation`: one PR evidence ID, the same repository-node ID, and the supporting observed source-evidence ID.

These typed records materialize `PULL_REQUEST REFERENCES intended-change` and `PULL_REQUEST TOUCHES REPOSITORY` canonical edges but retain their `declared` and `observed` origins in the typed record rather than overloading generic `Edge.confidence` or unbounded `Edge.properties`. The PR node ID is derived from the PR evidence identity; its display name is not an identity input. This preserves graph navigation while giving validation and queries an unambiguous origin contract.

Alternative: retain PR fields only in generic evidence properties or create only generic edges. Rejected because properties have no PR-specific stable identity, revision consistency, endpoint, or origin validation and would force queries to reconstruct the intended relationship from incidental metadata. Alternative: use the PR node as the cross-graph claim subject. Rejected because the candidate needs to be scoped to the declared intended change, not merely to the PR.

### 2. Separate PR identity from a revision-bounded source artifact and provenance chain

Normalize a merged PR before graph construction. Its PR identity is provider/source-qualified and payload-safe; its repository must resolve to an existing canonical `REPOSITORY` node; and both base and head are complete immutable Git object IDs. Build a PR `SourceArtifactIdentity` with an opaque PR locator and `head_revision` as `revision_or_version`, then create its external `ProvenanceRecord` and supporting `Evidence`. Base/head revisions and the repository reference are validated PR identity-level data, not source bodies or navigation URLs.

The source reference proving an intended-change association is separate from the PR source artifact. It resolves to its own admitted evidence and complete provenance, so the graph can state which source explicitly declared the association without copying provider text. A changed-symbol mapping also continues to have its own source artifact/provenance chain. The adapter receives normalized identity-level fields only; it discards provider-specific payload fields before record construction.

Alternative: put base/head revisions in the `CodeLocator` only or use the existing `merged_revision` as the PR identity. Rejected because a code locator has no PR identity or base comparison and a merged revision alone cannot represent the requested PR change boundary. Alternative: retain provider URLs as source references. Rejected by the payload-free source-artifact baseline.

### 3. Make relation origin explicit and constrain the relationship catalog

Advance the relationship catalog revision and add source mappings for the two direct PR facts: declared explicit association maps to `REFERENCES`; observed PR revision evidence maps to `TOUCHES`. Extend the code-locator `TOUCHES` source endpoint alternatives to include active/archived OpenSpec changes as well as the existing Jira work-item node. The direct PR edge direction is always `PULL_REQUEST → target`; the candidate claim direction is `intended-change → CodeLocator`.

Only the typed PR association emits `declared` and only the typed repository relation/PR changed-symbol support emits `observed`. A declared association is scope evidence, not a trusted implementation assertion. The mapping set contains no `IMPLEMENTS` route, and catalog validation continues to fail closed for reversed or unsupported endpoints.

Alternative: classify every general graph edge using the cross-graph evidence enums. Rejected because EKG-44 needs a narrow PR relation contract, while general edge classification would be an unapproved cross-cutting product model. Alternative: use `TRACES_TO` for the PR association. Rejected because the relationship is an explicit non-owning source reference, not OpenSpec/Jira traceability semantics.

### 4. Attach PR scope to observed cross-graph support without changing claim identity

Extend `CrossGraphLinkEvidence` with optional, immutable references to the typed PR evidence and declared association. A PR-derived observation must supply both references; non-PR observations remain valid without them. Include the new references in PR-derived observation identity, but keep `CrossGraphLinkClaim.id` based only on its existing intended-change subject, relationship kind, and complete code locator.

The enriched `pr_code_candidate_extraction` normalized input replaces `merged_revision` with base/head revisions and supplies PR source evidence plus an explicit declared association. For every resolved mapping it builds a `TOUCHES` claim whose subject equals the association's intended change and whose `CodeLocator.repository`/`revision` match the PR repository/head exactly. Its observation is `observed`, `authoritative`, and `untrusted`; its candidate lifecycle remains observed/derived/untrusted under the existing classification contract. Unresolved, ambiguous, incomplete, mismatched, or association-less mappings are diagnosed and emit no partial cross-graph records.

This produces the bounded evidence path:

`declared source reference → PR-to-intended-change association` + `observed PR source → PR-to-repository revision` + `observed changed-symbol source → PR-scoped TOUCHES candidate`.

The path deliberately stops at a candidate. It does not fan out from an OpenSpec change to its requirements, and it does not assert that all files/symbols in the base-to-head change set implement anything. Existing EKG-41 checks continue to prevent observed PR/file support from becoming trusted `IMPLEMENTS` truth.

Alternative: create one `IMPLEMENTS` edge for each changed symbol or all requirements of an associated change. Rejected because changed paths/symbols are observations, not requirement-level semantic proof. Alternative: store the PR only as provenance metadata. Rejected because consumers cannot enforce or query repository/revision/scope consistency from metadata alone.

### 5. Validate and persist the model as a new current catalog format

`GraphSnapshot` merge indexes PR evidence and both typed relation collections by stable ID, coalesces equivalent records in deterministic order, and rejects immutable conflicts, absent endpoints, missing source/provenance references, and cross-collection mismatches. Integrity validation additionally checks:

- PR node, repository node, base/head shape, merged status, source artifact, and provenance chain;
- association endpoints, direction, declared origin, and source reference;
- repository relation endpoint, observed origin, and source reference;
- PR-scoped observation references, code-locator repository/head agreement, candidate lifecycle, and the existing no-trusted-`IMPLEMENTS` policy.

Persistence serializes the typed collections and new observation fields with stable order and validates prospective snapshots before commit and after readback. Advancing the catalog revision prevents an older reader from silently dropping the new collections. The reader accepts a current-format snapshot with empty PR collections, but rejects earlier persisted catalog revisions and prior PR candidates that cannot meet the complete base/head/association contract. There is no migration or backup workflow for this new format because no approved authoritative mapping can reconstruct those facts.

Alternative: treat missing base/head fields as empty/default values or migrate them from a current checkout or merge commit. Rejected because that would manufacture revision evidence and violate the immutable-source baseline.

### 6. Expose a projection, not a new external integration surface

Add a reusable local query projection/operation for PR implementation evidence and extend relevant change/traceability projections with represented PR references. The DTO resolves only graph-stored fields: PR ID, repository ID, base/head revisions, declared association, declared/observed origins, source/provenance references, and candidate IDs. It never resolves a PR URL, loads a diff, calls an MCP server, or calculates requirement coverage/trust.

The pipeline retains `pr-code-candidate-extraction` as an opt-in stage. Its argument becomes the enriched PR-evidence collection, its metadata reports only safe counts/reason codes, and it keeps current no-input/unconfigured behavior. The extractor remains reusable so fixtures can test every matrix row without a network dependency.

## Data Flow

`provider-neutral merged PR identity + repository + base/head + PR source provenance` → `PullRequestImplementationEvidence` + `PULL_REQUEST` node → `observed PULL_REQUEST TOUCHES REPOSITORY`

`explicit source-backed OpenSpec/Jira association` → `PullRequestDeclaredAssociation` → `declared PULL_REQUEST REFERENCES intended change`

`resolved Graphify mapping for same PR` → `complete CodeLocator(repository, head, file, symbol)` + observed PR/association-scoped `TOUCHES` candidate → existing lifecycle/validation/persistence/query path.

All inputs are sorted and indexed by stable identities before graph construction. Processing is linear in PR records plus mapping records, apart from deterministic sort costs; no source code, diff, or provider-payload volume is retained in the graph.

## Risks / Trade-offs

- [A provider cannot supply base/head commits or an explicit source reference] → reject and diagnose rather than weaken revision/scope evidence.
- [A PR has multiple explicit intended-change associations] → retain each distinct typed association and scope candidates only to the association supplied for that observation; do not infer an association from other PR links.
- [A merged PR head differs from the eventual integration commit] → candidates remain observations at the submitted immutable head; they are not trusted implementation truth. A future post-merge revision contract requires approval.
- [Existing candidate fixtures and constructors use `merged_revision` only] → update project-owned fixtures and adapters atomically to the enriched normalized contract; no legacy reader is retained.
- [New typed records increase snapshot joins and size] → use ID indexes, coalescing, deterministic ordering, and payload-free fields; defer retention/index policy until volume evidence exists.
- [Consumers mistake an explicit association for requirement implementation] → expose relation origins and candidate lifecycle/trust separately and test negative requirement-coverage and `IMPLEMENTS` cases.

## Migration Plan

1. Add typed PR evidence/association/repository-relation models, stable IDs, payload-safe validators, and verification-matrix fixtures.
2. Extend source-artifact navigation validation, provenance construction, relationship vocabulary/source mappings, and the normalized PR candidate adapter to emit the model.
3. Thread typed PR references through cross-graph observations, merge, integrity validation, persistence serialization/readback, and catalog revision validation.
4. Extend local query/pipeline projections and update documentation; exercise repeated merge, readback, and all declared/observed negative cases locally.
5. Publish only the new catalog revision. Prior persisted graph catalogs fail deterministically; rollback is to the prior application/catalog reader against a separately rebuilt prior-format graph, not a fabricated data migration.

## Open Questions

None. `EKG-44` and the existing merged-PR, provenance, immutable-revision, and observed-evidence baselines determine the current contract; post-merge integration-commit semantics and requirement-level implementation mapping remain future change candidates.
