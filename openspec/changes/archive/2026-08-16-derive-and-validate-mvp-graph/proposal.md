## Why

The MVP graph already has source extraction and persistence foundations, but it does not yet define how deterministic relationships are derived from persisted canonical facts or how broken graph integrity is detected before downstream use. This change closes that gap so missing mappings, invalid traceability, unresolved references, and graph-shape defects fail locally and predictably before MCP query wrappers consume the graph.

## What Changes

- Add deterministic graph derivation after canonical graph persistence/readback, using only local canonical facts and explicit configuration.
- Add graph integrity validation that reports broken links, missing mappings, invalid traceability, invalid node/edge references, duplicate identities, and unresolved required references before later stages run.
- Ensure derivation and validation preserve source ownership boundaries: OpenLore remains the authority for code intelligence, OpenSpec remains the authority for requirements/specification facts, and LadybugDB-compatible storage remains generated local state.
- Extend the pipeline runner contract so configured derivation and validation stages execute in deterministic order after source extraction and persistence readback and before MCP query wrappers.
- Keep all behavior local-first, deterministic, scriptable from Python, and independently testable.

## Capabilities

### New Capabilities

- `graph-derivation`: Deterministic derivation of Engineering KG relationships from canonical graph snapshots, including relationship identities, evidence propagation, and non-authoritative derived metadata.
- `graph-integrity-validation`: Local validation of graph integrity, traceability, mappings, and referential consistency before derived graph data is used by downstream query stages.

### Modified Capabilities

- `pipeline-runner`: Add orchestration requirements for configured derivation and validation stages, including stage ordering, deterministic reporting, failure handling, and script wrapper output.

## Impact

- Affected code: reusable Python pipeline modules, canonical graph processing modules, validation result models, script wrappers, and tests.
- Affected graph behavior: derived edge generation, validation diagnostics, graph snapshot readback handling, and pipeline stage metadata.
- Affected systems/dependencies: local OpenSpec store input, local workspace registry configuration, OpenLore-owned CodeLocator references, and adapter-compatible LadybugDB persistence boundary.
- No new cloud dependency, API key, compilation, publishing, semantic extraction, or generated documentation behavior is introduced.
