## Purpose

The `mcp-startup-resolution` capability defines how Engineering KG resolves the workspace registry and graph store before starting MCP query tools.

## Requirements

### Requirement: MCP startup resolves graph store from explicit overrides
The system SHALL resolve the Engineering KG graph store for MCP startup using explicit CLI overrides before using OpenSpec project context.

#### Scenario: Graph store override is used directly
- **WHEN** the user starts `engineering-kg mcp` with `--graph-store`
- **THEN** the system uses the provided LadybugDB-compatible graph store path for the MCP server
- **THEN** the system does not resolve an OpenSpec store, load `repo-index.yaml`, or infer workspace layout

#### Scenario: Registry override resolves graph store
- **WHEN** the user starts `engineering-kg mcp` with `--registry`
- **THEN** the system loads the provided `repo-index.yaml` through the workspace registry loader
- **THEN** the system uses `WorkspaceRegistry.layout.resolved_graph_store_path` as the MCP server graph store

#### Scenario: OpenSpec store override resolves registry
- **WHEN** the user starts `engineering-kg mcp` with `--openspec-store`
- **THEN** the system resolves the matching registered OpenSpec store id to a local store path
- **THEN** the system loads `<store path>/repo-index.yaml`
- **THEN** the system uses the loaded workspace registry to resolve the MCP server graph store

### Requirement: MCP startup resolves workspace from OpenSpec project context
The system SHALL resolve the Engineering workspace through the OpenSpec store associated with the current project when no explicit startup override is provided.

#### Scenario: Requirements repository resolves through OpenSpec project context
- **WHEN** the user starts `engineering-kg mcp` from a requirements repository associated with an OpenSpec store
- **THEN** the system resolves the project-associated OpenSpec store through OpenSpec project context
- **THEN** the system loads `repo-index.yaml` from the selected OpenSpec store path
- **THEN** the system starts MCP with the graph store path from the loaded workspace registry

#### Scenario: Code repository resolves through OpenSpec project context
- **WHEN** the user starts `engineering-kg mcp` from a configured code repository whose OpenSpec project configuration selects a store
- **THEN** the system resolves the selected OpenSpec store through OpenSpec project context
- **THEN** the system loads `repo-index.yaml` from the selected OpenSpec store path
- **THEN** the system starts MCP with the same workspace graph store used from the requirements repository

#### Scenario: Current working directory does not infer workspace layout
- **WHEN** MCP startup resolves the OpenSpec store from current project context
- **THEN** the system uses the current working directory only as input to OpenSpec project resolution
- **THEN** the system does not search sibling directories, nearest `.engineering-kg` directories, nearest requirements repositories, or arbitrary registered stores to infer workspace layout

### Requirement: MCP startup applies deterministic override precedence
The system SHALL apply a deterministic startup resolution precedence for graph store selection.

#### Scenario: Override precedence is applied
- **WHEN** multiple startup inputs are provided
- **THEN** the system applies precedence in this order: `--graph-store`, `--registry`, `--openspec-store`, OpenSpec project store resolution from current working directory
- **THEN** lower-precedence inputs do not change the selected graph store

#### Scenario: Ambiguous generic store flag is not used
- **WHEN** the user starts the MCP command
- **THEN** the CLI exposes `--openspec-store` for OpenSpec store ids
- **THEN** the CLI exposes `--graph-store` for LadybugDB-compatible graph store paths
- **THEN** the CLI does not require a generic `--store` flag for MCP startup

### Requirement: Automatic MCP startup validates workspace membership
The system SHALL validate that the current Git repository belongs to the loaded workspace registry when startup uses automatic OpenSpec project resolution.

#### Scenario: Current repository is in workspace registry
- **WHEN** automatic MCP startup resolves an OpenSpec store and loads `repo-index.yaml`
- **THEN** the system resolves the current Git repository root
- **THEN** the system accepts startup only when the current Git repository root matches one of `WorkspaceRegistry.repositories[*].resolved_path`

#### Scenario: Current repository is not in workspace registry
- **WHEN** automatic MCP startup resolves an OpenSpec store and loads a registry that does not contain the current Git repository root
- **THEN** the system fails before exposing MCP tools
- **THEN** the error explains that the current repository is not part of the selected Engineering workspace

#### Scenario: Explicit low-level override bypasses membership validation
- **WHEN** the user starts `engineering-kg mcp` with `--graph-store`
- **THEN** the system does not require current Git repository membership in a workspace registry

### Requirement: MCP startup reports actionable resolution failures
The system SHALL report actionable local errors when MCP startup cannot resolve the OpenSpec project context, selected store, workspace registry, or graph store.

#### Scenario: OpenSpec project context cannot be resolved
- **WHEN** the user starts `engineering-kg mcp` without explicit overrides and OpenSpec cannot resolve a project-associated store from the current working directory
- **THEN** the system fails before exposing MCP tools
- **THEN** the error tells the user to configure `openspec/config.yaml` with `store: <id>`, register the store, use `--openspec-store`, or use `--registry`

#### Scenario: Selected OpenSpec store is not registered
- **WHEN** the user starts `engineering-kg mcp` with an OpenSpec store id that is not registered locally
- **THEN** the system fails before exposing MCP tools
- **THEN** the error identifies the missing OpenSpec store id without printing credentials or sensitive data

#### Scenario: Registry is missing from selected store
- **WHEN** the selected OpenSpec store path does not contain `repo-index.yaml`
- **THEN** the system fails before exposing MCP tools
- **THEN** the error identifies the missing workspace registry path

### Requirement: MCP startup remains host-independent and enterprise-safe
The system SHALL keep MCP startup behavior independent of the MCP host while supporting constrained Gigacode configuration.

#### Scenario: Startup does not depend on host-specific behavior
- **WHEN** the MCP server starts from Gigacode, Codex, Claude Desktop, or another MCP host
- **THEN** the system uses the same Engineering KG startup resolution behavior
- **THEN** the system does not rely on Codex-specific behavior, `AGENTS.md`, interactive shell environment, aliases, or implicit `PATH`

#### Scenario: Startup uses simple host configuration
- **WHEN** MCP host configuration is documented for Gigacode
- **THEN** the configuration passes simple command and argument values
- **THEN** the configuration does not use shell substitutions, complex one-liners, aliases, or interactive shell setup

#### Scenario: Startup avoids forbidden access paths
- **WHEN** the MCP server starts
- **THEN** startup completes without web fetchers, `curl`, `wget`, browser fetchers, ad hoc HTTP, secrets, external network access, OpenLore MCP, Jira MCP, Bitbucket MCP, Confluence, semantic extraction, graph rebuilding, or LLM services
