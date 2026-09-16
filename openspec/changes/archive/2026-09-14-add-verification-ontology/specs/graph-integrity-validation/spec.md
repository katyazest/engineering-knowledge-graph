## ADDED Requirements

### Requirement: Graph integrity validation enforces verification ontology contracts
Graph integrity validation SHALL validate verification node natural-key IDs, payload-safe identity fields, source-artifact/evidence/provenance completeness, catalog endpoint direction for `VERIFIED_BY`, `EXECUTED_IN`, `VALIDATES`, and test-suite `CONTAINS`, and every cross-graph `verification_evidence_id` binding. It SHALL return deterministic error diagnostics for missing, unsafe, conflicting, dangling, reversed, unprovenanced, claim-kind-mismatched, or subject-mismatched verification data. It SHALL not infer a relationship, select a conflicting assertion, derive test outcome or coverage, or convert verification data into implementation truth.

#### Scenario: Invalid verification support blocks downstream use
- **WHEN** a snapshot contains a `VERIFIED_BY` support record whose verification-evidence reference is absent, not a `VERIFICATION_EVIDENCE` node, lacks complete provenance, lacks the required `VALIDATES` relationship to the claim subject, or is attached to an `IMPLEMENTS` claim
- **THEN** validation returns invalid status with a deterministic verification-contract diagnostic
- **THEN** persistence and validation-required query entry points do not expose a trusted projection from that record
