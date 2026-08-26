## ADDED Requirements

### Requirement: Persisted ontology is migrated deterministically
The system SHALL migrate persisted records using retired OpenSpec-prefixed domain node and relationship kinds to the revised canonical ontology before normal graph readback or write behavior exposes the snapshot.

#### Scenario: Legacy OpenSpec facts are migrated
- **WHEN** a local graph store contains `openspec-spec`, `openspec-requirement`, or `openspec-scenario` records with supported OpenSpec evidence
- **THEN** persistence rewrites them to canonical specification, requirement, and scenario records using the defined canonical natural keys
- **THEN** persistence rewrites affected relationship endpoints and preserves compatible evidence and asserted-versus-derived metadata

#### Scenario: Migration is idempotent
- **WHEN** persistence migrates a graph store and the same store is read or migrated again without incompatible changes
- **THEN** the resulting canonical snapshot has the same IDs, records, evidence, and deterministic serialization
- **THEN** no duplicate records are created

#### Scenario: Migration conflict fails safely
- **WHEN** legacy records cannot be coalesced because they conflict on a canonical kind or natural-key field
- **THEN** persistence reports an explicit integrity failure before exposing a migrated snapshot
- **THEN** the original persisted graph remains unchanged

### Requirement: Ontology migration replaces persisted data atomically
The system SHALL create a recoverable backup and atomically replace the persisted graph only after the migrated snapshot passes canonical graph validation.

#### Scenario: Valid migration is committed
- **WHEN** a legacy graph migrates successfully
- **THEN** persistence writes a backup before replacing the graph with the validated canonical snapshot
- **THEN** later readback returns only the revised canonical vocabulary

#### Scenario: Failed replacement preserves previous graph
- **WHEN** an error occurs while writing a migrated graph
- **THEN** persistence reports the write failure
- **THEN** the prior graph file or its recoverable backup remains available for rollback
