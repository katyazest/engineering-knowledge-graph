## Context

Plane `EKG-43` (`8a974c15-bb39-4bfb-b633-291d78a7c163`) is unblocked by completed EKG-40. `ProvenanceRecord` already retains `SourceArtifactIdentity.revision_or_version`, `observed_at`, hash, extractor ID/version and derived input IDs; `Evidence.provenance_ids` associates it with facts. `GraphSnapshot`, the snapshot codec, the local query facade, and thin FactMCP tools preserve these references. None of these records says what revision the authoritative source has *now*. An observation time is about extraction, not proof of later source change. Current cross-graph trust and scenario-test execution projections are not freshness assessments; the repository has no critical-readiness checker to retrofit.

Implementation is wholly in project-owned Python assessment/query/wrapper modules and fixtures. Graphify, Jira/Bitbucket MCP, OpenLore, LadybugDB and FactMCP runtime remain external boundaries; do not query their internals or retain source payloads to guess current revisions. A caller/integration that has already checked an authoritative source supplies the result; this code cannot independently authenticate that claim.

## Goals / Non-Goals

**Goals:** Provide as-of `fresh`/`stale`/`unknown` evaluations for individual provenance chains, display them with their evidence association in existing query outputs, and supply a fail-closed current-evidence guard to explicitly current-required checks without confusing freshness with trust.

**Non-Goals:** Poll external sources; decide how to choose a live/current revision for a provider; apply a time-to-live; recalculate persisted facts/trust or relationship catalog membership; redefine critical readiness policies; implement EKG-64 or EKG-67; alter OpenLore index `freshness_policy`; migrate graph records.

## Decisions

### 1. Assess against a checked logical-artifact revision, not age

Define a small source-agnostic assessment input `CheckedSourceRevision` (or equivalent validated DTO) with `(source_type, source_identity, artifact_type, stable_locator, revision_or_version, checked_at)`. Its key is the four `SourceArtifactIdentity` fields excluding revision. `checked_at` is an offset-aware ISO-8601 instant provided by the checker: the result is explicitly **as of this check**, not a statement about query-time state. The normalized revision is an opaque equality-comparable version; no lexical/semantic ordering, clock skew rule, or Git-specific comparison. Same key + same revision -> `fresh`; same key + different revision -> `stale`; absent/unavailable/unmatched check -> `unknown`. The source must have been checked authoritatively by the supplying caller. The API validates input shape and consistency, not the caller's authority; documentation and output must not imply a network/source read by the graph query layer.

Require complete valid source/extraction metadata from existing EKG-40 provenance before comparing. Its `observed_at`, content hash, extractor ID/version explain *what and when* was extracted but cannot stand in for a current source revision. Compare offset-aware `checked_at` with `observed_at`: a check predating the observation yields `unknown`, not evidence of currentness or staleness. A stable content hash with a later checked changed source revision still yields stale relative to the revision; a different hash/extractor version without a checked current revision yields unknown. Use a separate `FreshnessAssessment` value (`status`, safe `reason`, optional `checked_at`, provenance/evidence references); do **not** add a mutable freshness field to `SourceArtifactIdentity` or `ProvenanceRecord`. Alternative: age threshold or mutable stored status. Rejected because neither proves a revision changed, and a stored freshness label is outdated as soon as a source changes.

### 2. Reuse the provenance graph to propagate uncertainty

Assess external provenance by key lookup, then derived provenance recursively over `input_provenance_ids` (stale if any stale, otherwise unknown if any unknown, otherwise fresh). Derived `observed_at`/hash are not source-revision checks. When different inputs have different `checked_at` values, expose each source's as-of instant; a derived fresh status is conditional on those supplied checks, not a claim that all sources were simultaneously checked. Memoize assessments by provenance ID for a single call; guard against missing references or cycles before considering a chain fresh. Invalid references remain invalid under existing graph-integrity rules when validation is required, and are never current-eligible in the guard; an unvalidated display can report `unknown`/unresolved without claiming success. Preserve each independent chain's status. At an `Evidence` association, fresh means at least one complete fresh chain, unknown if no fresh chain but an unknown chain, otherwise stale if all represented chains are stale; empty or internal-only support is unknown. Never use a stale chain just because the same fact has another fresh support: the check names its *specific support*. Multiple evidence records for a fact remain separately identified, not flattened into one fact-level truth value.

Alternative: take the latest provenance by observation time, or mark the whole fact stale when any old support exists. Rejected: latest does not prove currentness, and facts can legitimately have independent old and current support. Preserving both prevents hiding old evidence and allows a genuinely fresh independent chain to qualify.

### 3. Provide a fail-closed, opt-in current-required guard, not a new trust policy

Expose a reusable `current_evidence_eligibility(evidence_ids, checked_revisions)` decision (or equivalent) that evaluates the exact support selected by a caller. One specifically selected evidence record qualifies only if it has at least one complete fresh provenance chain; if a check depends jointly on multiple evidence records, every required record must qualify. Missing, stale, unknown or malformed chains fail closed. Report which support IDs qualified and which did not. Query DTOs carry per-evidence `current_evidence_eligible` for an explicitly current-required consumer; they do not relabel `trusted_projection`, `execution_state`, `confidence`, or an `IMPLEMENTS` relation. A consumer that does not declare a current-evidence requirement continues to use its existing policy.

Alternative: globally invalidate every historical `trusted` claim or reject graph snapshots containing stale evidence. Rejected: stored trust/classification is an audit fact, the graph can validly contain stale observations, and Plane does not identify which workflows require current evidence. The guard is the enforceable boundary for such workflows; neither this change nor a generic validator invents a readiness decision.

### 4. Integrate once at the reusable query layer and forward through wrappers

Add optional checked revision observations to existing local query entry points (`list_requirements`, `list_services`, `list_changes`, `get_traceability`, and other existing evidence-bearing PR/scenario query projections). Preserve their return containers, old fields, query filters, explicit missing behavior and deterministic sort order. Add `evidence_freshness` records keyed by evidence ID with individual referenced provenance assessments and `current_evidence_eligible`; include as-of `checked_at` and safe match/mismatch/no-check reason; on returned `provenance` entries, annotate their individual assessment so an agent can follow derived input IDs. For cross-graph observations and lifecycle support, attach assessment to the existing `provenance_evidence_id`; for PR/scenario projections attach it to existing evidence/provenance IDs rather than making an unrelated aggregate status. New fields are additive. A query with no revision input returns `unknown` for external support rather than a blanket currentness assertion. Malformed/unsafe or duplicate-conflicting check inputs fail the whole request with a safe structured query error; identical duplicates coalesce. Checks for unrelated keys cannot be used to make support fresh.

The four existing FactMCP tool signatures gain only optional checked revision observations and delegate to local query methods; continue binding the store at startup. Wrap input errors in the existing structured error envelope, avoiding raw user values and partial successful responses. No new provider schema, CLI infrastructure, external call, or separate MCP tool is necessary. Use already supported source identity validation rules; reject unsafe values (including payloads/URLs/credentials), missing revision, naive/invalid `checked_at`, and same-key conflicts before assessment. No repository path input is added to tool schemas. Alternative: implement comparison in each MCP tool or return a single fact-level boolean. Rejected because it duplicates policy and hides which provenance is stale.

### 5. Retain persistence and stable identities unchanged

Do not serialize `CheckedSourceRevision` or `FreshnessAssessment` into `GraphSnapshot`, its current-version codec, LadybugDB-compatible store, or immutable provenance. The snapshot remains an historical observation. Merge, derivation, `validate_graph_integrity`, claim/evidence/provenance ID generation and existing guarded migrations retain their contracts. This change needs no schema version bump, data migration, backup operation, or external configuration change. Run fixture-only query/readback tests to prove additive outputs for an unchanged persisted graph and identical repeated assessments. Alternative: persist current revision on `SourceArtifactIdentity`; rejected because it would change its stable ID and invalidate historical observation references as sources advance.

## Data Flow

`existing validated GraphSnapshot or persisted readback` + `optional caller-checked revision observations` → `validated keyed check map` → `memoized external/derived provenance assessments` → `evidence-specific current-eligibility guard` → `local query DTOs` → `thin FactMCP result`. No revision input means no new source contact and `unknown`. `checked_at` describes the caller's source check, never a TTL computation or a generated timestamp.

## Risks / Trade-offs

- [A caller supplies a wrong or old checked revision] → label the result as of the supplied `checked_at` and document the caller's authoritative-check responsibility; this service can validate shape but cannot authenticate a provider check. A freshness assertion is conditional on that input.
- [Consumer confuses fresh with trust, passing a PR observation as implementation proof] → keep existing classification/trusted projection untouched and test fresh-but-untrusted support.
- [A graph contains invalid/missing provenance chains] → validation-required paths retain existing integrity failure; guard fails closed, non-validating display cannot claim fresh from unresolved chains.
- [Additional traversal per returned support] → cache by provenance ID and artifact key for the duration of a query; no source/network calls and no graph rewrite.
- [No Plane acceptance criteria name particular critical readiness checks] → implement the explicit reusable current-required guard and query support; designation/integration of a concrete release or agent readiness workflow requires a separate approved decision, not an assumed policy in EKG-43.

## Migration Plan

1. Implement pure input validation/assessment and eligibility in a shared project-owned module, with fixture tests for the evidence-freshness matrix.
2. Add deterministic annotations to local query DTOs and exercise all existing evidence-bearing projection paths, missing-result behavior, invalid input errors, and unchanged trust.
3. Forward optional checked inputs through the existing four FactMCP tools and document their as-of/caller-attested contract; test local-only behavior with a fake query facade.
4. Verify identical persisted snapshot readback and historical IDs while assessments vary only with supplied checks. No data migration, rollout flag, or rollback of stored data is needed; reverting the additive query/wrapper behavior leaves the store untouched.

## Open Questions

Plane does not identify a particular critical readiness workflow or explicit acceptance criteria. EKG-43 provides a current-required decision for consumers that opt into it; whether a future workflow must require it is not decided here. The choice of authoritative source-check integration and its authentication are also outside this local assessment change.
