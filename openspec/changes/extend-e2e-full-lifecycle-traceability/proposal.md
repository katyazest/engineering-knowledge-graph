## Why

The current MVP end-to-end scenario proves OpenSpec, persistence, derivation, validation, and query flow, but it does not yet prove implementation and verification traceability across Jira user stories, Bitbucket pull requests, code locators, and tests. This leaves the graph unproven for the multirepo lifecycle path agents need when reviewing whether a change is fully specified, implemented, and verified.

## What Changes

- Extend the deterministic local E2E scenario to cover change-to-requirement-to-service-to-PR-to-CodeLocator-to-test traceability, including complete, missing-evidence, conflict, and multirepo cases.
- Add a project-owned Bitbucket MCP response adapter boundary that consumes locally configured Bitbucket MCP tool results without implementing or modifying the Bitbucket MCP server.
- Use `repo-index.yaml` repository SSH/HTTP URLs as the deterministic source of repository identity for Bitbucket project/repository matching.
- Use the Jira user story key as the primary join key from OpenSpec changes to Bitbucket PRs.
- Treat Bitbucket/Jira linked issues as the authoritative PR connection when exposed by the Bitbucket MCP tools.
- Enforce the team branch convention that the PR source branch name equals the Jira user story ID for a clean implementation match.
- Represent one Jira user story to many PRs across one or more indexed repositories; do not collapse PR evidence to a single selected repository or PR.
- Preserve match confidence and diagnostics for linked issue matches, branch policy mismatches, fallback text matches, missing evidence, out-of-workspace PRs, multiple linked Jira issues, dangling edges, and conflicting facts.
- Keep automated tests deterministic by using fake or mocked MCP responses; tests must not require real Bitbucket, credentials, network access, cloud services, or external API calls.

## Capabilities

### New Capabilities
- `bitbucket-mcp-implementation-evidence`: Normalizes locally configured Bitbucket MCP tool results into deterministic implementation evidence, PR nodes, repository links, change implementation edges, and CodeLocator evidence.

### Modified Capabilities
- `mvp-e2e-scenario`: Extend the scenario to prove full lifecycle traceability, multirepo PR coverage, missing evidence diagnostics, conflict diagnostics, and deterministic fake MCP responses.
- `canonical-ontology`: Add or formalize canonical vocabulary required for implementation and verification evidence while preserving source-owned payload boundaries.
- `workspace-registry`: Require repository URL identity from `repo-index.yaml` to support deterministic Bitbucket project/repository matching.
- `pipeline-runner`: Add orchestration for the implementation evidence stage without moving external MCP behavior into the pipeline core.
- `graph-integrity-validation`: Add validation rules for missing lifecycle links, PR/repository mismatches, branch policy violations, dangling implementation evidence, and conflicting lifecycle facts.
- `local-ekg-query-api`: Expose enough query structure to inspect implementation evidence, PRs, CodeLocators, test evidence, unresolved lifecycle gaps, and conflicts for a change.

## Impact

- Affected code: `src/engineering_kg/ingest/bitbucket.py`, `src/engineering_kg/ontology.py`, `src/engineering_kg/pipeline.py`, `src/engineering_kg/validation.py`, `src/engineering_kg/query.py`, and related tests/fixtures.
- Affected specs: new `bitbucket-mcp-implementation-evidence` spec plus delta specs for the modified capabilities listed above.
- External infrastructure: local Bitbucket MCP tools and Bitbucket/Jira linked issue data are consumed through a project-owned adapter; the Bitbucket MCP server and Jira integration internals remain external.
- Canonical graph and persisted graph data are affected because new PR, implementation evidence, CodeLocator, and verification traceability facts must be serializable, persisted, validated, and queryable.
- No breaking changes are intended for existing registry-only, OpenSpec-only, persistence, or query flows.
