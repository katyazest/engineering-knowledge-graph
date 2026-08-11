## ADDED Requirements

### Requirement: OpenSpec store source prefers registered OpenSpec store
The system SHALL use OpenSpec's local store registry/config as the primary source for selecting the OpenSpec store when one or more stores are registered.

#### Scenario: Single registered OpenSpec store matching requirements repository is selected
- **WHEN** local code validates the OpenSpec store source and OpenSpec store discovery returns exactly one registered store
- **THEN** the system cross-checks that registered store against the requirements repository identified by `engineering_kg.store_repository`
- **THEN** the system selects that registered store as the OpenSpec store source only when the paths match
- **THEN** the system reports the selection source, store id, resolved store path, and validation status as deterministic validation metadata

#### Scenario: Multiple registered OpenSpec stores select requirements repository match
- **WHEN** local code validates the OpenSpec store source and OpenSpec store discovery returns more than one registered store without an explicitly selected store id
- **THEN** the system cross-checks the registered store paths against the requirements repository identified by `engineering_kg.store_repository`
- **THEN** the system selects the registered store whose path matches the requirements repository
- **THEN** the system reports the selection source, store id, resolved store path, matched repository id, and validation status as deterministic validation metadata

#### Scenario: Registered stores without requirements repository match require explicit selection
- **WHEN** local code validates the OpenSpec store source and OpenSpec store discovery returns one or more registered stores that do not match the requirements repository identified by `engineering_kg.store_repository`
- **THEN** the system reports a validation error before returning a successful OpenSpec store source validation result

#### Scenario: Explicit registered store id is selected
- **WHEN** local code validates the OpenSpec store source with an explicit store id that exists in OpenSpec store discovery
- **THEN** the system cross-checks the matching registered store against the requirements repository identified by `engineering_kg.store_repository`
- **THEN** the system selects the matching registered store as the OpenSpec store source only when the paths match
- **THEN** the system reports the selected store id and selection source as deterministic validation metadata

### Requirement: OpenSpec store source falls back to requirements repository
The system SHALL use the requirements repository from the already-loaded workspace registry as the fallback OpenSpec store only when OpenSpec store discovery returns no registered stores.

#### Scenario: No registered stores uses requirements repository fallback
- **WHEN** local code validates the OpenSpec store source and OpenSpec store discovery returns no registered stores
- **THEN** the system resolves `engineering_kg.store_repository` to an existing repository entry with role `requirements`
- **THEN** the system selects that repository entry as the fallback OpenSpec store source
- **THEN** the system reports the selection source, repository id, role, resolved repository path, and validation status as deterministic validation metadata

#### Scenario: Fallback non-requirements repository is rejected
- **WHEN** local code falls back to the workspace registry and `engineering_kg.store_repository` references a repository entry that does not have role `requirements`
- **THEN** the system reports a validation error before returning a successful OpenSpec store source validation result

### Requirement: Registered store is cross-checked with requirements repository
The system SHALL cross-check a selected registered OpenSpec store against the workspace registry requirements repository before treating it as the Engineering KG OpenSpec source.

#### Scenario: Registered store matches requirements repository
- **WHEN** local code validates a selected registered OpenSpec store whose resolved path matches the repository entry referenced by `engineering_kg.store_repository`
- **THEN** the system accepts the registered store as the Engineering KG OpenSpec store source

#### Scenario: Registered store does not match requirements repository
- **WHEN** local code validates a selected registered OpenSpec store whose resolved path does not match the repository entry referenced by `engineering_kg.store_repository`
- **THEN** the system requires explicit store selection or configuration before OpenSpec extraction runs

### Requirement: OpenSpec root is validated inside store repository
The system SHALL validate that the selected OpenSpec store contains a usable OpenSpec root for durable specifications and intended changes.

#### Scenario: Store contains usable OpenSpec root
- **WHEN** local code validates an OpenSpec store repository whose resolved path contains `openspec/specs` and `openspec/changes` directories
- **THEN** the system accepts the resolved `openspec` directory as the OpenSpec root
- **THEN** the system reports the resolved OpenSpec root, specs path, and changes path as deterministic validation metadata

#### Scenario: Store repository path is missing
- **WHEN** local code validates an OpenSpec store repository whose resolved repository path does not exist as a directory
- **THEN** the system reports a validation error before OpenSpec extraction runs

#### Scenario: OpenSpec root is missing
- **WHEN** local code validates an OpenSpec store repository whose resolved repository path does not contain an `openspec` directory
- **THEN** the system reports a validation error before OpenSpec extraction runs

#### Scenario: OpenSpec specs or changes directory is missing
- **WHEN** local code validates an OpenSpec store repository whose `openspec` directory does not contain both `specs` and `changes` directories
- **THEN** the system reports a validation error before OpenSpec extraction runs

### Requirement: Validation uses registry path instead of nearest OpenSpec root
The system SHALL resolve OpenSpec extraction source paths from the selected registered store or fallback requirements repository rather than from process current working directory or nearest local OpenSpec root discovery.

#### Scenario: Execution from workspace still uses selected store
- **WHEN** local code validates the OpenSpec store source while the process current working directory is outside the configured requirements repository
- **THEN** the system resolves the OpenSpec root from the selected registered store or fallback requirements repository path
- **THEN** the system does not use the process current working directory as the source of OpenSpec specifications or changes

#### Scenario: Local authoring root does not override configured store
- **WHEN** a local project workspace also contains an `openspec` directory outside the selected registered store or fallback requirements repository
- **THEN** the system uses the OpenSpec root under the selected store for extraction source metadata

### Requirement: Validation preserves source ownership boundaries
The system SHALL validate the OpenSpec store source without reading or returning implementation code, OpenLore code intelligence, generated LadybugDB graph data, external-system payloads, credentials, tokens, or generated documentation.

#### Scenario: Validation metadata excludes source and generated content
- **WHEN** local code serializes the OpenSpec store source validation result
- **THEN** the serialized result contains only deterministic source metadata such as status, selection source, store id when available, repository id, repository role, resolved repository path, OpenSpec root path, specs path, and changes path
- **THEN** the serialized result excludes specification bodies, change bodies, source code, call graph, dependency graph, symbol bodies, generated graph records, credentials, tokens, and external API responses

#### Scenario: Validation remains local-first
- **WHEN** local code validates the OpenSpec store source
- **THEN** the system completes without network access, API keys, cloud services, OpenLore MCP calls, Jira MCP calls, Bitbucket MCP calls, Confluence calls, compilation, publishing, or generated documentation

### Requirement: Validation output is deterministic
The system SHALL return deterministic OpenSpec store source validation output for the same registry input and filesystem shape.

#### Scenario: Same store source produces same validation output
- **WHEN** local code validates the same workspace registry, unchanged OpenSpec store discovery data, and unchanged OpenSpec store source multiple times
- **THEN** each validation result has the same status, repository id, resolved paths, serialized structure, and validation metadata values
