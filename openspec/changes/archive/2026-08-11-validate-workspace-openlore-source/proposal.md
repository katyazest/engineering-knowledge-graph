## Why

The MVP pipeline needs to trust a workspace-level OpenLore source for code intelligence while keeping Engineering KG focused on canonical engineering facts and lightweight code references. Validating that source now establishes the boundary between OpenLore-owned code graph data and EKG-owned graph data before downstream extractors, normalization, derivation, and MCP queries depend on code context.

## What Changes

- Add validation for the configured workspace-level OpenLore source under the local project workspace.
- Confirm that OpenLore generated state is outside the OpenSpec store repository and implementation repository roots.
- Validate that repositories included in OpenLore federation have deterministic local index references without querying, rebuilding, or duplicating the OpenLore code graph.
- Expose validated OpenLore source metadata to later pipeline stages as references only.
- Preserve local-first execution with no network access, API keys, cloud services, compilation, publishing, Jira, Bitbucket, or external MCP dependency.

## Capabilities

### New Capabilities

- `workspace-openlore-source`: Validates workspace-level OpenLore source configuration, local generated-state boundaries, and repository federation references without storing OpenLore code graph details in Engineering KG.

### Modified Capabilities

- `pipeline-runner`: Add support for executing and reporting a workspace OpenLore source validation stage after the workspace registry stage and before later source extractors.

## Impact

- Affected specs: new `workspace-openlore-source`; modified `pipeline-runner`.
- Affected code: reusable Python pipeline modules, workspace registry/OpenLore configuration readers, local script wrapper output, and focused tests/fixtures for valid and invalid workspace OpenLore layouts.
- Affected data boundaries: OpenLore remains authoritative for code graph, architecture, impact, and symbol resolution; Engineering KG stores only deterministic engineering facts and `CodeLocator` references containing repository, revision, file, and symbol.
- No breaking changes expected.
