## ADDED Requirements

### Requirement: Query results expose represented first-class provenance
The system SHALL return the complete represented provenance records and stable IDs associated with queried facts and traceability relationships, including source identity/revision, observation time, content-hash algorithm/digest, extractor identity/version, derivation rule, and input provenance references where present. Results SHALL be deterministic and SHALL exclude source bodies, provider payloads, credentials, tokens, and URLs.

#### Scenario: Query returns external and derived explanation chain
- **WHEN** a caller queries a fact or traceability relationship supported by external and derived provenance
- **THEN** the result includes its deterministic provenance records and reference chain
- **THEN** it does not return authoritative source content or infer unrepresented provenance
