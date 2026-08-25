## ADDED Requirements

### Requirement: FactMCP wrappers bind graph store at startup
The system SHALL bind FactMCP query wrappers to one Engineering KG graph store before exposing query tools.

#### Scenario: Server starts with resolved graph store
- **WHEN** MCP startup creates the FactMCP server with a resolved local graph store path
- **THEN** every registered Engineering KG query tool uses that server-level graph store
- **THEN** tool invocation does not require the agent to provide a graph store path

#### Scenario: Tool schema excludes graph store parameter
- **WHEN** FactMCP wrappers register query tools
- **THEN** `list_requirements` exposes only query filters such as capability, service, OpenSpec change, or evidence reference
- **THEN** `list_services` exposes no graph store parameter
- **THEN** `list_changes` exposes no graph store parameter
- **THEN** `get_traceability` exposes graph object identity but no graph store parameter

#### Scenario: Startup-level debug override does not appear in tool schema
- **WHEN** the MCP server is started with `--graph-store`
- **THEN** the resolved debug graph store is bound before tools are exposed
- **THEN** the MCP tool schemas still exclude graph store path parameters
