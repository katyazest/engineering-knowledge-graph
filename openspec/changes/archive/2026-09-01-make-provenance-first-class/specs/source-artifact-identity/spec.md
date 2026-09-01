## ADDED Requirements

### Requirement: Source-artifact identity anchors external provenance
The system SHALL use the existing complete `SourceArtifactIdentity` as the authoritative source identity and revision component of every external provenance record. It SHALL preserve the identity unchanged across normalization, evidence association, merge, persistence, queries, and cross-graph linking; navigation detail remains non-authoritative and SHALL NOT substitute for provenance fields.

#### Scenario: Source identity remains stable in provenance
- **WHEN** one authoritative artifact supports facts across multiple graph boundaries
- **THEN** every associated external provenance record references the same validated source-artifact ID and retained revision
- **THEN** display names, paths, line ranges, and navigation details do not replace it
