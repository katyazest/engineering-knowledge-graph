## Context

The MVP documentation defines a project workspace that is a normal local directory, not a Git repository. That workspace contains generated state under `.openlore/` and `.engineering-kg/ladybugdb/`, implementation Git repositories under `src/codebase_repos/`, and one OpenSpec store Git repository under `openspec/requirements_repo/`.

The current `workspace-registry` implementation loads a `repo-index.yaml`, parses repository inventory, validates one-service-one-repository topology, exposes OpenLore federation inputs, and produces deterministic graph objects. Repository paths currently resolve relative to the registry file location, which works for a repo-local registry but does not explicitly model the non-Git workspace root or the ownership boundary between workspace-generated state and versioned repositories.

## Goals / Non-Goals

**Goals:**

- Represent the project workspace root as the execution boundary for generated local state.
- Validate that the registry names exactly one OpenSpec store repository.
- Resolve implementation repository paths, OpenLore generated state paths, and graph storage paths against the workspace layout deterministically.
- Preserve the rule that generated OpenLore indexes and generated LadybugDB-compatible graph data are local workspace state, not versioned OpenSpec-store or source-repository content.
- Keep canonical graph output limited to stable topology and references.

**Non-Goals:**

- Creating, rebuilding, or querying OpenLore indexes.
- Implementing a native LadybugDB bridge or changing the persistence adapter contract.
- Moving repositories on disk or managing Git state.
- Publishing generated graph data.
- Adding semantic extraction or derived architecture/code facts to `repo-index.yaml`.

## Decisions

### Model the workspace root explicitly

Add a registry-level workspace layout concept that can identify the local project workspace root independently from the `repo-index.yaml` file path. The default should preserve existing behavior for repo-local fixtures, while the new layout supports an OpenSpec store repo nested under the workspace.

Alternative considered: infer the workspace root from the OpenSpec store repository path. This is brittle because different workspaces may place the store at different relative depths and because the registry should validate layout instead of relying on path guessing.

### Keep the OpenSpec store as a repository role plus configured identity

Continue using `engineering_kg.store_repository` as the configured repository id for the OpenSpec store and require that the referenced repository exists with the `requirements` role. This avoids introducing a second competing store identifier while making the existing field stricter.

Alternative considered: add a separate top-level `openspec_store` block. That would make the store identity clearer, but it would duplicate repository inventory fields already represented by `repositories[]`.

### Resolve generated state against the workspace root

Treat workspace OpenLore and Engineering KG graph storage paths as workspace-local paths. The default graph storage remains `.engineering-kg/ladybugdb`; workspace OpenLore defaults to `.openlore/` or configured workspace-level OpenLore paths. Repository-level OpenLore index references remain references only and MUST NOT cause index creation during registry loading.

Alternative considered: resolve generated state paths relative to the requirements repository. That would blur ownership because the requirements repository is versioned and should not own generated OpenLore or graph data.

### Preserve repository path compatibility

Maintain support for existing repository entries whose paths resolve relative to the registry file. Add layout-aware behavior as an extension so older `repo-index.yaml` fixtures and repository inventory semantics continue to load.

Alternative considered: make all paths workspace-root-relative immediately. That is cleaner long term, but it risks breaking existing indexes and tests before migration guidance exists.

### Store only stable references in graph output

Canonical graph conversion should include workspace, repository, service, OpenSpec store, OpenLore configuration, and graph storage references, but not generated data or OpenLore code graph contents. `CodeLocator` resolution remains delegated to OpenLore MCP in later stages.

Alternative considered: include resolved OpenLore symbols or graph files in the registry graph snapshot. That conflicts with the MVP boundary that OpenLore owns code intelligence and EKG stores only canonical engineering facts.

## Risks / Trade-offs

- Existing path semantics may become confusing if both registry-file-relative and workspace-root-relative paths are accepted -> Mitigate with explicit field names, validation errors, and fixtures covering both layouts.
- The workspace root may point at a Git repository by mistake -> Mitigate by validating that the project workspace root is not required to be Git-managed and by avoiding any Git assumptions at that level.
- The OpenSpec store repository may be misconfigured as a code repository -> Mitigate by requiring the configured store repository to exist and use the `requirements` role.
- Generated state paths may accidentally target a versioned repository -> Mitigate by validating configured generated-state paths against repository resolved paths where practical.
- Local path validation can be too strict for transferred workspaces -> Mitigate by validating deterministic path relationships without requiring every path to exist unless a later validation stage explicitly checks filesystem availability.

## Migration Plan

1. Extend registry models and parser with layout fields while preserving current fixture behavior.
2. Add tests and fixtures for the target non-Git workspace layout.
3. Add validation for the configured OpenSpec store repository role and generated-state ownership boundaries.
4. Update canonical graph serialization to expose stable workspace layout references.
5. Update examples or schema documentation after tests define the accepted shape.

Rollback is straightforward because this change is additive at the planning level: keep existing registry-file-relative behavior and remove the new layout validations if they block existing users.

## Open Questions

- Should the registry field for workspace root be required in the target layout, or should it default to the parent of the OpenSpec store repository?
- Should generated-state path checks detect nested paths inside any Git repository by filesystem probing, or only by comparing configured repository paths?
- Should workspace-level OpenLore use one configured index path for the whole workspace or only repository-level index references in the MVP?
