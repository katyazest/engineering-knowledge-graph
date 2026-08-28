## Context

Plane task `EKG-72` (`ekg-72-implement-pr-to-code-candidate-extraction`) is the first producer for the cross-graph candidate/evidence foundation delivered by `EKG-09`.  The current canonical model already supplies `CodeLocator`, immutable cross-graph claims and observations, candidate lifecycle entries, local persistence, and validation.  It deliberately has no pull-request ingestion or code-candidate producer: `ingest/bitbucket.py`, `ingest/jira.py`, and `ingest/graphify.py` are currently empty boundary modules.

The repository configuration identifies Jira and Bitbucket MCP plus Graphify as external infrastructure. This change owns only normalized local input, deterministic mapping/admission, graph construction, and optional orchestration. It must not call those systems, absorb their provider models, or query OpenLore. The pipeline currently has no PR-input parameter or candidate stage, so the new stage must remain opt-in and preserve all existing runs.

## Goals / Non-Goals

**Goals:**

- Admit only explicit, merged engineering-change/PR associations whose existing graph subject is `JIRA_STORY`, and deterministically resolved changed symbols.
- Produce stable observed-change `CrossGraphLinkClaim` candidates with explainable local provenance, a `candidate` lifecycle entry, and deterministic diagnostics.
- Reuse the existing cross-graph persistence and integrity boundary and expose the producer through an optional pipeline stage.
- Make all behavior locally fixture-testable and repeatable.

**Non-Goals:**

- Fetching or discovering Jira stories, PRs, diffs, links, commits, or symbols; implementing Bitbucket, Jira, Graphify, LadybugDB, or OpenLore.
- Diff parsing, source-code parsing, symbol inference/fuzzy matching, mutable-reference resolution, confidence scoring, semantic analysis, copying external payloads into the graph, retaining hierarchical/authority-bearing external navigation links, or treating non-`JIRA_STORY` nodes as engineering changes.
- Creating a trusted link or an `IMPLEMENTS` edge, automatic lifecycle promotion/rejection, authorization policy, new query/MCP surfaces, or a change to existing trusted-link projection behavior.

## Decisions

### Decision: Use a project-owned normalized admission contract

Add a reusable module such as `engineering_kg.ingest.pr_code_candidates` with frozen normalized records for: (1) an explicit engineering-change/PR association, (2) a merged PR change set, and (3) a changed-symbol mapping outcome. The change set carries canonical engineering-change subject ID, PR identity, repository ID, immutable merged revision, and mapping records. A mapping carries a stable source mapping identity, file, and either one complete resolved symbol identity or a classified unresolved/malformed/ambiguous result.

The adapter boundary validates non-empty required identity fields and merger status before extraction. A retained identity may be a payload-safe opaque URI-shaped stable ID such as `urn:example.org/link-42`; it is retained as an identifier, not an external navigation link. The boundary rejects payload-like values and hierarchical or authority-bearing forms such as `https://…`, `custom://…`, and `https:host/path`. It receives simple mapping data or project-owned adapters from provider/Graphify responses, but provider-specific types, source payloads, and external navigation links end at that boundary and are never persisted. The normalized contract is deliberately explicit about the asserted association rather than treating matching issue keys, repository names, branches, commit text, or changed files as linkage.

Rationale: a narrow contract provides an independently testable seam while the external adapters do not yet exist. It prevents later source adapters from imposing their shapes on the canonical graph and makes the exact admission requirement visible.

Alternative considered: accept raw Bitbucket/Jira/Graphify payloads in the extractor. Rejected because it violates external-boundary isolation, requires live-service behavior to test, and makes candidate identity depend on unstable payload shapes. Alternative considered: discover associations by common identifiers. Rejected because EKG-72 requires explicit links.

### Decision: Emit existing cross-graph records, with stable observed provenance

For each eligible, resolved mapping, first look up the asserted subject in the input snapshot and require its kind to be exactly `JIRA_STORY`; a missing subject or `WORKSPACE`/other kind is a deterministic non-admission. Then construct the existing `CodeLocator(repository, merged_revision, file, symbol)` and `CrossGraphLinkClaim(subject_id, "observed-pr-change", locator)`. Construct one generic `Evidence` record with a deterministic ID and safe provenance fields: asserted association ID, PR ID, repository, merged revision, and source mapping ID. Its locator is an opaque, deterministic identifier for the PR change-set/mapping, not a URL-like external link or diff body. Only normalized payload-safe opaque URI-shaped stable identifiers may appear in these fields. Construct one `CrossGraphLinkEvidence` with a constant opaque strategy ID such as `pr-code-candidate-extraction` and the mapping identity as observation identity, then add candidate lifecycle revision `1` with the same provenance evidence.

All stable identities are based on immutable identifiers and the complete locator; PR title, display URL text, changed line numbers, source bodies, diagnostic wording, and processing order do not affect them. Sort inputs and output records by canonical IDs; use existing snapshot merging to coalesce identical records and reject conflicts. The resulting relationship kind says only that code was observed in an explicitly linked PR change set, not that it implements the engineering change.

Rationale: this uses the established immutable claim/evidence/lifecycle model exactly as intended and retains enough evidence for independent future promotion or rejection without creating code nodes.

Alternative considered: create an `IMPLEMENTS` edge from the engineering change to a synthetic code node. Rejected because the repository does not own code nodes and a changed symbol is insufficient semantic evidence. Alternative considered: store the PR relationship only as generic evidence. Rejected because it cannot support stable candidate identity or lifecycle.

### Decision: Treat non-admission as deterministic diagnostics, never partial candidates

The extractor returns `PrCodeCandidateExtractionResult(graph, metadata)` with accepted change-set, emitted claim, skipped-input, and reason counts plus sorted diagnostics. Eligible mappings with missing/ambiguous symbol resolution, incomplete locator identity, invalid identifier, non-merged status, duplicate-conflicting normalized identity, a missing graph subject, or a subject kind other than `JIRA_STORY` produce no candidate. Diagnostics include only stable safe IDs and reason codes; they never retain source payloads or hierarchical/authority-bearing URL-like external links. Where an input is otherwise admissible, its provenance evidence is retained so the non-emission can be explained without storing an external payload. Payload-safe opaque URI-shaped stable IDs may be retained as identifiers, not links.

Rationale: diagnostics preserve operational transparency while keeping candidate output conservative. The extractor needs no policy choice between possible targets.

Alternative considered: emit a file-level locator or choose the first symbol. Rejected because the cross-graph model requires complete locator targets and such a choice would falsely assert precision.

### Decision: Add an opt-in pipeline stage with explicit normalized input

Extend `run_pipeline` and `PipelineResult` with an optional tuple of normalized PR change sets and optional `pr_code_candidate_extraction` result. When `pr-code-candidate-extraction` is configured, the runner requires the input tuple and prior graph subjects, invokes the reusable extractor, merges its graph, and records the stage before derivation and validation. The runner supplies prior subjects but eligibility remains the extractor's exact `JIRA_STORY` check, so a `WORKSPACE` or other node kind yields deterministic non-admission rather than a candidate. It reports only result metadata, not raw inputs. The configuration/order checker must fail before extraction when its dependency is absent; existing empty, registry-only, and OpenSpec-only runs retain their current behavior when the stage is not configured.

The stage can run against subjects created by any earlier graph-producing adapter; EKG-72 does not prescribe a Jira-ingestion stage. Pipeline tests will provide a preexisting eligible subject through configured prior fixture graph production or a test seam consistent with the pipeline's canonical-graph boundary.

Rationale: the pipeline owns sequencing and metadata; the extractor remains reusable for tests and future adapters. An explicit argument avoids hidden filesystem or network reads.

Alternative considered: have the stage call MCP clients itself. Rejected because it would make a local deterministic pipeline depend on credentials/network and conflate extraction with acquisition.

### Decision: Preserve validation, persistence, and trust boundaries without a data migration

The producer uses the established `GraphSnapshot` cross-graph collections, generic evidence, merge behavior, persistence serialization, and graph-integrity checks. Extend validation/producer-focused tests only as needed to assert emitted records reference an existing subject and provenance evidence and have candidate lifecycle state. No storage schema migration is needed because the underlying additive collections already support absent-key defaults and these records use existing shapes.

Derivation receives candidate records but does not turn them into normal edges. The trusted cross-graph projection remains empty until a later independently evidenced lifecycle entry marks a claim `trusted`; no candidate extractor code invokes or modifies lifecycle promotion.

Rationale: this avoids a parallel candidate format and preserves compatibility with old snapshots and current consumers.

## Risks / Trade-offs

- [No real external adapter exists yet] → Specify and test a strict normalized contract with fixtures; a future adapter must satisfy it rather than changing graph semantics.
- [Association or mapping identity may be unavailable from an upstream provider] → Reject/diagnose the input rather than invent an identity or target.
- [A valid merged PR can still be mistaken for semantic implementation] → Use `observed-pr-change`, candidate lifecycle state, and explicit tests that no `IMPLEMENTS`/trusted link is emitted.
- [Diagnostics or provenance could leak PR/source payloads or URL-like external links] → Limit them to safe stable IDs, repository/revision/file/symbol locator identity, and reason codes; never retain payloads or external navigation links.
- [Identity values may disguise URLs or payloads] → Accept only payload-safe opaque URI-shaped identifiers (for example, `urn:example.org/link-42`) and deterministically reject hierarchical/authority-bearing forms (`https://…`, `custom://…`, `https:host/path`) and payload-like values at the boundary.
- [Candidate volume can grow with changed symbols] → Use deterministic linear mapping processing and ID-based deduplication; no source payloads are retained. Retention/indexing policy is deferred until volume data exists.
- [Pipeline stage ordering becomes ambiguous with future source stages] → Require explicit input and subject availability now; define additional upstream stages only when their product contracts are approved.

## Migration Plan

1. Add normalized admission records, deterministic extraction result/diagnostics, and fixture-based unit tests.
2. Build candidate claims/evidence/lifecycle entries using existing ontology records; add merge, persistence/readback, validation, and no-trust regression coverage.
3. Integrate the optional pipeline stage, dependency/order checks, and safe metadata; test legacy runs remain unchanged.
4. Run focused tests and the complete suite with no external infrastructure. Rollback removes the optional stage and extractor; existing persisted snapshots remain valid because no destructive storage migration occurs.

## Open Questions

- The task does not define the exact upstream normalized fields or source adapters for explicit engineering-change/PR associations and symbol mappings. This plan fixes the minimum project-owned contract; production adapters require a later approved provider-input contract if their data cannot provide it.
- The task does not define the independent actor, evidence type, or authorization policy for candidate promotion/rejection. This plan intentionally uses the existing lifecycle mechanism and does not decide that policy.
