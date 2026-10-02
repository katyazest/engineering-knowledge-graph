## MODIFIED Requirements

### Requirement: Ontology uses catalog-defined relationship values
The canonical ontology SHALL expose relationship kind values and relationship metadata through the canonical relationship catalog. It SHALL preserve stable IDs for unchanged valid canonical relationship identities and SHALL not encode source-specific mapping labels, candidate lifecycle state, confidence, display names, or evidence content into semantic relationship identity. In-memory construction and the current-version persisted representation SHALL admit only the current canonical relationship representation. A retired alias, reversed encoding, or source-prefixed domain relationship SHALL be converted only by an explicitly version-scoped persisted-snapshot migration that has sufficient retained facts to produce the current catalog-defined relationship; it SHALL otherwise be rejected before canonical graph exposure. The canonical ontology core SHALL not contain storage-engine-specific migration behavior.

#### Scenario: Canonical identity remains stable
- **WHEN** a valid relationship is represented by its catalog-defined canonical kind and unchanged endpoints
- **THEN** its stable identity remains unchanged after the catalog is introduced

#### Scenario: Canonical relationship format round-trips
- **WHEN** a graph containing only catalog-valid current canonical relationships is persisted and read back
- **THEN** the readback preserves its canonical kinds, ordered endpoints, and stable identities deterministically
- **THEN** it does not apply an unnecessary legacy-alias or reversed-relationship conversion

#### Scenario: Versioned migration is the only legacy conversion boundary
- **WHEN** a version-scoped migration supplies a supported legacy relationship with complete approved source mapping data
- **THEN** the resulting current snapshot contains only the mapped current catalog relationship and preserved supported references
- **THEN** direct in-memory construction or current-format readback of that legacy relationship remains rejected

#### Scenario: Candidate state does not change semantic identity
- **WHEN** a supported cross-graph claim has the same subject, catalog kind, and complete `CodeLocator` target at different candidate lifecycle states
- **THEN** its claim identity remains unchanged
