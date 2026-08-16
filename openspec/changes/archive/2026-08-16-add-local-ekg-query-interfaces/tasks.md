## 1. Query API Foundation

- [x] 1.1 Add `engineering_kg.query` module with an `EngineeringKgQuery` facade that can be constructed from a canonical `GraphSnapshot`.
- [x] 1.2 Implement deterministic result serialization helpers for graph identifiers, kinds, names, properties, evidence identifiers, confidence values, and supported locator identity fields.
- [x] 1.3 Add `EngineeringKgQuery.from_store(path)` that reads persisted graph data through the existing canonical persistence readback boundary.
- [x] 1.4 Add query-specific error/result types for missing objects, invalid graph inputs, and optional graph-integrity validation failures.

## 2. Core Query Operations

- [x] 2.1 Implement deterministic requirement listing from canonical requirement and OpenSpec requirement nodes.
- [x] 2.2 Implement requirement filtering by explicit graph facts such as capability, service, OpenSpec change, or evidence reference.
- [x] 2.3 Implement deterministic service and repository listing from workspace registry graph facts without merging unrelated service logic.
- [x] 2.4 Implement deterministic active and archived OpenSpec change listing with represented artifacts, touched specs, traceability links, and evidence identifiers.
- [x] 2.5 Implement traceability lookup for known graph object identifiers using only existing canonical and derived graph edges.
- [x] 2.6 Ensure non-confident relationships are returned with their stored confidence and are not upgraded by query logic.

## 3. Safety And Validation Behavior

- [x] 3.1 Ensure query output excludes source code, call graphs, dependency graphs, symbol bodies, OpenLore analysis payloads, external API payloads, credentials, and tokens.
- [x] 3.2 Ensure `CodeLocator` serialization returns only repository, revision, file, and symbol.
- [x] 3.3 Ensure OpenSpec and external reference serialization returns only graph-stored identity, properties, evidence identifiers, and supported locator identity fields.
- [x] 3.4 Add an option for store-backed or wrapper-backed queries to require graph integrity validation before returning traceability results.
- [x] 3.5 Return explicit empty or missing-link results when graph relationships are absent instead of inventing traceability from names, repository hints, or prompt context.

## 4. FactMCP Tool Wrapper

- [x] 4.1 Verify the exact FactMCP package name, import path, dependency source, and supported tool registration API before adding project dependency metadata.
- [x] 4.2 Add a FactMCP-facing module such as `engineering_kg.mcp.factmcp_server` that registers Engineering KG query operations as tools only.
- [x] 4.3 Implement requirements query tool wrappers that validate inputs and delegate to `EngineeringKgQuery`.
- [x] 4.4 Implement service query tool wrappers that validate inputs and delegate to `EngineeringKgQuery`.
- [x] 4.5 Implement OpenSpec change query tool wrappers that validate inputs and delegate to `EngineeringKgQuery`.
- [x] 4.6 Implement traceability query tool wrappers that validate inputs, honor required validation behavior, and delegate to `EngineeringKgQuery`.
- [x] 4.7 Ensure FactMCP wrappers do not expose query operations as MCP resources for this MVP change.
- [x] 4.8 Map query and validation failures to deterministic FactMCP tool error payloads without leaking source-owned payloads or sensitive values.

## 5. Tests

- [x] 5.1 Add unit tests for snapshot-backed query construction and local-first behavior.
- [x] 5.2 Add unit tests for store-backed query construction through the existing persistence readback boundary.
- [x] 5.3 Add unit tests for requirement, service, OpenSpec change, and traceability query ordering and filtering.
- [x] 5.4 Add unit tests confirming absent graph relationships return explicit empty or missing-link results.
- [x] 5.5 Add unit tests confirming forbidden source-owned payloads and sensitive fields are excluded from query output.
- [x] 5.6 Add wrapper tests confirming each FactMCP tool delegates to the reusable query API and contains no graph traversal logic.
- [x] 5.7 Add wrapper tests confirming query operations are exposed as FactMCP tools only, not resources.
- [x] 5.8 Add validation-required wrapper tests confirming invalid graphs block traceability responses with structured diagnostics.

## 6. Verification

- [x] 6.1 Run focused query API and FactMCP wrapper tests.
- [x] 6.2 Run existing persistence, derivation, validation, and pipeline tests to check integration boundaries.
- [x] 6.3 Run `openspec validate add-local-ekg-query-interfaces` before implementation is marked ready.
