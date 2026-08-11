## Why

The MVP pipeline can now produce deterministic in-memory graph snapshots from the workspace registry, but those graph facts do not yet pass through a durable canonical persistence boundary. This change adds an adapter-compatible LadybugDB persistence foundation so later OpenSpec, OpenLore, Jira, Bitbucket, derivation, and validation stages have a stable graph boundary to write to and verify against.

## What Changes

- Add a local adapter-compatible LadybugDB persistence foundation for canonical Engineering KG graph snapshots.
- Initialize an empty local graph store without requiring network access, API keys, cloud services, compilation, publishing, OpenLore queries, Jira, Bitbucket, Confluence, or MCP servers.
- Persist canonical ontology objects produced by existing pipeline stages: nodes, edges, evidence records, and supported locator/reference values.
- Read persisted graph snapshots back into the existing canonical in-memory ontology contract with deterministic serialization.
- Preserve the OpenLore ownership boundary by storing only CodeLocator identity fields and never duplicating OpenLore-owned code graph details.
- Allow the local pipeline runner to execute a persistence stage when configured, while preserving the existing empty bootstrap behavior and workspace-registry-only behavior.
- Keep this change free of external adapters, semantic extraction, generated wiki output, graph derivation rules, and broad validation rules beyond persistence integrity checks.

## Capabilities

### New Capabilities
- `ladybugdb-persistence`: Defines local initialization, write, and readback behavior for persisting canonical Engineering KG graph snapshots through the LadybugDB persistence boundary.

### Modified Capabilities
- `pipeline-runner`: Allows the local runner to execute an optional LadybugDB persistence stage after canonical graph objects are produced, while preserving deterministic bootstrap and registry-stage behavior.

## Impact

- Affects `src/engineering_kg/` by adding a persistence boundary and integrating it with reusable pipeline modules.
- Affects `scripts/build.py` only as a thin wrapper if persistence configuration or output reporting must be passed through.
- Affects tests for empty store initialization, deterministic graph persistence/readback, CodeLocator boundary preservation, and optional pipeline persistence-stage execution.
- May add or isolate a local LadybugDB dependency or adapter abstraction, but the core MVP behavior must remain local-first and independently testable without live external infrastructure.
- Does not affect OpenLore index ownership, Jira MCP, Bitbucket MCP, Confluence, generated wiki/MkDocs output, llmwiki-cli, dotMD, cloud LLMs, or API-key-dependent integrations.
