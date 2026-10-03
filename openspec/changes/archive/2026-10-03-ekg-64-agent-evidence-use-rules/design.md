## Context

`EKG-64` follows completed EKG-41 (`cross-graph-evidence-trust-model`) and EKG-43 (`evidence-freshness`). Repository evidence confirms these are executable rather than documentation-only changes: `src/engineering_kg/ontology.py`, `relationship_vocabulary.py`, `validation.py`, `freshness.py`, `query.py`, and `mcp/factmcp_server.py` provide classified support, trust projection, integrity diagnostics, as-of freshness, local query DTOs and thin agent-facing tools. `get_traceability` already distinguishes edges, support records and cross-graph candidates; `current_evidence_eligibility` is opt-in. Neither component defines a final agent evidence-use disposition or a readiness decision. The canonical relationship catalog has directed `OWNED_BY`, but no change-readiness relationship or approved readiness policy. EKG-42 conflict-aware merge rejects incompatible assertions rather than choosing by authority.

## Goals / Non-Goals

**Goals:** Implement a reusable deterministic policy at the project-owned query boundary; surface missing/stale/conflicting/candidate/inferred conditions to agents; give a bounded, explainable critical-conclusion operation; test non-fabrication through the local API and MCP boundary; publish normative consumer guidance. This is **runtime policy plus documentation**, not documentation-only: EKG-41/43 established the executable precedent and EKG-64 criterion 4 explicitly asks for E2E observable unknown/unresolved output.

**Non-Goals:** New ingestion heuristics, LLM calls, external source checks, inferred relationships, an implementation-owner discovery algorithm, change-readiness scoring/checklist, release approval, backfilling old evidence, graph trust promotion, or schema/persistence migration. EKG-61's broader context contract is downstream, not designed here.

## Decisions

### 1. Evaluate evidence use after existing admission/trust/freshness, never reclassify stored records

Implement one pure project-owned policy module consumed by the local query facade, using only canonical snapshot IDs, existing relationship catalog and trusted projection, provenance completeness, validation outcome, classified support/lifecycle and the shared freshness assessor/current-evidence guard. Its output is a query-time `supported` or `unresolved` disposition with sorted reason codes from `unknown`, `stale`, `conflicting`, `candidate`, `inferred`, plus existing support ID references. These are **evaluation reasons**, not new ontology states. Store no derived policy disposition; neither add graph edges nor mutate fact/evidence IDs. Preserve classification (`declared`/`observed`/`inferred`), lifecycle and trusted projection as separate fields. An explicit current-required check may use `fresh` only from EKG-43's caller-checked as-of assessment; `unknown` remains unknown in all other calls. For historical trust without an explicitly current-required check, unknown freshness is displayed but does not erase the trusted graph assertion.

Catalog-valid endpoints and complete provenance alone do not make a candidate authoritative; only an already admitted semantic edge or trusted cross-graph projection may support an authoritative relationship. An observed `TOUCHES` is not implementation ownership, non-confident `REFERENCES` is not traceability proof, and inferred-only `IMPLEMENTS` cannot be trusted under EKG-41. For a conflict rejected by merge, there is no queryable winning graph; for validation-required invalid input return the existing safe graph diagnostic and no partial success. On a non-validating display, unresolved references must never produce `supported`.

**Approved EKG-64 revision — overlapping candidate/conflict reasons:** For represented candidate `TOUCHES` relationships exposed by non-validating traceability, accumulate the candidate and canonical-conflict conditions before constructing the shared evidence-use result. A conflict branch must not short-circuit or replace the independently applicable `candidate` reason. Reuse the evaluator's duplicate-free lexical sorting: complete-support fixtures with only these two conditions return `["candidate", "conflicting"]` and `unresolved`, invariant under repeated evaluation and reversed assertion order. Preserve any other applicable reasons and safe existing relationship/evidence/provenance references; never select a conflicting assertion as authoritative, promote the candidate, or change stored classification/lifecycle. MCP forwards this local disposition and reason list unchanged. Validation-required calls and merge/persistence continue to reject invalid conflicting input rather than admitting it to obtain a display result. Verify the overlap with an in-memory fixture and registered fake/local MCP query factory; do not persist a conflicting fixture. This refines the existing multiple-reason policy, not relationship admission or the meaning of `TOUCHES`.

Alternative: rank by confidence/name match or amend stored trust when freshness changes. Rejected because EKG-41 forbids implicit promotion, EKG-42 forbids generic conflict winners, and EKG-43 deliberately makes freshness query-time and as-of.

### 2. Explain only a bounded proposed critical claim, not a newly invented policy

Add `explain_critical_conclusion(conclusion_type, subject_id, target_id?, checked_revisions?, current_required?)` (or an equivalent typed query operation) to the local facade; expose a thin FactMCP tool that delegates to it. Accept only `implementation_ownership` and `change_readiness` as conclusion kinds; validate the input before accessing the graph. For an exact service/repository subject and explicit target, an admitted direct `OWNED_BY` edge with complete resolved evidence/provenance, no unresolved conflict and correct direction can support **ownership of that subject only**. Return a sorted path with the edge ID, endpoint IDs, evidence IDs and transitive provenance IDs plus trust/classification (if applicable) and per-support freshness/check instant (if available). A direct edge has no cross-graph lifecycle; mark lifecycle not applicable rather than inventing one. If the caller requires current evidence, qualify every required support via EKG-43's guard. Do not infer owner of a code locator, PR or change from a repository owner, changed symbols, or a name; return unresolved/unknown with empty path when the exact direct relation is absent. Missing graph object IDs are unresolved; unsafe or malformed input is a safe error.

For `change_readiness`, even related test facts, merged PRs and fresh support do not constitute an approved readiness decision. The operation returns `unresolved` with the `unknown` reason and an empty decision path, with a safe basis identifying the absent decision contract; no positive or negative readiness judgment is produced. This is an explicit boundary, not a placeholder readiness algorithm. A future approved readiness policy would be a separate change and must supply an eligible path.

Alternative: infer implementation ownership via `IMPLEMENTS` → `OWNED_BY` or readiness via `VERIFIED_BY` and fresh tests. Rejected because graph reachability does not authorize those critical semantic conclusions and Plane supplies no transitive-owner or readiness decision criteria.

### 3. Make agent projections additive and MCP wrappers transparent

Add evidence-use fields to existing traceability relationship and cross-graph claim projections, with actual graph IDs, reason codes and status; retain existing `missing`, result containers, filters, ordering, `trusted_projection`, per-evidence freshness and optional checked-revision behavior. Do not rewrite `list_requirements`, `list_services`, `list_changes` as if nodes themselves were ownership or readiness decisions. Existing `get_traceability` tool forwards augmented query results unchanged. Add one bounded critical-conclusion tool without per-invocation graph-store path; use the established structured `GraphQueryError` envelope. New input accepts IDs, not free-text assertions, prompt text or source payloads; source-derived snippets and LLM messages are never authority inputs. Keep sanitization and payload-free diagnostics; identifier validation must avoid echoing untrusted raw values. The new operation uses validation before returning positive decisions so unresolved conflicting assertions cannot be treated as selected facts. E2E tests exercise both local persisted-readback and registered fake/local MCP tool against the same fixtures.

Alternative: implement policy in tool prompts or separately in each wrapper. Rejected because prompts are not a security boundary and duplicate implementations could diverge from the local API.

### 4. Preserve canonical and persistence contracts

The data flow is `existing GraphSnapshot / read_graph_snapshot` + optional caller-checked revisions → catalog + trust/validation + freshness → pure evidence-use evaluation → local projection DTO → thin MCP tool. No source read occurs at policy evaluation. No canonical schema, derivation rule, merge outcome, trusted edge, stable ID, snapshot codec, store version, config or external tool changes. Query results are deterministic per snapshot and checked input; reuse existing memoized per-call freshness assessment rather than traversing provenance repeatedly for each output record. Verification uses fixtures and offline mocks; no live Graphify, Jira/Bitbucket MCP, OpenLore, LadybugDB service or LLM is required.

## Risks / Trade-offs

- [Calling a direct service owner the owner of the changed code] → label the bounded result as ownership **of the exact graph subject**, never infer ownership of a code change, PR or locator.
- [Consumer confuses stale as-of evidence with a retracted historical edge] → return freshness separately and apply the freshness guard only to explicitly current-required conclusions.
- [Conflict may fail before a snapshot can be queried] → preserve EKG-42 fail-closed merge/validation diagnostic rather than manufacturing a `conflicting` winner row.
- [No approved readiness criteria] → always return unresolved for readiness and surface this explicit gap to EKG-61/future approval; tests prove no accidental `ready` output.
- [New additive fields/tool might change clients that assume closed response shapes] → preserve old keys and invocation signatures; document additive compatibility and test old callers.

## Migration Plan

1. Add pure policy evaluation, deterministic safe reason/path DTOs and unit tests for the EKG-64 matrix; reuse trust/freshness/validation rather than altering graph ingestion.
2. Integrate additive query results and the bounded critical-conclusion operation, with fixture tests for current-required behavior, absence, validation errors and deterministic path ordering.
3. Wire the thin MCP tool and document the normative agent rules; run offline persisted-readback and MCP E2E fixtures plus existing regression tests.

For the approved overlapping-reason revision, completed tasks describe the prior implementation only. Apply the pending delta in tasks 1.4 and 4.3, refresh the guidance in 3.2, and repeat matrix/regression verification in 4.2 before treating downstream implementation, TEST or review gates as current. Revalidate local/MCP reason preservation, deterministic output, candidate-only compatibility and fail-closed validation; the proposal scope, graph admission, persistence format and critical-conclusion eligibility remain unchanged.

No data migration, schema revision or infrastructure rollout is needed. Rolling back the query/tool additions leaves stored graph data untouched.

## Open Questions

Plane does not define positive change-readiness criteria or an implementation-owner inference rule beyond represented directed relationships. This revision deliberately does not answer either by guessing: readiness is unresolved and ownership is limited to the catalog's direct `OWNED_BY` for the exact service/repository. Any broader readiness or transitive ownership conclusion needs separate approval.
