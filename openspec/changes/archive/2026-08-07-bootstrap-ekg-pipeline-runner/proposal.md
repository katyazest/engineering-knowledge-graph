## Why

The MVP Engineering Knowledge Graph pipeline needs a runnable, testable base before later stages add canonical ontology, registry loading, persistence, OpenLore integration, or enterprise MCP adapters. This change creates the smallest useful local-first pipeline slice: a project entry point that starts, returns an empty valid status, and can be verified by automated tests.

## What Changes

- Define the Python package and test setup needed to run and verify the project locally.
- Add a minimal reusable Python pipeline module/function that can be imported by future pipeline stages.
- Add one Python script entry point that invokes the reusable pipeline module/function.
- Add a smoke test proving that the pipeline starts and returns an empty valid result/status.
- Keep the bootstrap deterministic, local-first, and runnable without API keys, cloud services, compilation, or publishing.
- Keep this bootstrap free of LadybugDB persistence, Jira import, Bitbucket import, OpenLore querying, wiki generation, semantic extraction, and code graph duplication.

## Capabilities

### New Capabilities
- `pipeline-runner`: Provides the runnable project foundation, reusable pipeline start module/function, Python script entry point, and smoke-testable empty pipeline result.

### Modified Capabilities

None.

## Impact

- Affects project packaging/test configuration, `src/engineering_kg/`, `scripts/`, and tests.
- Establishes the execution contract that later pipeline stages can extend.
- Aligns with the MVP plan and constraints in `docs/engineering-kg-development-plan-mvp.md`, `docs/engineering-knowledge-graph-pipeline-mvp.md`, and `docs/engineering-kg-project-constraints-mvp.md`.
- Does not change external APIs, enterprise systems, OpenLore indexes, LadybugDB storage, Jira, Bitbucket, generated wiki content, MkDocs, llmwiki-cli, dotMD, semantic extraction, or cloud LLM integrations.
