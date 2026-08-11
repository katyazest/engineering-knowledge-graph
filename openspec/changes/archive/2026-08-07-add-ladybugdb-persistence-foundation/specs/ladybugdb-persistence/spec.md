## ADDED Requirements

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
