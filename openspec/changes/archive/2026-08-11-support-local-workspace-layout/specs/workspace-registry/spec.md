## ADDED Requirements

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
