## MODIFIED Requirements

### Requirement: Graph integrity validation checks traceability shape
The system SHALL validate asserted and derived OpenSpec change-to-canonical-specification traceability relationships against source-specific change and canonical specification endpoint kinds.

#### Scenario: OpenSpec change traceability has valid endpoints
- **WHEN** graph integrity validation reads an OpenSpec change traceability relationship
- **THEN** validation verifies that its source is an `openspec-active-change` or `openspec-archived-change` node
- **THEN** validation verifies that its target is a canonical `specification` node
- **THEN** validation verifies that every referenced evidence identifier exists

#### Scenario: Retired source-prefixed domain endpoint is invalid
- **WHEN** graph integrity validation reads a relationship using `openspec-spec`, `openspec-requirement`, or `openspec-scenario` as a canonical domain endpoint
- **THEN** validation reports an error diagnostic identifying the retired source-prefixed ontology usage
- **THEN** validation returns an invalid validation status

## ADDED Requirements

### Requirement: Graph integrity validation checks canonical identity consistency
The system SHALL validate that records sharing a canonical ID have one compatible canonical kind and natural-key shape while allowing multiple evidence records to support that fact.

#### Scenario: Compatible evidence is accepted
- **WHEN** canonical facts with the same ID have compatible canonical fields and distinct valid evidence identifiers
- **THEN** validation accepts the fact as one canonical identity with multiple provenance records
- **THEN** validation does not report a duplicate identity conflict solely because the source evidence differs

#### Scenario: Incompatible canonical identity is invalid
- **WHEN** records with the same canonical ID disagree on kind or a natural-key property
- **THEN** validation reports an error diagnostic identifying the conflicting ID and fields
- **THEN** validation returns an invalid validation status
