## Purpose

The `ekg-mcp-query-wrappers` capability defines thin FactMCP tool wrappers that expose selected local Engineering KG query operations to agents while delegating graph behavior to reusable Python query APIs.

## Requirements

### Requirement: FactMCP wrappers expose query operations as tools
The system SHALL expose selected Engineering KG query operations through FactMCP tools that delegate to the reusable local Python query API.

#### Scenario: Query operation is registered as FactMCP tool
- **WHEN** the local FactMCP wrapper is started with supported Engineering KG query operations
- **THEN** each exposed query operation is registered as a FactMCP tool
- **THEN** the wrapper does not expose those query operations as MCP resources in the MVP

#### Scenario: Tool delegates to reusable query API
- **WHEN** an agent invokes an Engineering KG FactMCP query tool
- **THEN** the tool delegates graph reading, filtering, traversal, traceability handling, and serialization semantics to the reusable Python query API
- **THEN** the tool itself does not implement graph traversal, derivation, validation rules, source extraction, persistence internals, or service-specific business logic

### Requirement: FactMCP wrappers provide requirements query tools
The system SHALL provide FactMCP tools for querying canonical Engineering KG requirement facts and their provenance through the reusable query API.

#### Scenario: Agent lists canonical requirements
- **WHEN** an agent invokes the requirements query tool with a configured local graph source
- **THEN** the tool returns deterministic canonical requirement results delegated from the reusable query API
- **THEN** each result includes canonical graph identifiers, names, properties, evidence identifiers, and supported locator identity fields

#### Scenario: Agent filters requirements by OpenSpec provenance
- **WHEN** an agent invokes the requirements query tool with an OpenSpec change or evidence filter
- **THEN** the tool returns canonical requirements selected by existing graph relationships and provenance
- **THEN** the wrapper does not expose or reconstruct source-prefixed requirement entities

### Requirement: FactMCP wrappers provide service query tools
The system SHALL provide FactMCP tools for querying Engineering KG service and repository facts through the reusable query API.

#### Scenario: Agent lists services
- **WHEN** an agent invokes the services query tool with a configured local graph source
- **THEN** the tool returns deterministic service and repository results from the reusable query API
- **THEN** service boundaries remain explicit in the returned graph identifiers and relationships

#### Scenario: Service query does not mix service logic
- **WHEN** an agent asks for service-related facts through the FactMCP tool
- **THEN** the tool returns only facts and relationships represented by the graph query API
- **THEN** it does not combine unrelated service behavior across repositories

### Requirement: FactMCP wrappers provide OpenSpec change query tools
The system SHALL provide FactMCP tools for querying active and archived OpenSpec change facts through the reusable query API.

#### Scenario: Agent lists changes
- **WHEN** an agent invokes the OpenSpec changes query tool with a configured local graph source
- **THEN** the tool returns deterministic active and archived change results from the reusable query API
- **THEN** returned change facts include represented artifact links, touched specification links, traceability links, and evidence identifiers

#### Scenario: Agent queries a missing relationship
- **WHEN** an agent queries a change relationship that is absent from the graph
- **THEN** the tool returns the reusable query API's explicit missing or empty relationship result
- **THEN** it does not invent a relationship in the wrapper layer

### Requirement: FactMCP wrappers provide traceability query tools
The system SHALL provide FactMCP tools for querying canonical and derived Engineering KG traceability relationships through the reusable query API.

#### Scenario: Agent queries canonical traceability
- **WHEN** an agent invokes the traceability query tool for a known graph object identifier
- **THEN** the tool returns deterministic canonical traceability relationships with derivation status, evidence identifiers, and locator identity fields
- **THEN** source-specific OpenSpec context is returned only as provenance for applicable relationships

#### Scenario: Invalid graph blocks traceability response when validation is required
- **WHEN** the FactMCP wrapper is configured to require graph integrity validation and the graph is invalid
- **THEN** the traceability query tool returns a structured error or diagnostic result
- **THEN** it does not return partial traceability as if the graph were valid

### Requirement: FactMCP wrapper behavior remains local-first
The system SHALL keep FactMCP query wrappers local-first, deterministic, and credential-free.

#### Scenario: Tools run without external services
- **WHEN** an agent invokes Engineering KG FactMCP query tools in an environment without network access
- **THEN** the tools complete using only local project code, FactMCP runtime behavior, configured local graph input, and the reusable Python query API
- **THEN** the tools do not call cloud services, OpenLore MCP, Jira MCP, Bitbucket MCP, Confluence, external APIs, compilation, publishing, semantic extraction, or LLM services

#### Scenario: Tool output excludes source-owned payloads
- **WHEN** a FactMCP query tool serializes a result
- **THEN** the result excludes source code, call graphs, dependency graphs, symbol bodies, OpenLore analysis payloads, Jira payloads, Bitbucket payloads, Confluence content, credentials, tokens, and external API responses

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

### Requirement: Agent-facing query tools expose freshness through the local API
The existing FactMCP `list_requirements`, `list_services`, `list_changes`, and `get_traceability` tools SHALL return the local query API's additive per-support freshness and current-evidence eligibility fields. They SHALL optionally forward caller-supplied checked current-source revision observations to that API, with no wrapper-owned comparison, source resolution, or trust promotion. When no checked revision is supplied, the tools SHALL expose `unknown`, not an assumed fresh/stale result. Invalid checks SHALL return a structured payload-safe error with no partial success response. Tool schemas SHALL continue to exclude graph-store paths; existing invocations without the new optional input SHALL remain valid.

#### Scenario: Agent sees unknown by default
- **WHEN** an agent queries a fact through an existing tool without checked source revisions
- **THEN** the fact's represented evidence shows `unknown` freshness and ineligible current-evidence status without changing the existing fact fields

#### Scenario: Wrapper forwards checked revisions only
- **WHEN** a caller supplies valid checked authoritative revision observations with an existing tool request
- **THEN** the wrapper returns the local API's as-of freshness result for corresponding represented support
- **THEN** the wrapper does not fetch the source, compare revisions itself, or reinterpret stored trust

#### Scenario: Unsafe revision input does not leak
- **WHEN** a caller sends an invalid or conflicting checked-revision input
- **THEN** the wrapper returns a structured safe error and no partial results or source payloads

### Requirement: Agent-facing tools forward evidence-use and critical-conclusion results
The existing FactMCP query tools SHALL preserve and return local API evidence-use fields without recomputing authority, freshness, conflicts or evidence paths. A thin opt-in critical-conclusion tool SHALL delegate to the local bounded explanation operation for caller-proposed implementation ownership or change readiness, expose its `supported`/`unresolved` result and exact represented path, and return structured safe errors for invalid inputs or validation-required graph failures. Existing tool invocations, graph-store binding, optional checked-revision behavior, payload exclusions and no-network contract SHALL remain compatible. No tool SHALL create graph relationships from names, prompts or LLM guesses.

#### Scenario: Missing evidence through MCP stays unresolved
- **WHEN** an agent uses the critical-conclusion tool or existing traceability tool on a fixture without the requisite relationship/evidence
- **THEN** it receives an `unresolved`/`unknown` conclusion or existing empty/missing traceability with no invented edge or provenance IDs

#### Scenario: Tool remains thin and safe
- **WHEN** a caller supplies an unsupported conclusion kind or invalid checked-revision input
- **THEN** the tool returns the local API's structured payload-safe error with no partial success
- **THEN** it does not call an external service, inspect prompt content, or infer a replacement answer
