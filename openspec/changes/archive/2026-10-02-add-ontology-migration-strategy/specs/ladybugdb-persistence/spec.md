## MODIFIED Requirements

### Requirement: Persisted ontology is migrated deterministically
The persistence boundary SHALL invoke the storage-engine-independent versioned snapshot migration boundary before normal graph readback or write behavior exposes or merges persisted state. It SHALL recognize only the registered source descriptors and migration chains defined by `ontology-snapshot-migration`, including the supported OpenSpec-prefixed-to-canonical transition when its natural keys, relationship mappings, evidence, and provenance are complete. It SHALL deserialize and expose only the validated current canonical snapshot; an unsupported source version or a source that cannot be migrated deterministically SHALL fail before readback or write replacement.

#### Scenario: Legacy OpenSpec facts are migrated
- **WHEN** a local graph store contains a versionless document matching the supported OpenSpec-prefixed descriptor with `openspec-spec`, `openspec-requirement`, or `openspec-scenario` records and supported OpenSpec evidence
- **THEN** persistence invokes the registered migration to rewrite them to canonical specification, requirement, and scenario records using the defined canonical natural keys
- **THEN** it rewrites affected relationship endpoints and preserves compatible evidence and asserted-versus-derived metadata before exposing readback

#### Scenario: Migration is idempotent
- **WHEN** persistence migrates a supported graph store and the same store is read, migrated, or written again without incompatible changes
- **THEN** the resulting current-version canonical snapshot has the same version, IDs, records, evidence, and deterministic serialization
- **THEN** no duplicate records, repeated transforms, or additional backup replacements are created

#### Scenario: Migration conflict fails safely
- **WHEN** a registered legacy migration cannot coalesce records because they conflict on a canonical kind, natural-key field, immutable value, or required mapping
- **THEN** persistence reports an explicit payload-safe integrity or compatibility failure before exposing a migrated snapshot
- **THEN** the original persisted graph remains unchanged

### Requirement: Ontology migration replaces persisted data atomically
The persistence adapter SHALL create a recoverable byte-equivalent backup of the source logical snapshot and atomically replace the persisted graph only after the storage-engine-independent migration produces a current-version target that passes persistence decoding and canonical graph validation. Failure to recognize a source version, transform it, validate the target, create the backup, or replace the graph SHALL report an explicit persistence or migration failure and SHALL leave the source graph available unchanged. A current-version no-op SHALL not create or overwrite a migration backup.

#### Scenario: Valid migration is committed
- **WHEN** a supported legacy graph migrates successfully
- **THEN** persistence writes a recoverable backup before atomically replacing the graph with the validated current-version snapshot
- **THEN** later readback returns only the current canonical vocabulary and explicit schema version

#### Scenario: Failed replacement preserves previous graph
- **WHEN** an error occurs while backing up, validating, or writing a migrated graph
- **THEN** persistence reports the write or migration failure
- **THEN** the prior graph file or its recoverable backup remains available for rollback and no partial target document is exposed

### Requirement: Persistence preserves and safely migrates first-class provenance
The persistence boundary SHALL persist and read first-class provenance with deterministic serialization, association, ordering, and merge semantics. It SHALL retain no authoritative source content. A registered migration SHALL preserve legacy evidence only when all provenance fields required by the target contract are retained authoritatively and the migration can bind them deterministically; otherwise it SHALL emit a deterministic compatibility or integrity failure, preserve the prior store or backup, and SHALL NOT fabricate timestamps, hashes, extractor metadata, rules, input provenance, or source-artifact identity.

#### Scenario: Complete legacy provenance migrates safely
- **WHEN** a supported persisted legacy snapshot retains every required first-class provenance field and source-artifact identity component
- **THEN** persistence migrates it through the registered version path, preserves the required canonical fact IDs and provenance references, and returns deterministic payload-free current-version readback

#### Scenario: Incomplete legacy provenance fails safely
- **WHEN** a supported persisted legacy snapshot lacks its observation time, content hash, extractor version, source-artifact identity, or required derivation information
- **THEN** persistence reports a deterministic compatibility or integrity failure and does not rewrite the graph as if provenance were complete

### Requirement: Persistence round-trips PR implementation evidence and scoped observations deterministically
The persistence boundary SHALL serialize, merge, and read PR implementation-evidence records, their declared and observed relation references, and PR-scoped cross-graph observation references in deterministic order. It SHALL coalesce equivalent records, reject immutable conflicts and dangling references before replacing persisted state, and preserve the existing claim identity and provenance chains. A valid current-version snapshot with no PR implementation-evidence records SHALL read back with empty corresponding collections. A versioned migration may carry or convert PR records only when a registered source contract retains the required base revision, head revision, explicit association, and provenance data; it SHALL reject rather than invent, backfill, or infer missing PR fields.

#### Scenario: PR evidence round-trip is stable
- **WHEN** a valid current-version snapshot with one declared PR association and one observed scoped candidate is persisted and read repeatedly
- **THEN** each readback has the same PR identity, repository/base/head revisions, relation origins, source/provenance references, candidate identity, and deterministic ordering
- **THEN** no provider payload, URL, source code, or implementation conclusion is added during persistence

#### Scenario: Incomplete historical PR data is not migrated
- **WHEN** a registered source snapshot contains a PR candidate without required base/head revisions, explicit association, or provenance data
- **THEN** version migration fails before readback or replacement with a deterministic compatibility diagnostic
- **THEN** it does not fabricate a PR evidence record or inferred `IMPLEMENTS` relationship

### Requirement: Persistence round-trips verification ontology records at the current catalog revision
The persistence boundary SHALL serialize, merge, validate, and read back verification node kinds, their canonical relationships, and optional cross-graph verification-evidence support references in deterministic order at the relationship catalog revision expected by the current ontology schema version. It SHALL coalesce compatible records, preserve stable node and claim identities, and reject immutable conflicts or invalid verification references before replacing persisted state. A valid current-version snapshot without verification records SHALL read back with no verification-specific records. A versioned migration may carry verification data only when an explicitly registered source mapping preserves its natural identity, relation direction, support references, and provenance; it SHALL reject rather than invent, backfill, or infer verification records or support.

#### Scenario: Verification records round-trip without implementation inference
- **WHEN** a valid current-version snapshot contains a verification chain and a verification-evidence-bound `VERIFIED_BY` support record
- **THEN** repeated persistence and readback preserve canonical IDs, relation directions, support reference, provenance references, and deterministic ordering
- **THEN** persistence adds no test-framework/CI payload, test output, URL, or `IMPLEMENTS` relationship

#### Scenario: Incomplete historical verification data is not migrated
- **WHEN** a registered source snapshot lacks the retained fields needed to establish a verification node identity, relationship direction, support reference, or provenance
- **THEN** persistence returns a deterministic migration compatibility failure before exposing graph data or replacing the source document
- **THEN** it does not fabricate verification records or backfill support references
