## ADDED Requirements

### Requirement: Graph integrity validation checks canonical references
The system SHALL validate canonical graph snapshots for broken node, edge, and evidence references before downstream query stages use the graph.

#### Scenario: Broken edge endpoint is invalid
- **WHEN** graph integrity validation reads a snapshot containing an edge whose source ID or target ID does not match an existing node ID
- **THEN** validation reports an error diagnostic identifying the affected edge and missing endpoint
- **THEN** validation returns an invalid validation status

#### Scenario: Broken evidence reference is invalid
- **WHEN** graph integrity validation reads a node or edge whose evidence ID does not match an existing evidence record ID
- **THEN** validation reports an error diagnostic identifying the affected graph object and missing evidence ID
- **THEN** validation returns an invalid validation status

### Requirement: Graph integrity validation detects duplicate identity conflicts
The system SHALL validate that canonical graph object IDs identify one deterministic serialized object per node, edge, and evidence collection.

#### Scenario: Duplicate identical objects are accepted as deterministic duplicates
- **WHEN** graph integrity validation reads duplicate graph objects with the same ID and identical serialized values in the same collection
- **THEN** validation does not report a conflicting identity error for those objects
- **THEN** validation metadata reports the duplicate identity count deterministically

#### Scenario: Duplicate conflicting objects are invalid
- **WHEN** graph integrity validation reads duplicate graph objects with the same ID and different serialized values in the same collection
- **THEN** validation reports an error diagnostic identifying the conflicting object ID and collection
- **THEN** validation returns an invalid validation status

### Requirement: Graph integrity validation checks traceability shape
The system SHALL validate derived and extracted traceability relationships against their expected graph object kinds.

#### Scenario: OpenSpec change-to-spec traceability has valid endpoints
- **WHEN** graph integrity validation reads an OpenSpec change-to-spec traceability relationship
- **THEN** validation verifies that the source endpoint is an OpenSpec active change, archived change, or change-scoped spec node
- **THEN** validation verifies that the target endpoint is an OpenSpec durable spec node

#### Scenario: Invalid traceability endpoints are reported
- **WHEN** graph integrity validation reads a traceability relationship whose endpoints do not match the expected source and target object kinds
- **THEN** validation reports an error diagnostic identifying the relationship and invalid endpoint kind
- **THEN** validation returns an invalid validation status

### Requirement: Graph integrity validation separates errors from warnings
The system SHALL classify graph diagnostics deterministically so invalid graph structure blocks later stages while non-authoritative unresolved hints remain visible without inventing links.

#### Scenario: Required unresolved reference is an error
- **WHEN** graph integrity validation reads a required mapping or traceability reference that cannot resolve to an existing graph object
- **THEN** validation reports an error diagnostic for the unresolved required reference
- **THEN** validation returns an invalid validation status

#### Scenario: Non-confident unresolved related spec is a warning
- **WHEN** graph integrity validation reads unresolved related-spec metadata that originated from manually maintained non-confident OpenSpec frontmatter
- **THEN** validation reports a warning diagnostic for the unresolved related-spec reference
- **THEN** validation does not create a target node or authoritative traceability relationship for that reference

### Requirement: Graph integrity validation reports deterministic metadata
The system SHALL return deterministic graph integrity validation metadata with validation status, diagnostics, severity counts, and graph counts.

#### Scenario: Validation metadata is stable
- **WHEN** local code runs graph integrity validation multiple times against the same canonical graph snapshot
- **THEN** each validation result reports the same status, diagnostics, severity counts, graph counts, and serialized metadata

#### Scenario: Validation metadata excludes source bodies and payloads
- **WHEN** graph integrity validation metadata is serialized
- **THEN** the metadata includes validation status, diagnostic rule IDs, severities, affected graph object IDs, messages, severity counts, and graph counts
- **THEN** the metadata excludes full requirement bodies, full markdown artifact bodies, source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads

