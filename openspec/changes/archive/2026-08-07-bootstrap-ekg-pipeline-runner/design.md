## Context

The MVP Engineering Knowledge Graph project currently has an OpenSpec repository, documentation, empty script entry points, and empty package directories. The MVP constraints require a deterministic, local-first pipeline that runs from Python scripts, exposes reusable Python modules, requires no API keys or cloud services, and keeps each stage independently testable.

This change covers the first development-plan step only: a project skeleton that can start and be tested. Later changes will add canonical ontology, service registry loading, LadybugDB persistence, OpenLore federation checks, OpenSpec extraction, Jira and Bitbucket MCP adapters, normalization, derivation, validation, and MCP wrappers.

## Goals / Non-Goals

**Goals:**

- Provide a minimal Python package/test setup for local development.
- Provide a reusable Python pipeline module/function that future stages can extend.
- Provide a Python script entry point that invokes the reusable module/function.
- Return an empty but valid deterministic pipeline status/result.
- Add smoke tests proving that the reusable function and script entry point start successfully.

**Non-Goals:**

- No LadybugDB persistence or database initialization.
- No canonical ontology, graph node model, edge model, evidence model, or stable ID implementation.
- No OpenLore querying, OpenLore index creation, or code graph storage.
- No Jira MCP, Bitbucket MCP, or external enterprise-system integration.
- No wiki, MkDocs, llmwiki-cli, dotMD, semantic extraction, cloud LLM, compilation, or publishing behavior.

## Decisions

1. Use a reusable Python module/function as the primary execution contract.

   The script entry point will be a thin wrapper over reusable package code, so later script wrappers and MCP wrappers can call the same logic without duplicating pipeline behavior. The alternative was to place initial behavior directly in `scripts/build.py`; that would make the first runnable slice faster, but it would conflict with the MVP rule that reusable Python modules are the pipeline foundation.

2. Return an explicit empty pipeline result/status.

   The bootstrap runner will return structured status data showing that the pipeline started and completed with no configured stages. This gives tests and future stages a stable contract. The alternative was a print-only script, but that would make verification weaker and force later changes to redesign the execution boundary.

3. Keep all behavior local and deterministic.

   The bootstrap will not read secrets, call network services, call MCP tools, inspect OpenLore indexes, or depend on generated external artifacts. This matches the MVP constraints and keeps the first slice transferable to the isolated enterprise machine.

4. Use the existing repository layout.

   Implementation should extend the current `src/engineering_kg/` and `scripts/` layout instead of introducing a separate application framework. The first package setup should be minimal and only include dependencies needed for running and testing the bootstrap.

## Risks / Trade-offs

- The initial result/status may be too small for later stages to reuse directly -> Keep it explicit and simple, and allow later OpenSpec changes to evolve it when canonical ontology or persistence requirements are introduced.
- Packaging choices may not match the final enterprise environment exactly -> Keep the setup minimal, avoid cloud or API-key dependencies, and prefer standard Python tooling that can be mirrored locally.
- Script wrappers may drift from reusable package behavior -> Keep scripts thin and test the package function directly, with one smoke test covering script startup.
- The bootstrap may be mistaken for a complete pipeline -> Name and output should make it clear that zero stages are configured/executed in this change.
