## ADDED Requirements

### Requirement: Workspace OpenLore source is validated from registry configuration
The system SHALL validate the workspace-level OpenLore source using the already-loaded workspace registry configuration.

#### Scenario: Workspace OpenLore source resolves from layout
- **WHEN** local code validates the workspace OpenLore source for a registry with `layout.openlore_path`
- **THEN** the system resolves the workspace OpenLore source path deterministically from the registry workspace root
- **THEN** the system reports the resolved workspace OpenLore source path as validation metadata

#### Scenario: Default workspace OpenLore source resolves deterministically
- **WHEN** local code validates the workspace OpenLore source for a registry without an explicit `layout.openlore_path`
- **THEN** the system resolves the workspace OpenLore source path to the default `.openlore` path under the resolved workspace root

### Requirement: Workspace OpenLore source remains local generated state
The system SHALL validate that the workspace OpenLore source is local generated state outside the OpenSpec store repository and implementation repository roots.

#### Scenario: Workspace OpenLore source inside repository is rejected
- **WHEN** local code validates a registry whose resolved workspace OpenLore source path is inside a configured repository root
- **THEN** the system reports a validation error before returning a successful OpenLore source validation result

#### Scenario: Workspace OpenLore source outside repositories is accepted
- **WHEN** local code validates a registry whose resolved workspace OpenLore source path is under the workspace root and outside configured repository roots
- **THEN** the system accepts the workspace OpenLore source boundary

### Requirement: Federation repository references are validated
The system SHALL validate deterministic OpenLore federation references for repositories included in federation.

#### Scenario: Included repository has local index reference
- **WHEN** local code validates a repository with `openlore.include_in_federation` set to true
- **THEN** the system requires a non-empty `openlore.index_location` value for that repository
- **THEN** the system includes the repository id and index reference in validation metadata

#### Scenario: Excluded repository does not require index reference
- **WHEN** local code validates a repository with `openlore.include_in_federation` set to false
- **THEN** the system does not require that repository to define an OpenLore index reference

#### Scenario: Federation disabled skips repository index requirements
- **WHEN** local code validates a registry with `openlore.federation_enabled` set to false
- **THEN** the system completes validation without requiring per-repository OpenLore index references
- **THEN** the system reports zero federation repositories in validation metadata

### Requirement: Validation does not duplicate OpenLore code intelligence
The system SHALL validate OpenLore source configuration without reading, storing, or returning OpenLore code graph contents.

#### Scenario: Validation metadata excludes code graph details
- **WHEN** local code serializes the OpenLore source validation result
- **THEN** the serialized result contains only deterministic source metadata such as source path, federation setting, freshness policy, repository ids, and index references
- **THEN** the serialized result does not contain source code, call graph, dependency graph, class body, function body, symbol body, architecture analysis, impact analysis, or OpenLore query responses

#### Scenario: Validation remains local-first
- **WHEN** local code validates the workspace OpenLore source
- **THEN** the system completes without network access, API keys, cloud services, OpenLore MCP calls, Jira MCP calls, Bitbucket MCP calls, Confluence calls, compilation, publishing, or generated documentation

### Requirement: Validation output is deterministic
The system SHALL return deterministic OpenLore source validation output for the same registry input.

#### Scenario: Same registry produces same validation output
- **WHEN** local code validates the same workspace registry multiple times
- **THEN** each validation result has the same status, resolved source path, federation setting, freshness policy, repository references, serialized structure, and counts

