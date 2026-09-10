## Purpose

The `ladybugdb-persistence` capability defines the local adapter-compatible persistence boundary for canonical Engineering KG graph snapshots.
## Requirements
### Requirement: Local adapter-compatible LadybugDB store can be initialized
The system SHALL provide a reusable local adapter-compatible LadybugDB persistence boundary that initializes an Engineering KG store at a configured local path without requiring network access, API keys, cloud services, OpenLore queries, Jira, Bitbucket, Confluence, external MCP servers, compilation, publishing, Docker, or generated documentation.

#### Scenario: Empty store initializes
- **WHEN** local code initializes the adapter-compatible LadybugDB persistence boundary with an empty temporary output path
- **THEN** the system creates or opens a local Engineering KG store successfully
- **THEN** reading the store as a canonical graph snapshot returns zero nodes, zero edges, and zero evidence records

#### Scenario: Initialization remains local-first
- **WHEN** local code initializes the store in an environment without network access
- **THEN** initialization completes using only local project code, local dependencies, and the configured local storage path

### Requirement: Canonical graph snapshots can be persisted
The system SHALL persist canonical `GraphSnapshot` content through the LadybugDB persistence boundary, including nodes, edges, evidence records, and supported locator/reference values, using stable canonical object IDs as storage identities.

#### Scenario: Registry graph snapshot is persisted
- **WHEN** local code persists a canonical graph snapshot produced from a valid workspace registry
- **THEN** the store contains the snapshot's canonical nodes and edges keyed by their stable IDs
- **THEN** the persisted graph can be read back as canonical ontology objects

#### Scenario: Evidence records are persisted
- **WHEN** local code persists a graph snapshot containing evidence records
- **THEN** the store contains those evidence records keyed by their stable IDs
- **THEN** readback preserves each evidence source, locator, properties, and serialized structure

### Requirement: Persistence readback is deterministic
The system SHALL read persisted graph data back into the existing canonical in-memory ontology contract with deterministic structure and serialization.

#### Scenario: Same graph readback is stable
- **WHEN** local code reads the same persisted store multiple times without intervening writes
- **THEN** each returned graph snapshot has the same node count, edge count, evidence count, object IDs, and serialized values

#### Scenario: Repeated writes do not duplicate graph objects
- **WHEN** local code persists the same canonical graph snapshot to the same store multiple times
- **THEN** readback returns one canonical object per stable node, edge, and evidence ID
- **THEN** readback serialization is the same as after the first write

### Requirement: Persistence preserves OpenLore ownership boundary
The system SHALL store only Engineering KG canonical facts and CodeLocator identity fields, and MUST NOT duplicate OpenLore-owned code intelligence or fetched external-system payloads.

#### Scenario: CodeLocator stores only identity fields
- **WHEN** local code persists and reads back a graph snapshot containing a `CodeLocator`
- **THEN** the serialized readback contains repository, revision, file, and symbol
- **THEN** the serialized readback does not contain source code, call graph, dependency graph, class body, function body, OpenLore analysis details, credentials, tokens, or external API response payloads

#### Scenario: Confluence reference stores only page identity
- **WHEN** local code persists and reads back a graph snapshot containing a `ConfluencePageRef`
- **THEN** the serialized readback contains page_id
- **THEN** the serialized readback does not contain page content, page URL, comments, attachments, credentials, tokens, or Confluence API response data

### Requirement: Persistence failures are reported before derived stages run
The system SHALL report local persistence initialization, write, and readback failures as explicit failures before later derivation, validation, projection, wiki, or MCP wrapper behavior is executed.

#### Scenario: Invalid storage path fails explicitly
- **WHEN** local code attempts to initialize persistence with an invalid or unwritable local storage path
- **THEN** the system reports a persistence failure
- **THEN** the system does not report the persistence stage as successfully executed

#### Scenario: Readback mismatch fails explicitly
- **WHEN** local code writes a canonical graph snapshot and readback cannot reconstruct the stored graph as canonical ontology objects
- **THEN** the system reports a persistence integrity failure
- **THEN** the system does not proceed as if the stored graph is valid

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

### Requirement: Persistence preserves and safely migrates first-class provenance
The system SHALL persist and read first-class provenance with deterministic serialization, association, ordering, and merge semantics. It SHALL retain no authoritative source content. For legacy persisted evidence, it SHALL migrate only when all required provenance fields can be recovered from retained authoritative metadata; otherwise it SHALL emit a deterministic compatibility diagnostic or integrity failure, preserve the prior store/backup, and SHALL NOT fabricate timestamps, hashes, extractor metadata, rules, or input provenance.

#### Scenario: Complete legacy provenance migrates safely
- **WHEN** persisted legacy evidence retains every required first-class provenance field
- **THEN** persistence migrates it atomically, preserves canonical fact IDs, and returns deterministic payload-free readback

#### Scenario: Incomplete legacy provenance fails safely
- **WHEN** persisted legacy evidence lacks its observation time, content hash, extractor version, or required derivation information
- **THEN** persistence reports deterministic compatibility/integrity failure and does not rewrite the graph as if provenance were complete

### Requirement: Persistence round-trips PR implementation evidence and scoped observations deterministically
The persistence boundary SHALL serialize, merge, and read PR implementation-evidence records, their declared/observed relation references, and PR-scoped cross-graph observation references in deterministic order. It SHALL coalesce equivalent records, reject immutable conflicts and dangling references before replacing persisted state, and preserve the existing claim identity and provenance chains. A new-format valid snapshot with no PR implementation-evidence records SHALL read back with empty corresponding collections. Persistence SHALL reject a prior catalog revision or PR candidate that lacks the required base/head revisions or explicit association; it SHALL NOT invent, backfill, or migrate those fields.

#### Scenario: PR evidence round-trip is stable
- **WHEN** a valid snapshot with one declared PR association and one observed scoped candidate is persisted and read repeatedly
- **THEN** each readback has the same PR identity, repository/base/head revisions, relation origins, source/provenance references, candidate identity, and deterministic ordering
- **THEN** no provider payload, URL, source code, or implementation conclusion is added during persistence

