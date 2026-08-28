## Why

Plane task `EKG-72` requires Engineering KG to turn explicitly linked engineering-change and merged pull-request change sets into stable, reviewable code-link candidates.  Today the repository has a cross-graph candidate/evidence model but no producer that admits pull-request change evidence without confusing changed symbols with trusted implementation truth.

## What Changes

- Add deterministic, local normalization and extraction of code-link candidates from explicitly linked engineering-change/PR change sets and their changed-symbol records.
- Produce complete stable `CodeLocator` targets only for deterministically resolvable symbols, with attributable observed-provenance evidence and an explicit candidate lifecycle entry.
- Record deterministic admission/skipping diagnostics so every emitted candidate can be explained and unresolved, malformed, unlinked, or ineligible inputs do not create partial candidates.
- Preserve the separation between observed candidates and trusted `IMPLEMENTS` links: this change does not promote, infer, or emit trusted implementation semantics from changed symbols.
- Make the extraction available as a reusable pipeline stage and report deterministic, payload-safe metadata. Admit only `JIRA_STORY` subjects; reject `WORKSPACE` and every other node kind. Never persist source payloads or URL-like external links; accept payload-safe opaque URI-shaped stable IDs (including `urn:example.org/link-42`) while rejecting hierarchical or authority-bearing URL forms.

## Capabilities

### New Capabilities
- `pr-code-candidate-extraction`: Normalize explicitly linked engineering-change/PR change-set inputs and emit explainable, deterministic cross-graph code-link candidates.

### Modified Capabilities
- `cross-graph-link-evidence`: Define the observed-provenance candidate relation and evidence constraints used by the PR extraction producer.
- `pipeline-runner`: Define orchestration and metadata behavior for the optional PR code-candidate extraction stage.

## Impact

- Affected project-owned components: Bitbucket and engineering-change adapter boundaries, normalized change-set and symbol-mapping models, cross-graph candidate construction, pipeline orchestration, graph validation/persistence integration, and unit/integration fixtures.
- Canonical graph data gains candidate claims, observations, and candidate lifecycle records produced from PR evidence; existing stable `CodeLocator` and cross-graph-link contracts are extended but trusted semantic edges remain unchanged.
- External infrastructure is limited to already-normalized Jira/Bitbucket MCP and Graphify-derived symbol inputs supplied to project-owned adapters. No live MCP, Graphify, OpenLore, or Bitbucket implementation/configuration changes are in scope.
- Non-goals: source-code analysis, symbol guessing, fuzzy matching, PR/Jira discovery, OpenLore calls, automated promotion/rejection policy, trusted `IMPLEMENTS` inference from a changed symbol or PR alone, and retaining external navigation links or source payloads. This change does not admit non-`JIRA_STORY` graph nodes as engineering changes or use hierarchical URLs as stable IDs.
