## Context

Plane task `EKG-41` (`fdd1423b-b900-4bbd-969a-0dc84bc614aa`) requires an explicit provenance and trust model for cross-graph relations. The current graph has immutable first-class provenance, candidate observations, lifecycle revisions, a relationship catalog, and trusted-link projection. It can establish that support exists and that a claim was explicitly marked trusted, but it cannot tell consumers whether that support is a declared mapping, a PR/file observation, or an inference, nor prevent LLM-only or observed evidence from appearing as implementation proof.

The affected surface is project-owned local Python: ontology records, normalized adapters, cross-graph merge/projection, integrity validation, current-format persistence, and local query DTOs. Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, and LLM providers remain external identity-level inputs and are neither called nor changed. Source/provider/LLM content continues to be excluded from the canonical graph.

## Goals / Non-Goals

**Goals:**
- Add one immutable, deterministic classification/trust contract to cross-graph observations and lifecycle support.
- Distinguish evidence origin (`declared`, `observed`, `inferred`), evidence status (`authoritative`, `derived`), explicit confidence, and trust disposition without changing claim identity.
- Enforce precedence conservatively: declared authoritative support can qualify an explicit trusted decision; observation and inference never self-promote, and PR/file or LLM-only evidence cannot prove `IMPLEMENTS`.
- Preserve the result through merge, validation, current-format persistence/readback, and local query projection.

**Non-Goals:**
- Define an ordinal confidence scale, confidence calculation, evidence scoring, trust actor, approval UI/workflow, or automatic promotion policy.
- Treat merged PRs, files, symbol mapping, evidence counts, source order, or LLM output as implementation proof.
- Change Graphify, provider/LLM payload contracts, OpenLore resolution, network behavior, source-code retention, or canonical claim IDs.
- Migrate, backfill, or guess classification/trust fields for historical records. The current canonical persistence boundary already rejects unsupported formats; compatibility requires a future approved requirement and concrete legacy-data evidence.

## Decisions

### 1. Model classification on each support record, not on the claim

Extend `CrossGraphLinkEvidence` and `CrossGraphLinkLifecycle` (or an equivalent immutable support record referenced by each) with `origin`, `status`, `confidence`, and `trust_disposition`. Define closed enums for origin, status, and disposition; retain confidence as a non-empty payload-safe opaque label with no ordered semantics. For `CrossGraphLinkEvidence`, validate `strategy_id` and `observation_id` as non-empty payload-safe opaque identifiers under the existing identifier baseline: allowed opaque URI-shaped stable identifiers remain identifiers, while source content, provider payloads, credentials, tokens, and URL-like/hierarchical or authority-bearing forms are rejected. This keeps the explicit user-requested confidence representation without inventing a product confidence scale.

The immutable support identity includes the classification/trust fields so a record cannot be silently reclassified during merge. `CrossGraphLinkClaim.id` remains based only on subject, relationship kind, and complete `CodeLocator`; it is deliberately unchanged.

Alternative: place one classification or score on the claim. Rejected because one claim can accumulate incompatible declared, observed, and inferred support, and a claim-level value would discard audit context or require an invented aggregation policy.

### 2. Separate evidence eligibility from lifecycle state and relationship validity

Add reusable trust-policy helpers, adjacent to the relationship vocabulary, which consume only a canonical claim, its classified observation/lifecycle support, complete provenance resolution, and current lifecycle. Relationship catalog validation stays first: it decides whether a relationship kind and endpoints are possible. The trust policy then decides whether the supported claim is eligible for trusted projection.

For `IMPLEMENTS`, trusted eligibility requires all existing catalog/provenance/lifecycle conditions plus authoritative declared support. Observed PR/file evidence remains valid evidence of a `TOUCHES` candidate but cannot satisfy implementation eligibility. LLM-only inferred support stays retained as inferred and untrusted for implementation. The `trusted` lifecycle state never substitutes for the qualifying support class. For all relations, precedence is an eligibility rule rather than an evidence-ranking algorithm: individually valid conflicting support coexists and never selects a winner automatically.

Alternative: use confidence thresholds or source precedence to select a trusted claim. Rejected because EKG-41 does not approve a score scale, threshold, or automatic promotion, and this would turn observations into semantic truth.

### 3. Normalize source labels at adapter boundaries and fail closed

Normalized project-owned adapters explicitly assign the classification: an explicit declared mapping is `declared` and authoritative only when the adapter has authoritative source provenance; merged PR changed-symbol output is `observed` and derives its existing candidate lifecycle; an LLM adapter, if supplied in the future, must mark LLM-only support `inferred` and cannot emit trusted implementation. Unrecognized source categories, absent classification, unsafe confidence text, payload-bearing `strategy_id` or `observation_id`, and incompatible status/provenance are rejected with stable diagnostics before serialization or graph emission.

No provider-specific enum or payload schema enters the ontology. The PR candidate extractor retains only its existing identity-level change-set/mapping data; it gains classification constants rather than source content.

Alternative: infer classification from strategy ID, evidence source, or provenance kind at query time. Rejected because strategy labels are not a trust contract, provenance `derived` does not itself mean inferred, and delayed inference would make persistence and audit ambiguous.

### 4. Enforce the model at merge, validation, persistence, and query boundaries

`GraphSnapshot` construction and merge validate immutable record shape and coalesce only equivalent classified support. The integrity validator checks all snapshot-level references, classification-to-provenance consistency, explicit lifecycle disposition, and forbidden trusted `IMPLEMENTS` projections. It reports stable rule IDs and performs no repairs.

Persistence serializes/deserializes only the expanded current canonical support shape, validates before write and after readback, and rejects records missing the new fields or carrying a payload-bearing observation `strategy_id` or `observation_id`. Increment the catalog/schema revision used by the existing current-format persistence guard so old payloads cannot be misread as classified records. No migration, backup, or rollback path is planned because no mapping from absent historical classifications to the approved contract exists.

The query DTO projects a claim's current lifecycle and trusted-projection result alongside every support record's stored classification and provenance reference, plus only admitted opaque observation identifiers. Query is a presentation boundary: it neither recalculates confidence nor decides trust, and cannot expose identifiers rejected before serialization/persistence. It continues to sanitize source bodies, provider payloads, LLM prompts/responses, credentials, tokens, and URLs.

Alternative: allow old records with a default `observed`/`untrusted` value. Rejected because it fabricates provenance/trust facts and conflicts with the explicit EKG-41 model.

## Data Flow

`normalized declared mapping | PR/file observation | future LLM inference` → `payload-safe provenance` + `classified support record` → `cross-graph claim and explicit lifecycle` → `merge` → `catalog + trust-policy + integrity validation` → `current-format persistence/readback` → `local claim projection`.

Trusted `IMPLEMENTS` flow additionally requires: `authoritative declared observation` + `explicit trusted lifecycle` + existing catalog and complete-provenance checks. PR/file and LLM-only flows terminate in auditable non-trusted support for implementation.

## Risks / Trade-offs

- [Existing tests and fixtures construct support records without new fields] → update all project-owned constructors and fixtures atomically; reject old serialized forms rather than defaulting.
- [“Confidence” is interpreted as a numeric policy] → keep it opaque and non-ordering; a threshold or scale is an explicit future change candidate.
- [A declared source is mislabeled authoritative by an adapter] → require complete source-artifact provenance and central classification/provenance consistency validation; external authority remains an adapter admission responsibility.
- [Consumers mistake trusted lifecycle for trusted implementation] → return both stored support classification and projection result, and test the negative PR/LLM cases.

## Migration Plan

1. Add classification enums/value object, safe-field validation including opaque observation identifiers, identity behavior, and reusable trust-policy helpers.
2. Update the PR candidate adapter and cross-graph constructors to emit explicit observed support; prepare declared and inferred normalized boundary handling without adding external calls.
3. Thread fields through merge, integrity validation, trusted projection, persistence serializer/deserializer, and catalog/schema revision.
4. Extend query DTOs and documentation with deterministic classified support and projection results.
5. Exercise every verification-matrix row across model, adapter, merge, validation, serialization, persistence/readback, and query tests.

No data migration or rollback is applicable: old persisted forms lack the facts required to classify support safely and are rejected. A future compatibility request must supply evidence of deployed historical data and an approved mapping.

## Open Questions

None. EKG-41 does not authorize a confidence scale, threshold, or automated trust decision; the design preserves confidence as an explicit opaque value.
