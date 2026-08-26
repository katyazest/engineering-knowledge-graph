## MODIFIED Requirements

### Requirement: Ontology represents OpenSpec extraction facts
The system SHALL provide source-independent canonical graph vocabulary for specifications, requirements, and scenarios, and source-specific vocabulary only for OpenSpec active changes, archived changes, and change artifacts.

#### Scenario: Canonical OpenSpec-backed facts are available
- **WHEN** local code constructs graph nodes for facts extracted from OpenSpec specifications
- **THEN** it can represent the facts as `specification`, `requirement`, and `scenario` node kinds without an OpenSpec-prefixed domain kind
- **THEN** each node can retain OpenSpec source evidence and serialize deterministically without external services

#### Scenario: Source-owned OpenSpec entities remain available
- **WHEN** local code constructs graph nodes for an OpenSpec change or planning artifact
- **THEN** it can represent `openspec-active-change`, `openspec-archived-change`, and `openspec-artifact` node kinds
- **THEN** their OpenSpec lifecycle identity does not become the identity of a canonical specification, requirement, or scenario

### Requirement: Stable IDs are deterministic
The system SHALL provide deterministic stable ID generation for canonical ontology objects based on object kind and explicit source-independent identity parts.

#### Scenario: Same canonical identity produces same ID
- **WHEN** local code generates a stable ID twice using the same canonical object kind and natural-key identity parts
- **THEN** both generated IDs are identical

#### Scenario: Source locator does not affect canonical identity
- **WHEN** the same canonical fact is supported by evidence with different source names, file paths, headings, or line ranges
- **THEN** its canonical stable ID is unchanged
- **THEN** those source-specific values are retained only in evidence or locator data

## ADDED Requirements

### Requirement: Canonical facts preserve source provenance
The system SHALL attach evidence identifiers to canonical nodes and relationships and SHALL keep provider-specific locators and payload metadata outside canonical identity and domain vocabulary.

#### Scenario: Canonical fact has OpenSpec evidence
- **WHEN** an OpenSpec adapter emits a canonical specification, requirement, scenario, or relationship
- **THEN** the fact references OpenSpec evidence containing its supported locator identity
- **THEN** the canonical fact does not expose `openspec_identity`, scope, or source path as a required identity field
