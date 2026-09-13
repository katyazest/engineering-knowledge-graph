## Context

Plane task `EKG-45` (source backlog `EKG-13`) is the missing source producer after the PR implementation-evidence model from `EKG-44`. That model already has immutable `PullRequestImplementationEvidence`, declared PR-to-intended-change associations, observed PR-to-repository relations, source-artifact/provenance validation, and current-format persistence. It deliberately does not fetch external data. `engineering_kg.ingest.bitbucket` is empty, while `pr_code_candidates` currently receives hand-assembled normalized PR/mapping input and `openlore_bridge` already accepts compact implementation-evidence changed-file requests.

The repository configuration makes Bitbucket MCP an external integration boundary. No Bitbucket MCP client, credentials, tool schema, or response fixture exists in the repository, so this change must provide a project-owned source-port contract rather than embed an undocumented MCP API in the ontology or pipeline. `EKG-45` is traceable to the Plane issue; `EKG-13` is source-backlog context only.

## Goals / Non-Goals

**Goals:**

- Turn one explicitly selected Bitbucket PR source observation into the existing payload-free PR evidence/repository-relation model, with immutable base/head commit IDs and complete external provenance.
- Preserve source-available changed-file identities and explicit structured declarations as compact, independently attributable adapter output that can feed the existing OpenLore and PR-candidate seams.
- Materialize only exact declared associations to already represented active/archived OpenSpec changes or Jira stories; preserve an unassociated but valid PR observation when no supported declaration exists.
- Keep acquisition deterministic, testable through injected fakes, ordered by stable identity, and independent of live external infrastructure in the test suite.

**Non-Goals:**

- Define, configure, authenticate to, or modify a Bitbucket MCP/API/server; discover PRs globally; query a repository checkout; or add a default networked pipeline stage.
- Add provider-specific entities, URLs, request/response payloads, credentials, tokens, diffs, source/commit message bodies, line ranges, or code data to canonical ontology, persistence, or query models.
- Add a canonical commit-log/file-history collection, parse diffs, resolve symbols, construct a `CodeLocator` from a file, or change EKG-44's base/head revision evidence boundary.
- Infer traceability from titles, descriptions, comments, issue-like tokens, branch names, commit messages, repository names, changed paths, counts, or global/fuzzy textual similarity.
- Emit an `IMPLEMENTS` edge, requirement coverage, trusted projection, candidate lifecycle, or automatic candidate promotion; alter the unconfigured pipeline, persistence catalog, relationship vocabulary, or existing query contracts.

## Decisions

### 1. Put Bitbucket transport behind a small injected source port

Implement `engineering_kg.ingest.bitbucket` as a reusable module with an injected `BitbucketSourcePort`. Its input is a compact selection containing the source-qualified PR identity and the canonical repository ID expected by EKG. The port obtains a source-private `BitbucketPullRequestSourceRecord`; a deployment-specific MCP/API client is responsible for converting its own tool calls and response objects into that record. The source-private record contains only the allowlisted fields needed for this task: merged status, exact base/head commit IDs, observation instant, source-reference identity fields, changed-file source records, and separately classified structured declaration records.

The module owns compact, frozen adapter DTOs, a source result, fixed reason codes, and source-private response validation. These DTOs are Bitbucket-bound integration values, not ontology classes. The provider port may carry transient provider payloads during transport conversion, but the adapter never returns, serializes, stores, hashes as a retained field, or propagates them. A port exception is reduced to an unavailable result with no exception text.

This matches the existing OpenLore bridge's provider-port pattern and lets an actual MCP integration be added without changing the canonical graph. Alternative: call a hard-coded MCP tool or parse raw mappings directly in `pipeline.py`. Rejected because no such tool/response contract is available in this repository, it would make ordinary local runs credential/network dependent, and it would leak provider semantics across the canonical boundary.

### 2. Reuse the EKG-44 PR model; base and head are the represented commit boundary

After validating the selected record, the adapter builds the already-approved `PullRequestImplementationEvidence` and `PullRequestObservedRepositoryRelation`, plus the exact existing PR node/edge projection through `project_pull_request_evidence`. The canonical repository must already exist in the supplied subject snapshot and must be a `REPOSITORY` node. The source-qualified PR identity and canonical repository determine the existing PR evidence ID; base/head revisions, source evidence, and provenance remain immutable conflict-checked fields rather than inputs to display or identity selection.

For the PR source, repository-relation source, and each structured declaration source, the adapter constructs a distinct `SourceArtifactIdentity`, external `ProvenanceRecord`, and `Evidence` using `normalize_source_artifact`/`external_provenance` or equivalent shared helpers. The PR artifact has `artifact_type=pull-request` and uses the exact head commit as `revision_or_version`; its opaque locator is not a provider URL. The useful provenance representation is a deterministic serialization of the allowlisted source observation, never an external body. Existing EKG-44 graph merge and integrity checks then validate source/provenance binding and exact projected edges.

A valid PR does not require an association or a changed-file list to be represented. An invalid PR is atomic: emit a safe diagnostic and no PR-related evidence, provenance, node, edge, association, or file observation for that selected input. A valid PR with one invalid file/reference can retain the independently valid PR result but excludes the defective subordinate observation.

Alternative: add Bitbucket PR, repository, commit, and file nodes or a provider-specific persistence collection. Rejected because EKG-44 already defines the canonical PR/repository representation; an unbounded commit/file history is not approved by the task, and it would require new ontology, query, persistence, and migration contracts.

### 3. Model changed files as provenance-complete adapter observations, not code claims

The result owns `BitbucketChangedFileObservation` records for valid file information made available by the source. Each contains a stable source-file identity, repository-relative file path, PR evidence ID, repository ID, head revision, and its separate source evidence/provenance references. Its identity is based on the immutable PR/repository/head/file context and not input order, display values, line ranges, or diff content. The adapter coalesces equivalent observations after stable sorting and reports a conflict rather than selecting between distinct values sharing one source-file identity.

The observations are ephemeral normalized evidence inputs, rather than a new canonical graph collection: they are passed unchanged to `ChangedFileReference`/`ImplementationEvidenceContext` for `OpenLoreSemanticBridge`. The adapter also provides an explicit conversion seam from exact bridge outcomes back into `ChangedSymbolMapping`/`NormalizedPullRequestEvidence`, retaining the original stable changed-file identity and source/provenance chain. That seam only accepts outputs whose PR/repository/head/file context matches the observation. Existing candidate extraction can therefore create its observed/untrusted candidate later, with no Bitbucket-specific types crossing the seam.

Changed-file observations do not become code locators: no diff parsing, file-name/similarity fallback, line-range interpretation, or symbol selection occurs here. An unavailable changed-file feed is a distinct reason-coded result, not an empty successful list. File records with an unsafe path, missing ID/path, conflicting duplicate, or PR/repository/head mismatch are excluded individually with a safe diagnostic.

Alternative: have the source adapter invoke OpenLore or directly construct candidate claims. Rejected because EKG-46 owns exact symbol resolution and EKG-14/44 own candidate admission; combining them would conflate provider acquisition, code intelligence, and implementation trust.

### 4. Recognize only structured, source-backed traceability declarations

The source-port contract has one supported declaration shape: a separately supplied `BitbucketStructuredReference` containing an exact canonical intended-change ID, one eligible intended-change kind, and its own source reference. It is a transport-normalized statement that the Bitbucket integration explicitly classifies as a declaration; it is not parsed from a text field. The adapter checks the exact target against the supplied canonical snapshot before constructing a `PullRequestDeclaredAssociation` and its existing `PULL_REQUEST REFERENCES` projection. Multiple distinct valid declarations for a PR are retained independently, consistent with EKG-44.

Missing, unsupported, malformed, ambiguous, or unresolvable declarations yield safe diagnostics and no association. They do not invalidate an otherwise complete PR/repository result and they cannot produce a PR-scoped candidate. This is intentionally narrower than generic title/issue-key matching and satisfies the EKG-44 explicit-association baseline.

Alternative: interpret a standardized textual tag in PR title/body or exact work-item-like token as an explicit reference. Rejected because the existing PR implementation-evidence specification expressly prohibits association inference from those fields and the task supplies no approved textual convention.

### 5. Keep graph, persistence, pipeline, and public compatibility additive

`BitbucketSourceResult` returns the canonical graph contribution for admitted PR/repository/declaration records plus separate changed-file observations and safe metadata. The caller may merge the graph contribution through normal `GraphSnapshot` validation and current persistence, but the adapter never writes storage. Changed-file observations are carried only through the existing bridge/candidate input seams; they do not create an orphan persisted graph collection.

There is no relationship-catalog, ontology, persistence catalog, query DTO, or migration change. The existing local `pr-code-candidate-extraction` stage remains a normalized-input-only stage and continues not to acquire Bitbucket data. The README/source-boundary documentation will distinguish the new reusable adapter from a configured live `bitbucket-mcp` pipeline stage. This retains bootstrap and unconfigured pipeline behavior, while an integration can call the adapter before handing its graph contribution and file observations to later existing stages.

Alternative: add a `bitbucket-mcp` stage that silently invokes the source port whenever the pipeline runs. Rejected because source selection/discovery and deployed MCP configuration are not part of EKG-45, and it would contradict the existing local/no-external-acquisition pipeline contract.

## Data Flow

`selected PR + injected Bitbucket source port` → source-private allowlisted PR record

`valid merged PR + existing repository` → head-bounded PR source evidence/provenance → existing `PullRequestImplementationEvidence` + observed repository relation → canonical graph contribution

`structured explicit reference + exact eligible subject graph node` → separate association source evidence/provenance → existing declared `PULL_REQUEST REFERENCES` contribution

`source-available changed file + same PR/repository/head` → `BitbucketChangedFileObservation` → existing OpenLore changed-file request → exact bridge outcome → existing changed-symbol mapping/candidate input

Every collection is sorted by stable ID before result construction. Processing is linear in selected PRs, declarations, and changed files apart from deterministic sorting; it performs no global textual search, diff parsing, code analysis, or source-content retention.

## Risks / Trade-offs

- [The deployed Bitbucket MCP lacks the source-port fields or structured declaration records] → return an explicit unavailable/unsupported diagnostic and do not manufacture evidence; a deployment adapter can be implemented only once its concrete MCP contract can satisfy this port.
- [A valid PR has no explicit association] → retain bounded PR/repository evidence and file observations, but create no association-scoped candidate; this preserves evidence without claiming traceability.
- [A PR changes renamed/deleted or otherwise non-resolvable files] → retain only source-approved safe head-revision file observations; records that cannot satisfy the head-context contract are reason-coded non-admissions for later code resolution.
- [Callers treat changed-file evidence as implementation proof] → keep file observations outside canonical semantic relations, require EKG-46 exact resolution and EKG-14/44 candidate admission, and regress no-`IMPLEMENTS` behavior.
- [Provider data contains sensitive or large payloads] → use allowlisted transient extraction, structural safe-ID validation, deterministic safe hashes, reason codes, and serialization regression tests; never expose exception text or raw source.
- [Many changed files increase result size] → retain only compact identifiers/path/provenance references, sort once, and defer retention/index policy until a separately approved volume requirement.

## Migration Plan

1. Add source-port/selection/source-private record contracts, safe diagnostics, and fixture fakes in `ingest.bitbucket`; reuse compact identity and source-artifact/provenance helpers.
2. Implement atomic PR/repository normalization, structured-association materialization, and deterministic graph-result construction against existing EKG-44 models and merge validation.
3. Add provenance-complete changed-file observations and explicit conversions to the existing OpenLore request and post-resolution PR candidate input seams, retaining exact IDs/context.
4. Add unit/integration fixtures for every verification-matrix row, graph merge, downstream handoff, payload exclusion, and no-live-infrastructure behavior; update source-boundary documentation.
5. Run the full local suite. No persisted-data migration, catalog revision, rollback conversion, or external-infrastructure configuration is needed because no persisted schema changes and no default pipeline acquisition are introduced. Rollback removes the adapter module/callers; pre-existing snapshots remain readable.

## Open Questions

None for the project-owned contract. A concrete deployed Bitbucket MCP tool/response mapping is deliberately an external port implementation prerequisite, not an ontology or product decision in this change.
