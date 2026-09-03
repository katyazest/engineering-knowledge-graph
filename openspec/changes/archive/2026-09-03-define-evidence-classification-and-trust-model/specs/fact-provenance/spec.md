## ADDED Requirements

### Requirement: Provenance-associated cross-graph support preserves evidence classification
The system SHALL preserve a cross-graph support record's declared/observed/inferred origin and authoritative/derived status with its complete provenance association without copying source content. A derived status SHALL remain consistent with the referenced provenance chain; an authoritative status SHALL be rejected when the associated provenance does not represent an authoritative external source observation. Provenance completeness alone SHALL NOT establish a support record's trust disposition or implementation proof.

#### Scenario: Derived support remains classified through provenance
- **WHEN** a cross-graph support record with derived status references a complete derived provenance chain
- **THEN** persistence and query retain the derived classification and provenance references
- **THEN** they do not infer trusted implementation from the complete chain
