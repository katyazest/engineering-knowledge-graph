## Why

LLM agents need a stable local interface for inspecting Engineering KG facts without reimplementing graph traversal, persistence readback, or traceability rules in prompts and ad hoc scripts. This is needed now because the MVP pipeline already defines local persistence, derivation, and validation, and the next useful boundary is agent-facing query access over the generated local graph.

## What Changes

- Add reusable local Python query APIs over canonical Engineering KG snapshots and the LadybugDB-compatible local store.
- Provide query operations for requirements, services, OpenSpec changes, and traceability relationships using deterministic graph logic.
- Add thin MCP wrappers that delegate to the reusable Python query APIs without duplicating graph traversal or business rules.
- Keep the query surface local-first, deterministic, credential-free, and limited to Engineering KG facts plus locator identities.
- Preserve OpenLore ownership of code intelligence by returning `CodeLocator` references instead of source code, call graphs, dependency graphs, symbol bodies, or OpenLore analysis payloads.

## Capabilities

### New Capabilities

- `local-ekg-query-api`: Reusable Python query interface for reading canonical Engineering KG facts about requirements, services, OpenSpec changes, and traceability from local graph snapshots or the local LadybugDB-compatible store.
- `ekg-mcp-query-wrappers`: Thin MCP-facing wrappers that expose selected Engineering KG query operations to local agents by delegating to the reusable Python query API.

### Modified Capabilities

None.

## Impact

- Affected code: `src/engineering_kg/` query modules, package exports, and tests.
- Affected local interfaces: new Python API functions/classes and MCP wrapper entry points.
- Affected graph sources: existing canonical graph snapshots and LadybugDB-compatible local storage readback.
- Dependencies: no new cloud, credential, compilation, publishing, OpenLore query, Jira, Bitbucket, Confluence, or external MCP dependency is introduced by the query API itself.
- Systems: Engineering KG local pipeline output and local agent/MCP access only.
