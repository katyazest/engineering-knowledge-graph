## Why

Plane task `EKG-46` (source backlog item `EKG-15`) needs a runtime boundary that lets Engineering KG (EKG) turn implementation-evidence references into precise code-resolution and navigation requests for OpenLore. EKG currently validates OpenLore workspace configuration and can retain `CodeLocator` evidence, but it has no compact, validated contract for invoking code resolution while preserving OpenLore as the authoritative owner of the code graph.

This follows the completed `EKG-09` cross-graph evidence model and `EKG-14` PR-to-code candidate extraction: resolution must remain repository- and revision-specific, and failure to resolve a symbol must be visible rather than guessed.

## What Changes

- Add a reusable, project-owned OpenLore semantic-bridge contract for resolving changed files to symbols and for constructing an OpenLore navigation handoff from a complete `CodeLocator`.
- Bind every bridge request to a repository registered in the workspace registry (`repo-index.yaml`) and to an immutable revision that agrees with its implementation-evidence reference.
- **Federation is optional**: if a registered repository has an OpenLore federation configuration, use its index location; if federation is absent, fall back to the registered repository's local path from `repo-index.yaml`.
- Define deterministic resolved, unresolved, ambiguous, invalid-response, and unavailable-provider outcomes; only one exact resolved symbol may produce a `CodeLocator`.
- Preserve the EKG/OpenLore ownership boundary: EKG retains compact identities and outcomes only, while code graphs, source bodies, semantic reasoning, and navigation results remain in OpenLore.
- Keep the bridge independently testable through a project-owned provider port and local fixtures; no OpenLore internal implementation, index construction, or provider-specific payload model is added to EKG.

## Capabilities

### New Capabilities
- `openlore-semantic-bridge`: Validated repository/revision-scoped code-symbol resolution and navigation-handoff contract between EKG implementation evidence and OpenLore.

### Modified Capabilities
- None.

## Impact

- Affected project-owned areas: `engineering_kg.openlore` (or a dedicated bridge module), normalized implementation-evidence integration, and fixture-based tests.
- External infrastructure: OpenLore remains an external authoritative code-intelligence provider; this change defines only EKG's adapter port and compact boundary DTOs. Federation configuration is optional; the bridge works with or without it.
- Canonical graph and persistence: no OpenLore code graph, source code, or semantic response is ingested or persisted. Existing `CodeLocator` and PR candidate evidence remain the compatible compact reference format.
- Pipeline: no automatic OpenLore indexing or broad code-analysis stage is introduced; callers explicitly invoke the reusable bridge with validated implementation evidence.

## Design Notes: Federation Fallback Strategies

When federation configuration is absent, the bridge uses the workspace registry (`repo-index.yaml`) as the routing authority. Alternative fallback strategies that could be considered in future changes:

1. **Explicit provider configuration** - A dedicated `openlore-provider.yaml` mapping repositories to provider endpoints/index paths, separate from federation.
2. **Environment-based resolution** - CI/CD or runtime environment variables specifying the OpenLore index location per repository.
3. **Discovery protocol** - A lightweight query to a known OpenLore registry service to resolve repository-to-index mappings dynamically.
4. **Convention-over-configuration** - Default index paths derived from repository names/paths (e.g., `.openlore/index/` under each repo root).

The current change adopts the repo-index fallback described above as the minimal, deterministic approach that requires no additional configuration files or runtime services.
