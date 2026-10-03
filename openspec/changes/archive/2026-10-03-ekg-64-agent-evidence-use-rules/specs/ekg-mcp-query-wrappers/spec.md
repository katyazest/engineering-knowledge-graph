## ADDED Requirements

### Requirement: Agent-facing tools forward evidence-use and critical-conclusion results
The existing FactMCP query tools SHALL preserve and return local API evidence-use fields without recomputing authority, freshness, conflicts or evidence paths. A thin opt-in critical-conclusion tool SHALL delegate to the local bounded explanation operation for caller-proposed implementation ownership or change readiness, expose its `supported`/`unresolved` result and exact represented path, and return structured safe errors for invalid inputs or validation-required graph failures. Existing tool invocations, graph-store binding, optional checked-revision behavior, payload exclusions and no-network contract SHALL remain compatible. No tool SHALL create graph relationships from names, prompts or LLM guesses.

#### Scenario: Missing evidence through MCP stays unresolved
- **WHEN** an agent uses the critical-conclusion tool or existing traceability tool on a fixture without the requisite relationship/evidence
- **THEN** it receives an `unresolved`/`unknown` conclusion or existing empty/missing traceability with no invented edge or provenance IDs

#### Scenario: Tool remains thin and safe
- **WHEN** a caller supplies an unsupported conclusion kind or invalid checked-revision input
- **THEN** the tool returns the local API's structured payload-safe error with no partial success
- **THEN** it does not call an external service, inspect prompt content, or infer a replacement answer
