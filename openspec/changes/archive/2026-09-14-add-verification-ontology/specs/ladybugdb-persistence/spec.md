## ADDED Requirements

### Requirement: Persistence round-trips verification ontology records at the current catalog revision
The persistence boundary SHALL serialize, merge, validate, and read back verification node kinds, their canonical relationships, and optional cross-graph verification-evidence support references in deterministic order at the current relationship catalog revision. It SHALL coalesce compatible records, preserve stable node and claim identities, and reject immutable conflicts or invalid verification references before replacing stored state. A valid current-format snapshot without verification records SHALL read back with no verification-specific records. A persisted earlier catalog revision SHALL be rejected before readback or write; the system SHALL NOT invent, backfill, or migrate verification node identities, relations, support references, or provenance.

#### Scenario: Verification records round-trip without implementation inference
- **WHEN** a valid current-format snapshot contains a verification chain and a verification-evidence-bound `VERIFIED_BY` support record
- **THEN** repeated persistence and readback preserve canonical IDs, relation directions, support reference, provenance references, and deterministic ordering
- **THEN** persistence adds no test-framework/CI payload, test output, URL, or `IMPLEMENTS` relationship

#### Scenario: Prior catalog revision is rejected
- **WHEN** a store declares a catalog revision earlier than the verification-ontology revision
- **THEN** persistence returns a deterministic unsupported-catalog-revision failure before exposing graph data
- **THEN** it does not rewrite the store or fabricate verification records
