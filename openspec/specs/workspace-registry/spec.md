## Purpose

The `workspace-registry` capability defines loading, validation, and canonical graph conversion for the evolved `repo-index.yaml` workspace registry.

## Requirements

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

### Requirement: Registry supports non-git project workspace layout
The system SHALL support a local project workspace root that is not required to be a Git repository and that acts as the execution boundary for workspace-level generated Engineering KG state.

#### Scenario: Workspace root is resolved deterministically
- **WHEN** local code loads a registry that declares a project workspace root
- **THEN** the system resolves the workspace root deterministically without requiring the workspace root itself to be a Git repository

#### Scenario: Workspace root contains generated state locations
- **WHEN** local code loads a registry for the MVP workspace layout
- **THEN** the system can identify workspace-level generated state locations for OpenLore indexes and the local LadybugDB-compatible Engineering KG graph store

### Requirement: Registry identifies one OpenSpec store repository
The system SHALL validate that the Engineering KG registry identifies exactly one OpenSpec store repository for durable requirements, specifications, OpenSpec changes, wiki content, and versioned Engineering KG configuration.

#### Scenario: Configured store repository is valid
- **WHEN** `engineering_kg.store_repository` references an existing repository entry with the `requirements` role
- **THEN** the registry loader accepts that repository as the OpenSpec store repository

#### Scenario: Store repository role is invalid
- **WHEN** `engineering_kg.store_repository` references an existing repository entry that does not have the `requirements` role
- **THEN** the registry loader reports a validation error before producing canonical graph objects

### Requirement: Registry keeps implementation repositories independent
The system SHALL represent implementation repositories as independent Git repositories under the project workspace without making the workspace root or OpenSpec store repository own their source code.

#### Scenario: Code repositories resolve under workspace layout
- **WHEN** a repository entry with a code or library role declares a local path under the workspace layout
- **THEN** the registry loader resolves that repository as an independent repository path while preserving the one-service-one-repository topology validation

#### Scenario: Requirements repository does not own source code
- **WHEN** local code loads a registry containing the OpenSpec store repository and implementation repositories
- **THEN** the system treats implementation source repositories as separate repository entries rather than nested content owned by the OpenSpec store repository

### Requirement: Registry separates generated state from versioned repositories
The system SHALL reject generated-state configuration that places workspace-level OpenLore indexes or the local Engineering KG graph store inside the OpenSpec store repository or an implementation repository.

#### Scenario: Workspace graph storage is outside repositories
- **WHEN** the registry configures the local LadybugDB-compatible graph storage path
- **THEN** the system validates that the graph storage path is workspace-generated state outside configured repository roots

#### Scenario: Workspace OpenLore storage is outside repositories
- **WHEN** the registry configures a workspace-level OpenLore index path
- **THEN** the system validates that the OpenLore index path is workspace-generated state outside configured repository roots

### Requirement: Registry graph output includes layout references only
The system SHALL convert the non-Git workspace layout into canonical graph references without storing generated OpenLore index contents, generated graph data, or implementation code intelligence in the registry graph snapshot.

#### Scenario: Layout references are serialized deterministically
- **WHEN** local code converts a valid non-Git workspace registry to a canonical graph snapshot
- **THEN** the graph contains deterministic references for workspace root, OpenSpec store repository, configured repository paths, workspace OpenLore location, and local graph storage location

#### Scenario: Generated contents are excluded
- **WHEN** local code converts the workspace layout to graph objects
- **THEN** the graph snapshot excludes generated OpenLore code graph details, generated LadybugDB records, source code contents, and fetched external-system data
