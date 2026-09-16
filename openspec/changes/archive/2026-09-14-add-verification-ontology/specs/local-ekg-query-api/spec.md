## ADDED Requirements

### Requirement: Query API exposes represented verification traceability without inference
The local query API SHALL expose deterministic, payload-free projections of catalog-valid `VERIFIED_BY`, `EXECUTED_IN`, `VALIDATES`, and test-suite `CONTAINS` relationships adjacent to a requested represented graph object, and any represented cross-graph `verification_evidence_id` support reference. Query output SHALL retain only canonical IDs, kind, approved properties, relationship/evidence/provenance references, and supported locator identity fields in deterministic order. It SHALL not retrieve test systems, return framework/CI payloads, test logs, URLs, credentials, tokens, source code, source-code line content, inferred test coverage or outcome, automatically trusted verification, or an implementation conclusion not represented by an existing trusted projection.

#### Scenario: Query distinguishes verification support from implementation truth
- **WHEN** a caller queries a requirement with represented test/run/evidence facts and a cross-graph `VERIFIED_BY` candidate supported by verification evidence
- **THEN** the response distinguishes the verification relationships, support classification/lifecycle, and trusted-projection result deterministically
- **THEN** it does not label the candidate or related test-code association as `IMPLEMENTS`
