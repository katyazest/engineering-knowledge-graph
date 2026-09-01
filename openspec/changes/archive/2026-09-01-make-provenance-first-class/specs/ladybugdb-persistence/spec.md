## ADDED Requirements

### Requirement: Persistence preserves and safely migrates first-class provenance
The system SHALL persist and read first-class provenance with deterministic serialization, association, ordering, and merge semantics. It SHALL retain no authoritative source content. For legacy persisted evidence, it SHALL migrate only when all required provenance fields can be recovered from retained authoritative metadata; otherwise it SHALL emit a deterministic compatibility diagnostic or integrity failure, preserve the prior store/backup, and SHALL NOT fabricate timestamps, hashes, extractor metadata, rules, or input provenance.

#### Scenario: Complete legacy provenance migrates safely
- **WHEN** persisted legacy evidence retains every required first-class provenance field
- **THEN** persistence migrates it atomically, preserves canonical fact IDs, and returns deterministic payload-free readback

#### Scenario: Incomplete legacy provenance fails safely
- **WHEN** persisted legacy evidence lacks its observation time, content hash, extractor version, or required derivation information
- **THEN** persistence reports deterministic compatibility/integrity failure and does not rewrite the graph as if provenance were complete
