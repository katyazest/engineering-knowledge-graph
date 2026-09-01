## ADDED Requirements

### Requirement: Graph integrity validation validates first-class provenance
The system SHALL validate provenance record stable IDs, required external/derived fields, timestamp and hash shapes, payload-free field constraints, referenced fact/evidence/input provenance existence, and the requirement that derived provenance has an explicit rule. It SHALL issue deterministic error diagnostics and an invalid result for any violation before downstream persistence or query use.

#### Scenario: Dangling derived provenance is invalid
- **WHEN** a derived fact references a provenance identifier absent from the snapshot
- **THEN** validation reports a deterministic error naming the affected fact and missing provenance reference
- **THEN** validation returns invalid status
