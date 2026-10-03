# Agent evidence-use policy (EKG-64)

Agent-facing conclusions must be grounded in relationships and support represented in the Engineering KG. Names, similar text, prompt context, confidence labels, PR/file observations, and model-generated guesses do not create relationships or promote candidates.

Query projections may add an `evidence_use` disposition (`supported` or `unresolved`), sorted `reason_codes`, and references to graph IDs. Unresolved-information reasons are:

- `unknown`: support or provenance is absent, unresolvable, or not checked as-of the requested revision;
- `stale`: an as-of check found a revision mismatch;
- `conflicting`: an incompatible assertion conflict remains unresolved (the graph validator/merge may reject it rather than expose a winner);
- `candidate`: a candidate lifecycle or observed implementation link;
- `inferred`: support is classified as inferred.

Reasons do not rank or resolve one another. Stored trust/lifecycle and as-of freshness remain independent: unknown freshness is not stale or fresh, and historical trust is not rewritten. Freshness restricts only requests that explicitly require current evidence.

A represented candidate `TOUCHES` assertion that is also in an unresolved same-ID canonical conflict retains both `candidate` and `conflicting` reason codes, in duplicate-free lexical order (`["candidate", "conflicting"]` when no other reason applies). Its disposition stays `unresolved`: this display rule neither selects a conflict winner nor promotes the candidate. Non-validating traceability can display the represented assertions and their safe existing references; validation-required queries and graph merge/persistence still reject invalid conflicting input with no partial success. Non-conflicting candidate `TOUCHES` remains candidate-only.

Critical implementation ownership is supported only for a catalog-valid, directed, evidenced `OWNED_BY` edge from the exact represented service or repository to the requested target, with complete resolvable provenance and a valid graph. This establishes ownership of that subject only, not ownership of a change, pull request, file, code locator, or similarly named object. Change readiness is always `unresolved`/`unknown` until a separately approved readiness decision contract exists; tests, merged PRs, fresh evidence, and names are not a readiness decision.

The policy is query-time only. It does not alter graph records, IDs, persisted snapshots, source payloads, or external systems. Existing query result containers and MCP calls remain compatible; new projection fields and the opt-in `explain_critical_conclusion` operation are additive.

## EKG-64 verification matrix

| Named test / input class | Observable assertion | Anchor |
| --- | --- | --- |
| `test_similar_names_no_authority` | No authoritative relationship or owner; missing traceability stays empty/unresolved | EKG-64 criterion 1; local-ekg-query-api represented-only baseline |
| `test_prompt_guess_no_authority` | No promotion; inferred support remains labeled, implementation unresolved | EKG-64 criterion 1; EKG-41 implementation trust boundary |
| `test_missing_support_unknown` | `unresolved`/`unknown`, empty path; required validation produces existing safe graph diagnostic instead of partial success | EKG-64 criteria 2, 4; fact-provenance baseline |
| `test_stale_and_unchecked_current_required` | `stale` vs `unknown` as-of; both fail current-required check, no change to stored trust | EKG-64 criterion 2; EKG-43 freshness/current-required baseline |
| `test_conflict_no_winner` | `conflicting`/unresolved or existing merge/validation error; no selected authority | EKG-64 criterion 2; conflict-aware-graph-merge baseline |
| `test_candidate_not_authoritative` | `candidate`/unresolved for authoritative implementation; retained support | EKG-64 criterion 2; EKG-41 and relationship catalog |
| `test_candidate_touches_conflict_retains_both_reasons` | Non-validating local traceability and registered fake/local MCP preserve `unresolved` and exactly `["candidate", "conflicting"]` for complete-support candidate `TOUCHES` in an incompatible same-ID cohort, independent of repeated queries/assertion order; safe existing references only; validation-required calls return the existing safe error/no partial result; candidate-only and conflict-only cases remain compatible; no conflicted input is persisted | Approved EKG-64 revision; criterion 2; multiple-reason requirement; EKG-41/catalog candidate boundary; conflict-aware-graph-merge baseline |
| `test_inferred_not_authoritative` | `inferred`/unresolved; no trusted implementation | EKG-64 criteria 1, 2; EKG-41 trust model |
| `test_direct_ownership_path` | `supported` for same subject only, with edge/evidence/provenance IDs; no extrapolation | EKG-64 criterion 3; canonical relationship catalog |
| `test_readiness_without_contract` | `unresolved`/`unknown`; never `ready`/`not-ready` | EKG-64 criterion 3; EKG-43 explicit non-goal |
| `test_e2e_missing_evidence` | No fabricated traceability; absent support returns `unknown`/unresolved and no invented path | EKG-64 criterion 4; existing MCP local-first baseline |
