## MODIFIED Requirements

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

### Requirement: FactMCP wrappers provide traceability query tools
The system SHALL provide FactMCP tools for querying canonical and derived Engineering KG traceability relationships through the reusable query API.

#### Scenario: Agent queries canonical traceability
- **WHEN** an agent invokes the traceability query tool for a known graph object identifier
- **THEN** the tool returns deterministic canonical traceability relationships with derivation status, evidence identifiers, and locator identity fields
- **THEN** source-specific OpenSpec context is returned only as provenance for applicable relationships
