## ADDED Requirements

### Requirement: Persisted logical snapshots declare an ontology schema version
The persistence codec SHALL store `ontology_schema_version` as a top-level positive integer in every newly initialized, newly written, or successfully migrated logical graph snapshot document. The initial current value SHALL be `1`. The version identifies the complete project-owned persisted ontology schema, including serialized record shapes, stable-identity interpretation, and relationship representation; it SHALL be independent of the in-memory `GraphSnapshot` API. `catalog_revision` SHALL remain serialized relationship-catalog metadata and SHALL be validated for the selected schema version, but it SHALL NOT by itself select a schema migrator.

#### Scenario: New snapshot has explicit schema version
- **WHEN** the persistence boundary initializes an empty store or serializes a valid current canonical snapshot
- **THEN** the logical snapshot document contains `ontology_schema_version: 1` and the expected current `catalog_revision`
- **THEN** readback reconstructs the same current canonical snapshot deterministically

#### Scenario: Version representation is invalid
- **WHEN** a persisted document supplies a missing, boolean, non-integer, zero, negative, or otherwise malformed `ontology_schema_version` and it does not match an explicitly registered legacy descriptor
- **THEN** the migration boundary returns a deterministic version-format or unsupported-version failure before exposing a graph snapshot
- **THEN** it does not infer a version from display values, record order, current runtime defaults, or an incidental storage path

### Requirement: Migration compatibility is explicit and forward-only
The system SHALL migrate a persisted document only when an explicitly registered source descriptor and deterministic forward migration path lead to the current ontology schema version. The initial compatibility set SHALL include (a) a versionless current-canonical descriptor that requires the current relationship catalog revision and current decodable record shapes, and upgrades only the missing version marker, and (b) the already-defined versionless OpenSpec-prefixed descriptor whose complete retained natural keys, relationship mappings, evidence, and provenance support deterministic canonicalization. The migration registry SHALL reject all other versionless documents. Each future schema version SHALL define its source-version compatibility, adjacent forward transform, target version, expected catalog revision, and validation rules; a reader SHALL NOT downgrade a newer snapshot, skip an unregistered transition, or treat a catalog-revision change as compatible without such a path.

#### Scenario: Supported legacy snapshot migrates through a registered path
- **WHEN** a versionless persisted snapshot matches the supported OpenSpec-prefixed descriptor and contains the retained data required by the canonical ontology migration contract
- **THEN** the migration boundary applies the registered forward transform, rewrites the document at schema version `1`, and produces only current canonical node, relationship, identity, evidence, and provenance representations
- **THEN** repeated migration finds the current version and produces no additional records or semantic changes

#### Scenario: Versionless snapshot without an approved descriptor is rejected
- **WHEN** a persisted document lacks `ontology_schema_version` but is neither a valid current-canonical document nor a complete supported OpenSpec-prefixed source document
- **THEN** the migration boundary returns a deterministic unsupported-ontology-schema-version or unsupported-legacy-format failure
- **THEN** it does not add a version marker, select a descriptor by input order, or expose partial graph data

#### Scenario: Future or unchained version is rejected
- **WHEN** a document declares a schema version later than the runtime current version or an earlier declared version for which no complete registered forward chain exists
- **THEN** the migration boundary returns a deterministic unsupported-ontology-schema-version failure identifying only safe version and migration identifiers
- **THEN** it performs no downgrade, partial upgrade, or graph replacement

### Requirement: Migration validates complete output and fails without data fabrication
The migration boundary SHALL transform a complete logical snapshot document in memory, validate the target document with the current persistence decoder, canonical identity rules, relationship catalog, provenance rules, and graph-integrity validation, and return a deterministic payload-safe result. A successful result SHALL identify source and target schema versions, applied migration identifiers, migration status, and final graph counts. A transform SHALL preserve supported stable facts and references or reject the source; it SHALL NOT fabricate canonical natural-key values, relationship direction or meaning, provenance, PR revisions or associations, verification facts or support, lifecycle decisions, confidence, or trust state.

#### Scenario: Incomplete source data fails closed
- **WHEN** a registered source format lacks a field required to reconstruct its current canonical identity, relationship, provenance, PR evidence, or verification support
- **THEN** migration returns a deterministic integrity or compatibility failure before returning a target snapshot
- **THEN** the failure metadata excludes source bodies, provider payloads, credentials, tokens, and competing asserted values

#### Scenario: Current document is a deterministic no-op
- **WHEN** a valid persisted document already declares schema version `1` and satisfies its catalog and current-format validation rules
- **THEN** migration returns a `not-needed` result with source and target version `1` and no applied migration identifiers
- **THEN** its canonical serialization and graph counts remain unchanged

### Requirement: Migration core is storage-engine independent
The migration registry, source recognition, transforms, version selection, and target validation orchestration SHALL operate on the project-owned logical snapshot document and canonical models, not on LadybugDB APIs, database queries, file paths, or database-specific schema features. A storage adapter SHALL be responsible only for loading the logical document, requesting migration, and atomically committing an approved target document through its own persistence mechanism. A future graph-database adapter SHALL be able to reuse the same migration core by supplying and committing the logical snapshot document without altering migration semantics.

#### Scenario: Migration runs with an adapter-neutral logical document
- **WHEN** a test invokes the migration core with an in-memory logical snapshot document representing a supported source version
- **THEN** it receives the same deterministic migration result as the local persistence adapter for equivalent data
- **THEN** the migration core performs no file, network, LadybugDB, or database-driver operation

### Requirement: Ontology migration verification matrix bounds compatibility testing
The change SHALL document and test this verification matrix: a new or current version-`1` document with the expected catalog revision is admitted; a versionless current-canonical document matching its descriptor is upgraded only with the version marker; a complete supported OpenSpec-prefixed legacy document migrates to current canonical records; a versionless unrecognized document, malformed version value, unsupported past version, unchained version, future version, catalog-version mismatch, incomplete source identity/provenance/PR/verification data, migration conflict, and invalid target validation are rejected; successful migration is idempotent; and every rejection leaves persisted source state unchanged. The matrix is anchored to Plane task `EKG-66`; cases outside it are CHANGE_CANDIDATE findings unless they violate another approved requirement or applicable baseline.

#### Scenario: Matrix cases are executable
- **WHEN** the ontology migration test suite runs the approved matrix cases against fixture documents and an adapter-neutral migration entry point
- **THEN** every case has the documented admission, migration, no-op, or rejection outcome
- **THEN** the tests verify deterministic result metadata, stable output ordering, and no source-state mutation on failure
