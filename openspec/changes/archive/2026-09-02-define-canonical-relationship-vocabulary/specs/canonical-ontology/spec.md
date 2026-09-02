## ADDED Requirements

### Requirement: Ontology uses catalog-defined relationship values
The canonical ontology SHALL expose relationship kind values and relationship metadata through the canonical relationship catalog. It SHALL preserve stable IDs for unchanged valid canonical relationship identities and SHALL not encode source-specific mapping labels, candidate lifecycle state, confidence, display names, or evidence content into semantic relationship identity. It SHALL persist and read back only the current canonical relationship representation; legacy aliases and reversed relationship encodings are not accepted or migrated. EKG-38 is anchored to the greenfield baseline that EKG has no historical deployment or persisted graph data, so it SHALL NOT add compatibility, migration, backup, or rollback behavior; any such behavior requires a future explicit requirement supported by concrete evidence of pre-canonical data.

#### Scenario: Canonical identity remains stable
- **WHEN** a valid relationship is represented by its catalog-defined canonical kind and unchanged endpoints
- **THEN** its stable identity remains unchanged after the catalog is introduced

#### Scenario: Canonical relationship format round-trips
- **WHEN** a graph containing only catalog-valid current canonical relationships is persisted and read back
- **THEN** the readback preserves its canonical kinds, ordered endpoints, and stable identities deterministically
- **THEN** it does not apply a legacy-alias or reversed-relationship conversion

#### Scenario: Candidate state does not change semantic identity
- **WHEN** a supported cross-graph claim has the same subject, catalog kind, and complete `CodeLocator` target at different candidate lifecycle states
- **THEN** its claim identity remains unchanged
