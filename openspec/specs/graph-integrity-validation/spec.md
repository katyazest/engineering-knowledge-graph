## Purpose

The `graph-integrity-validation` capability defines deterministic validation of canonical Engineering KG graph references, identity stability, and traceability shape.
## Requirements
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

### Requirement: Graph integrity validation validates first-class provenance
The system SHALL validate provenance record stable IDs, required external/derived fields, timestamp and hash shapes, payload-free field constraints, referenced fact/evidence/input provenance existence, and the requirement that derived provenance has an explicit rule. It SHALL issue deterministic error diagnostics and an invalid result for any violation before downstream persistence or query use.

#### Scenario: Dangling derived provenance is invalid
- **WHEN** a derived fact references a provenance identifier absent from the snapshot
- **THEN** validation reports a deterministic error naming the affected fact and missing provenance reference
- **THEN** validation returns invalid status

### Requirement: Graph integrity validation enforces relationship vocabulary
Graph integrity validation SHALL validate every canonical edge and trusted cross-graph link against the relationship catalog's kind, ordered endpoint contract, cardinality, semantic/trust classification, evidence references, and provenance requirements. It SHALL report deterministic error diagnostics for violations before persistence or downstream query use.

#### Scenario: Invalid trusted link fails validation
- **WHEN** a trusted cross-graph link uses a non-catalog kind or a subject kind not allowed for its `CodeLocator` target
- **THEN** validation reports an error diagnostic identifying the claim or link
- **THEN** validation returns invalid status

### Requirement: Integrity validation enforces cross-graph evidence classification and precedence
The system SHALL validate every cross-graph observation and lifecycle-support record's classification/trust fields, classification-to-provenance consistency, and implementation-trust eligibility in the complete snapshot. It SHALL return deterministic diagnostics for invalid classification, contradictory status/provenance, missing explicit trust disposition, forbidden trusted implementation support, or automatic-promotion attempts; it SHALL not repair, rank, or backfill invalid records.

#### Scenario: Integrity validation rejects unqualified implementation trust
- **WHEN** a complete snapshot contains a trusted `IMPLEMENTS` projection without qualifying authoritative declared support
- **THEN** validation returns an invalid status with a deterministic implementation-trust diagnostic
- **THEN** persistence and validation-required query entry points reject the snapshot

### Requirement: Integrity validation enforces PR evidence, relation origin, and candidate scope consistency
Graph integrity validation SHALL validate PR evidence stable identity, payload-safe source references, repository endpoint, merged status, immutable base/head revisions, source-artifact/provenance resolution, declared intended-change association endpoint, and observed PR-to-repository relation. It SHALL validate that each PR-scoped cross-graph observation references its represented PR and declared association and that its locator repository/head revision agree with the PR evidence. It SHALL report deterministic errors and SHALL not repair, infer, default, or promote invalid PR evidence.

#### Scenario: Inconsistent PR evidence makes the snapshot invalid
- **WHEN** a snapshot contains a PR evidence record with a dangling source/provenance reference, unsupported association endpoint, duplicate-conflicting revision identity, or a candidate locator that differs from the PR repository or head revision
- **THEN** validation returns invalid status with a deterministic diagnostic naming the affected record and violated PR-evidence rule
- **THEN** later persistence-required query and trusted projection boundaries reject the invalid snapshot

