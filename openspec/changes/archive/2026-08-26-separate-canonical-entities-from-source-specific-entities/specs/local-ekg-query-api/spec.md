## MODIFIED Requirements

### Requirement: Query API lists requirements deterministically
The system SHALL provide deterministic requirement query operations over canonical `requirement` facts and their evidence without exposing source-prefixed requirement kinds as a query contract.

#### Scenario: Canonical requirements are listed
- **WHEN** local code requests requirements from a graph containing canonical requirement nodes
- **THEN** the query API returns canonical identifiers, kinds, names, canonical properties, evidence identifiers, and supported locator identity fields
- **THEN** results are ordered deterministically by stable graph identity

#### Scenario: Requirements are filtered by provenance
- **WHEN** local code requests requirements filtered by an OpenSpec change or evidence reference
- **THEN** the query API filters canonical requirements through represented relationships and evidence provenance
- **THEN** it does not require, return, or infer an `openspec-requirement` node

## ADDED Requirements

### Requirement: Query API exposes canonical provenance without source payloads
The system SHALL expose each returned canonical fact's source and supported locator identity as provenance while excluding provider payload bodies and source-specific ontology aliases.

#### Scenario: OpenSpec provenance is returned
- **WHEN** a query result is supported by OpenSpec evidence
- **THEN** the result includes the evidence source, identifier, and supported OpenSpec locator identity fields
- **THEN** the result does not include full markdown content, an OpenSpec-prefixed canonical kind, or a duplicated source-owned domain object
