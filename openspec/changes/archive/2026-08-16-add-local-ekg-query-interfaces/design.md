## Context

The Engineering KG MVP is local-first and deterministic. Current repo state defines canonical graph ontology, local persistence/readback, pipeline stage ordering, OpenSpec graph extraction, derivation, and graph integrity validation. The documented MVP sequence places reusable Python APIs before script wrappers and MCP wrappers, with the boundary `Scripts/MCP -> Reusable Python modules -> LadybugDB`.

This change adds the agent-facing read side of that architecture. LLM agents should inspect requirements, services, OpenSpec changes, and traceability through stable local query operations instead of reimplementing graph traversal over snapshots, persistence files, or pipeline metadata.

The user decision for this change is that MCP exposure should use FactMCP as the wrapper surface. The local repository does not currently contain FactMCP examples or dependency metadata, so implementation must verify the exact FactMCP package, import path, and registration API before adding it to project dependencies.

## Goals / Non-Goals

**Goals:**

- Provide reusable Python query APIs over canonical `GraphSnapshot` data and the existing LadybugDB-compatible local readback boundary.
- Support deterministic queries for requirements, services, OpenSpec changes, and traceability relationships.
- Expose selected query operations through thin FactMCP wrappers for local agent use.
- Keep all graph traversal, filtering, serialization, and traceability behavior in reusable Python modules, not in FactMCP wrapper functions.
- Return only Engineering KG facts, evidence references, and locator identity fields; preserve OpenLore ownership of detailed code intelligence.
- Keep the query API testable without starting an MCP server.

**Non-Goals:**

- No source extraction, semantic extraction, LLM reasoning, cloud calls, generated documentation publishing, or external enterprise-system fetching.
- No OpenLore MCP querying from the Engineering KG query API or FactMCP wrappers.
- No duplication of source code, call graphs, dependency graphs, symbol bodies, OpenLore analysis payloads, Jira payloads, Bitbucket payloads, Confluence content, credentials, or tokens.
- No query-specific graph derivation rules inside wrappers.
- No replacement of the existing LadybugDB-compatible persistence boundary.

## Decisions

### Decision: Add a reusable query module as the authoritative read API

Add a module such as `engineering_kg.query` that exposes a small, typed query facade over `GraphSnapshot`:

- `EngineeringKgQuery.from_snapshot(snapshot)`
- `EngineeringKgQuery.from_store(path)`
- `list_requirements(...)`
- `list_services(...)`
- `list_changes(...)`
- `get_traceability(...)`

The API should return deterministic DTOs or dictionaries built from canonical ontology objects. Results must be sorted by stable IDs or explicit names, and filters should use explicit graph fields such as node kind, properties, edge kind, source ID, target ID, and evidence IDs.

Rationale: this keeps graph behavior reusable by tests, scripts, and MCP wrappers. It also makes FactMCP an adapter choice rather than the owner of Engineering KG query semantics.

Alternative considered: implement query logic directly in MCP tools. That would be quick for the first tool but would duplicate traversal rules, make local tests weaker, and contradict the MVP architecture.

### Decision: Read persisted graph data through the persistence boundary

Store-backed queries should call the existing persistence readback function, for example `read_graph_snapshot(path)`, and then query the returned canonical snapshot. The query module should not parse storage files directly or depend on LadybugDB-native APIs.

Rationale: persistence already owns readback integrity and adapter compatibility. Query code should consume the canonical graph contract that the rest of the pipeline uses.

Alternative considered: query the local graph file or LadybugDB adapter internals directly. That would create a second storage contract and make future LadybugDB adapter replacement harder.

### Decision: Use FactMCP tools only as the thin wrapper surface

Create a FactMCP-facing module, for example `engineering_kg.mcp.factmcp_server`, that registers query operations as FactMCP tools and delegates immediately to `engineering_kg.query`. The wrapper will not expose query operations as MCP resources in the MVP.

Wrapper responsibilities should be limited to:

- accepting local configuration such as graph store path or snapshot source;
- validating wrapper input shapes;
- calling the reusable query API;
- returning deterministic serialized results;
- mapping query exceptions to stable MCP-facing error payloads.

Wrapper responsibilities must not include graph traversal, derivation, validation, source extraction, persistence internals, or service-specific business rules.

Rationale: the user wants FactMCP as the MCP wrapper surface and query operations exposed as tools. The Engineering KG must still remain usable by non-MCP callers and tests.

Alternative considered: use the official Python MCP SDK directly. That is a reasonable fallback if FactMCP is unavailable, but this change should target FactMCP unless implementation-time verification proves it cannot run in the local and enterprise constraints.

### Decision: Keep query operations deliberately narrow for MVP

Initial query operations should cover the agent workflows named in the proposal:

- requirements by capability, service, change, or evidence reference where the graph contains those relationships;
- services and repositories known to the workspace registry graph;
- active and archived OpenSpec changes with their touched specs and artifacts;
- traceability paths represented by existing canonical edges and deterministic derived edges.

Queries should not invent missing links from names, repository hints, or prompt context. If a relationship is absent or non-confident, the API should return that state explicitly.

Rationale: deterministic query APIs are valuable only if agents can trust that results reflect graph facts rather than fresh inference.

Alternative considered: provide a generic graph search first. That would be flexible, but it would push graph interpretation back into agents and weaken the user-facing requirement.

### Decision: Validate graph integrity before serving query results when configured

The query API may accept an already validated snapshot, but store-backed or wrapper-backed entry points should have a clear option to require prior graph integrity validation metadata or run local validation before serving results. Invalid graph diagnostics should be surfaced as structured query errors rather than partial traceability answers.

Rationale: the previous MVP stage exists to prevent downstream query consumers from using broken graph references.

Alternative considered: always query whatever graph is available. That makes local exploration easier but risks returning misleading traceability to agents.

## Risks / Trade-offs

- FactMCP package details are not present in this repo -> Verify the exact dependency and registration API during implementation; keep the wrapper isolated so the query API is not blocked by wrapper mechanics.
- Query DTOs may duplicate ontology serialization too much -> Start with thin result objects that reference canonical IDs, kinds, names, properties, evidence IDs, and locator identities.
- Agents may need richer path finding than MVP query operations provide -> Add only explicit, spec-covered query operations first; defer generic traversal until there is a concrete use case.
- Validation-on-query can add overhead -> Make validation behavior explicit and deterministic, and allow callers that already validated the snapshot to pass that state in.
- Wrapper errors may leak local filesystem details -> Return configured local paths only when they are part of the user's local input; never include secrets, tokens, payload bodies, or sensitive external data.

## Migration Plan

1. Add `engineering_kg.query` with snapshot-backed query operations and focused unit tests.
2. Add store-backed query construction through existing `read_graph_snapshot`.
3. Add FactMCP wrapper module after verifying exact FactMCP dependency and API details.
4. Add wrapper tests that confirm each FactMCP operation delegates to the reusable query API.
5. Add documentation or examples for local startup only if required by the implementation tasks.
6. Rollback is removing the FactMCP wrapper registration and query module imports; existing pipeline, persistence, derivation, and validation behavior remains unchanged.

## Open Questions

- TODO: Confirm the exact FactMCP package name, import path, dependency source, and supported server registration API.
- TODO: Decide whether wrapper startup should require a graph store path, accept one per request, or support both.
