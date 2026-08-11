## Why

The Engineering KG MVP needs to run from a local project workspace that is not itself a Git repository while keeping generated OpenLore and graph state separate from versioned requirements and implementation source code. The current registry capability loads `repo-index.yaml` relative to the registry file, but it does not yet define the workspace-level layout needed to coordinate sibling code repositories, one OpenSpec store repository, and local generated storage.

## What Changes

- Extend workspace registry requirements to support a non-Git project workspace root as the execution boundary for Engineering KG.
- Define how the registry identifies the single OpenSpec store repository that owns requirements, OpenSpec changes, wiki content, and versioned EKG configuration.
- Define how implementation repositories are represented as independent Git repositories under the workspace, with one service mapped to one repository.
- Define workspace-level generated state locations for OpenLore indexes and the local LadybugDB-compatible EKG graph store.
- Preserve the ownership boundary that generated OpenLore indexes and generated graph data are local workspace state, not content owned by the OpenSpec store repository or implementation repositories.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workspace-registry`: Add requirements for resolving and validating a non-Git project workspace layout with workspace-level OpenLore, independent code repositories, one OpenSpec store repository, and local graph storage.

## Impact

- Affects workspace registry models, loaders, validation, and canonical graph conversion.
- Affects registry configuration examples and tests for path resolution and ownership boundaries.
- Does not require network access, API keys, cloud services, publishing generated graph data, OpenLore index creation, or LadybugDB-native integration changes.
