## Context

Engineering KG already has a local-first workspace registry loader that parses `layout.openlore_path`, global OpenLore federation settings, and per-repository OpenLore federation inputs from `repo-index.yaml`. The registry also enforces the MVP layout boundary that workspace-level generated OpenLore state and LadybugDB graph state must live outside the OpenSpec store repository and implementation repository roots.

This change adds the next MVP pipeline step: validating the workspace-level OpenLore source after registry loading and before later extractors rely on code context. OpenLore remains the authoritative source for code graph, architecture, impact, and symbol resolution. Engineering KG must not query, rebuild, persist, or duplicate OpenLore code graph details during this validation.

## Goals / Non-Goals

**Goals:**

- Validate that the workspace-level OpenLore source configured by the registry is usable as a local generated-state source.
- Validate that OpenLore federation repository references are deterministic and resolvable relative to the workspace/repository layout.
- Report the validation as a distinct pipeline stage named `workspace-openlore-source`.
- Keep the stage local-first, deterministic, and independently testable.
- Preserve the EKG/OpenLore ownership boundary by exposing only source metadata and references, not code graph contents.

**Non-Goals:**

- Do not create, rebuild, refresh, or mutate `.openlore` indexes.
- Do not call OpenLore MCP, Jira MCP, Bitbucket MCP, Confluence, cloud services, or network APIs.
- Do not add source code, call graph, dependency graph, symbol bodies, or OpenLore analysis details to the canonical Engineering KG graph.
- Do not replace OpenLore as the authoritative code intelligence system.
- Do not implement downstream OpenSpec, Jira, Bitbucket, normalization, derivation, validation, or MCP query stages.

## Decisions

### Decision: Implement a separate `workspace-openlore-source` pipeline stage

The pipeline runner should treat OpenLore source validation as its own configured/executed stage after `workspace-registry`. This matches the documented MVP sequence and gives later extractors a clear precondition: workspace layout and OpenLore source references have been validated before code-aware processing begins.

Alternative considered: fold this into the existing workspace registry stage. That would hide the lifecycle boundary between loading stable topology and validating the generated OpenLore source, making pipeline reports less useful and making later stage dependencies harder to reason about.

### Decision: Reuse the parsed `WorkspaceRegistry` as input

The validation stage should consume the existing `WorkspaceRegistry` object instead of reparsing `repo-index.yaml`. It should use `registry.layout.resolved_openlore_path`, `registry.openlore`, and `registry.federation_repositories()` as its inputs.

Alternative considered: add a separate OpenLore configuration file. That would duplicate configuration already present in the registry and weaken the registry as the deterministic source of local workspace topology.

### Decision: Validate references, not OpenLore contents

The stage should verify local reference shape and boundaries: the resolved workspace OpenLore path, federation enablement, included repositories, and per-repository index locations. It may check local path existence when the requirement says the source must already be present, but it must not inspect or serialize code graph contents.

Alternative considered: read OpenLore index internals to prove freshness or symbol availability. That crosses the ownership boundary and risks duplicating OpenLore code intelligence inside EKG. Freshness and symbol resolution should remain OpenLore concerns.

### Decision: Return deterministic stage metadata outside the canonical graph

Validation output should be represented as deterministic pipeline status/stage metadata, not new canonical graph nodes or edges. The current graph snapshot can continue to come from the workspace registry stage, with OpenLore references already present as layout/repository properties.

Alternative considered: add OpenLore source nodes to the canonical graph. That would make generated tooling state look like domain knowledge and could encourage later stages to persist details that belong to OpenLore.

### Decision: Keep script behavior as a thin wrapper

The build script should continue delegating to reusable Python modules. If the registry configures `workspace-openlore-source`, the runner should report that stage in `configured_stages` and `executed_stages` once validation succeeds.

Alternative considered: add validation logic directly to the script wrapper. That would make the script harder to reuse and test, and would diverge from the current Scripts/MCP -> reusable Python modules -> LadybugDB architecture.

## Risks / Trade-offs

- OpenLore source freshness is not proven by this stage -> Keep `freshness_policy` as metadata for later OpenLore integration and document that validation only confirms local source configuration/reference usability.
- Existing fixtures may not contain a real `.openlore` directory -> Use focused fixtures for source-present and source-missing scenarios, and make the required existence behavior explicit in the spec before implementation.
- Adding stage metadata could change pipeline output expectations -> Update tests for configured registries that include the new stage while preserving existing bootstrap and registry-only behavior.
- Registry and OpenLore validation boundaries can overlap -> Keep repository-root placement checks in the registry loader and reserve the new stage for source-level validation and federation reference checks.

