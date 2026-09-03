## 1. Canonical evidence-trust contract

- [x] 1.1 Add immutable canonical origin, status, trust-disposition, payload-safe opaque-confidence, and payload-safe opaque `strategy_id`/`observation_id` validation for cross-graph observation and lifecycle support records; verify invalid and unsafe values fail before serialization and snapshot emission.
- [x] 1.2 Include classification/trust fields in support-record identity, deterministic serialization, and merge conflict/coalescing behavior while preserving `CrossGraphLinkClaim` stable IDs; add model-level idempotency tests.
- [x] 1.3 Add reusable relationship/trust-policy helpers that apply catalog validation first and explicit evidence eligibility second; verify that no confidence/order/count rule promotes a claim.

## 2. Source normalization and cross-graph projection

- [x] 2.1 Update PR changed-symbol candidate extraction to emit explicit observed, non-trusted support and candidate lifecycle classification without retaining provider payloads; test merged PR/file evidence cannot prove `IMPLEMENTS`.
- [x] 2.2 Implement normalized declared-support admission and future inferred/LLM-only boundary validation using only canonical identity-level inputs; test authoritative/provenance consistency and fail-closed unsupported source categories.
- [x] 2.3 Update trusted-link projection to require qualifying authoritative declared support plus explicit trusted lifecycle for `IMPLEMENTS`, while retaining valid observed/inferred support as auditable non-trusted evidence; test positive declared and negative PR/LLM cases.

## 3. Integrity and persistence

- [x] 3.1 Extend graph integrity validation with deterministic classification, provenance-consistency, precedence, and forbidden implementation-trust diagnostics; test validation-required query and persistence rejection paths.
- [x] 3.2 Extend current-format graph persistence serialization/deserialization and schema/catalog revision for classified support records; reject records missing the new fields or carrying payload-bearing `strategy_id`/`observation_id` values without defaulting or migration, and test deterministic round trips and malformed readback.

## 4. Query and documentation

- [x] 4.1 Extend local cross-graph query DTOs to return stored origin, status, confidence, trust disposition, lifecycle, provenance references, admitted opaque observation identifiers, and trusted-projection result without recalculation or payload leakage; add deterministic query tests proving rejected identifiers are not queryable.
- [x] 4.2 Publish the cross-graph evidence classification/trust reference and EKG-41 verification matrix, including the absence of a confidence scale and legacy backfill; ensure it remains aligned with the executable catalog/policy.

## 5. Verification

- [x] 5.1 Exercise every approved verification-matrix row across ontology, adapter, merge, validation, serialization, persistence/readback, and query tests, including declared-authoritative admission, observed PR/file and LLM-only implementation rejection, conflicting support retention, invalid-field and payload-bearing identifier rejection, identifier persistence/query-boundary exclusion, and repeated support coalescing.
- [x] 5.2 Run the complete local automated suite and verify no test requires live Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, or LLM infrastructure.
