## ADDED Requirements

### Requirement: Integrity validation enforces cross-graph evidence classification and precedence
The system SHALL validate every cross-graph observation and lifecycle-support record's classification/trust fields, classification-to-provenance consistency, and implementation-trust eligibility in the complete snapshot. It SHALL return deterministic diagnostics for invalid classification, contradictory status/provenance, missing explicit trust disposition, forbidden trusted implementation support, or automatic-promotion attempts; it SHALL not repair, rank, or backfill invalid records.

#### Scenario: Integrity validation rejects unqualified implementation trust
- **WHEN** a complete snapshot contains a trusted `IMPLEMENTS` projection without qualifying authoritative declared support
- **THEN** validation returns an invalid status with a deterministic implementation-trust diagnostic
- **THEN** persistence and validation-required query entry points reject the snapshot
