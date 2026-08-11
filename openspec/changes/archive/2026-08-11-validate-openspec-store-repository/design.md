## Context

The MVP workspace separates the non-Git project workspace from independent Git repositories. OpenSpec has its own local store registry/config for standalone stores registered on the machine, exposed through commands such as `openspec store list --json` and `openspec store doctor`. That OpenSpec store registry is the primary authority for store identity when stores are registered.

The requirements repository is also configured through `engineering_kg.store_repository` in `repo-index.yaml` and owns durable requirements, OpenSpec specs, OpenSpec changes, wiki content, and versioned Engineering KG configuration. EKG should use the requirements repository from the workspace registry as a fallback store only when OpenSpec reports no registered stores. Generated OpenLore indexes and generated LadybugDB-compatible graph data belong to the local workspace and must stay outside configured repository roots.

The current `workspace-registry` capability already loads `repo-index.yaml`, validates that `engineering_kg.store_repository` references a repository with role `requirements`, resolves repository paths, and enforces generated-state boundaries for explicit non-Git workspace layouts. The pipeline runner already supports optional configured validation stages, as shown by `workspace-openlore-source`. OpenSpec ingestion has a placeholder module, so this change should introduce a narrow store-source validation boundary before adding extraction behavior.

## Goals / Non-Goals

**Goals:**

- Validate one OpenSpec store source before OpenSpec extraction.
- Resolve OpenSpec store paths from OpenSpec's registered store configuration when a store is registered.
- Fall back to the requirements repository from the loaded workspace registry when OpenSpec reports no registered stores.
- Cross-check registered stores against the workspace registry so the selected store corresponds to the requirements repository boundary, including the multiple-store case.
- Require a usable OpenSpec root under the validated store repository.
- Return deterministic validation metadata suitable for pipeline status reporting and tests.
- Keep validation local-first and free of credentials, network calls, generated graph reads, OpenLore MCP calls, Jira calls, Bitbucket calls, Confluence calls, compilation, and publishing.

**Non-Goals:**

- Implement full OpenSpec specification/change extraction.
- Register, unregister, remove, or mutate OpenSpec stores through the OpenSpec CLI.
- Read implementation source code, OpenLore code graph contents, LadybugDB records, Jira data, Bitbucket data, Confluence pages, or generated documentation.
- Change the LadybugDB persistence format or OpenLore source validation contract.

## Decisions

### Add a dedicated OpenSpec store source validator

Create a small validator in the OpenSpec ingestion boundary, likely `engineering_kg.ingest.openspec`, that accepts a loaded `WorkspaceRegistry` plus OpenSpec store discovery data and returns an immutable result object.

Rationale: OpenSpec store validation is source validation for requirements and intended changes, not generic repository inventory parsing. Keeping it in the OpenSpec ingest boundary avoids overloading `project.registry` with extraction-specific checks while still reusing registry-resolved repository metadata for fallback and cross-checks.

Alternative considered: extend `load_workspace_registry()` to validate the physical OpenSpec root immediately. That would make any registry load depend on local filesystem presence of an `openspec/` directory, even for pipeline modes that only need topology or graph references. The current registry loader should remain focused on structural registry validity.

### Prefer OpenSpec registered stores, then fall back to registry identity

The validator should first use OpenSpec store discovery data from `openspec store list --json` or the equivalent OpenSpec store configuration reader, and it should resolve the requirements repository from `registry.engineering_kg.store_repository` for cross-checking.

Selection rules:

- If multiple registered stores are available, choose the registered store whose resolved path matches the requirements repository from `repo-index.yaml`.
- If exactly one registered store is available, select it only if its resolved path matches the requirements repository from `repo-index.yaml`.
- If registered store discovery and the requirements repository do not identify the same store, require an explicit store id or deterministic configuration input before extraction.
- If no stores are registered, select the repository whose id equals `registry.engineering_kg.store_repository`, require role `requirements`, and use that repository's `resolved_path` as the fallback store repository root.

The OpenSpec root should resolve according to the selected store path, with the fallback resolving as `<requirements_repository.resolved_path>/openspec`.

Rationale: OpenSpec owns store registration and is more reliable than duplicating store identity in EKG configuration. The registry fallback preserves the MVP local-first workflow on machines where no standalone store is registered yet.

Alternative considered: always use `repo-index.yaml` as the store source. That ignores OpenSpec's own store configuration and can diverge from the user's active OpenSpec setup.

Alternative considered: use OpenSpec nearest-root behavior. That behavior is useful for authoring local changes, but it is not the deterministic pipeline contract because it can accidentally bind extraction to the executor's current directory.

### Cross-check selected store against workspace registry

The validator should compare registered OpenSpec store paths to the requirements repository resolved from `engineering_kg.store_repository` in `repo-index.yaml` before extraction. A registered store match becomes the selected store. If registered stores exist but no registered path matches the requirements repository path, the validator should stop and require explicit store selection. If no store is registered, the fallback requirements repository path becomes the selected store path.

Rationale: OpenSpec is the authority for registered stores, while `repo-index.yaml` is the workspace authority for repository roles and generated-state boundaries. Both are needed to avoid extracting requirements from a registered store that does not belong to the EKG workspace.

### Validate minimum usable store shape

The first validation pass should check deterministic filesystem facts only:

- registered OpenSpec store discovery succeeds or returns an empty list;
- registered OpenSpec store paths are cross-checked against the requirements repository in `repo-index.yaml`;
- a selected registered store path matches the requirements repository in `repo-index.yaml`, or no registered store exists and the requirements repository fallback is used;
- the fallback repository resolves to exactly one repository entry when needed;
- the workspace repository role is `requirements`;
- the repository path exists as a directory;
- the selected store contains an `openspec` root when the store path is the repository root;
- the resolved OpenSpec root contains `specs` and `changes` directories when extraction will depend on both durable specs and intended changes;
- generated workspace OpenLore and Engineering KG storage paths are not inside the store repository or other configured repository roots, relying on existing registry layout validation where possible.

Rationale: These checks prove that later extraction will read from the intended source of truth without adding semantic parsing or external system dependencies.

Alternative considered: parse every OpenSpec file during store-source validation. That belongs to later extraction/validation stages; this change should establish the source boundary first.

### Report deterministic metadata, not content

The result should expose stable metadata such as validation status, selection source (`registered-store` or `registry-fallback`), store id when available, store repository id, role, resolved repository path, resolved OpenSpec root, specs path, changes path, and boolean existence checks or counts if needed. It must not return specification bodies, change text, source code, generated graph records, credentials, tokens, or external API payloads.

Rationale: Pipeline status needs to explain which source was validated while preserving clear ownership boundaries and avoiding accidental leakage of requirements or implementation details into generic status surfaces.

Alternative considered: include discovered spec/change filenames. That could be useful later, but it starts to overlap with extraction. If needed, filename inventory should be introduced by the OpenSpec extractor capability with explicit requirements.

### Add an optional pipeline stage

Add a configured stage name such as `openspec-store-source`. When the registry's `engineering_kg.pipeline_stages` includes this stage, the runner should execute it after `workspace-registry` has loaded the registry and before later OpenSpec extraction stages. `PipelineResult` should include the validation result when the stage runs, and `as_dict()` should serialize it deterministically.

Rationale: This mirrors the existing `workspace-openlore-source` stage pattern and keeps the runner configurable for MVP stage-by-stage development.

Alternative considered: always validate the OpenSpec store whenever a registry is loaded. Optional stage execution better preserves existing registry-only and OpenLore-only behavior.

## Risks / Trade-offs

- OpenSpec store path may be valid structurally but contain invalid specs or changes -> Mitigation: keep this capability limited to source validation and add semantic extraction/validation in later OpenSpec extractor work.
- Multiple registered stores can make automatic selection ambiguous when none match the repo-index requirements repository -> Mitigation: select the matching registered requirements repository store when exactly one match exists, otherwise fail with an explicit validation error unless a store id is provided by configuration or command input.
- OpenSpec store command output can differ by CLI version -> Mitigation: isolate store discovery behind a narrow adapter and test validator behavior with structured discovery data.
- Fixtures may need directories that look like Git repositories or OpenSpec stores -> Mitigation: validate only directory shape required by the source contract unless a later requirement explicitly needs Git metadata.
- Stage ordering mistakes could let extraction run before source validation -> Mitigation: pipeline tests should assert deterministic configured and executed stage order when `openspec-store-source` is configured.
- Registry and source validation can duplicate the requirements-role check -> Mitigation: keep registry validation as structural protection and repeat or assert the role in source validation for clear fallback and cross-check error messages at the OpenSpec boundary.
