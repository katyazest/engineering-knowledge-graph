## ADDED Requirements

### Requirement: Canonical workspace registry is loaded from repo-index
The system SHALL load `repo-index.yaml` as the canonical workspace registry for Engineering KG MVP pipeline bootstrapping.

#### Scenario: Registry loads from local file
- **WHEN** local code loads a valid `repo-index.yaml`
- **THEN** the system returns a workspace registry object containing workspace identity, repositories, repository roles, local repository paths, Engineering KG configuration, OpenLore federation configuration, and pipeline orchestration inputs

#### Scenario: Registry loading remains local-first
- **WHEN** local code loads the workspace registry
- **THEN** the system does not require network access, API keys, cloud services, OpenLore queries, LadybugDB persistence, Jira, Bitbucket, Confluence, generated documentation, or external MCP servers

### Requirement: Registry preserves repository inventory compatibility
The system SHALL preserve the repository inventory semantics of the existing `repo-index.yaml` format.

#### Scenario: Existing repository discovery fields are accepted
- **WHEN** a registry entry contains repository id, path, description, ssh_url, default_branch, role, exploration settings, and git settings compatible with the existing multirepo exploration schema
- **THEN** the registry loader accepts those fields as repository inventory data

#### Scenario: Repository paths resolve relative to registry file
- **WHEN** a repository entry declares a relative path
- **THEN** the registry loader resolves the local repository location relative to the `repo-index.yaml` file location

### Requirement: Registry stores stable topology only
The system SHALL reject or ignore registry content that attempts to make `repo-index.yaml` the source of truth for derived or external-system facts.

#### Scenario: Registry does not duplicate derived facts
- **WHEN** local code validates the workspace registry
- **THEN** the registry is not treated as a source of truth for code structure, architecture relationships, implementation details, Jira data, Bitbucket data, OpenSpec requirements, or generated documentation

#### Scenario: Registry stores only external configuration references
- **WHEN** registry content configures OpenLore, Jira, Bitbucket, OpenSpec, LadybugDB, or pipeline stages
- **THEN** the registry stores deterministic local configuration inputs and references rather than fetched external records, credentials, API responses, or generated outputs

### Requirement: Registry validates MVP service topology
The system SHALL validate the MVP topology rule that one service maps to one repository.

#### Scenario: Service repository mapping is valid
- **WHEN** the registry contains repositories with service identity
- **THEN** each service identity maps to exactly one repository

#### Scenario: Duplicate service mapping is rejected
- **WHEN** two repository entries declare the same MVP service identity
- **THEN** the registry loader reports a validation error before producing canonical graph objects

### Requirement: Registry produces canonical graph snapshot
The system SHALL convert stable workspace topology into deterministic canonical graph objects.

#### Scenario: Workspace graph objects are produced
- **WHEN** local code converts a valid workspace registry to a canonical graph snapshot
- **THEN** the graph contains deterministic nodes for workspace, services, and repositories represented by the registry
- **THEN** the graph contains deterministic edges representing workspace-to-repository and service-to-repository ownership

#### Scenario: Registry graph output is deterministic
- **WHEN** local code converts the same workspace registry multiple times
- **THEN** each graph snapshot has the same stable node ids, edge ids, serialized structure, and counts

### Requirement: Registry exposes OpenLore federation inputs
The system SHALL expose deterministic OpenLore federation inputs from the workspace registry without creating or rebuilding OpenLore indexes.

#### Scenario: Federation inputs are available
- **WHEN** local code reads OpenLore configuration from a valid registry
- **THEN** the system can identify repositories included in federation and their configured local index references

#### Scenario: OpenLore ownership boundary is preserved
- **WHEN** local code processes OpenLore federation configuration from the registry
- **THEN** the system does not store OpenLore code graph details in the registry or canonical Engineering KG graph
