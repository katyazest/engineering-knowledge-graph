## Why

Plane task `a5987bd4-215c-4a3e-995e-35fe8bb3f6b9` requires authoritative source artifacts to have stable, deterministic identities and deduplication across extraction, adapters, and persistence. Current provenance uses source-specific locator shapes whose identity can depend on display names or incidental local paths, preventing one uniform, durable source-artifact contract.

## What Changes

- Introduce a source-artifact identity and locator contract that retains source type, authoritative source identity, artifact type, revision/version, and stable locator independently of display names and incidental paths.
- Require extractors and external-source adapters to construct and propagate the contract before canonical graph facts are created or persisted.
- Deduplicate compatible source artifacts and their evidence deterministically across repeated ingestion and persistence; reject conflicting records for the same source-artifact identity.
- Preserve existing canonical fact IDs: source-artifact identity is provenance identity and does not become canonical domain identity.
- Define validation, persistence compatibility, and migration behavior for existing persisted evidence that lacks the explicit identity fields.

## Capabilities

### New Capabilities
- `source-artifact-identity`: Define the source-agnostic authoritative-artifact identity, validation, stable locator, deterministic evidence identity, and deduplication behavior.

### Modified Capabilities
- `openspec-graph-extraction`: Require OpenSpec extraction to emit explicit source-artifact identity and locator provenance without changing canonical fact identities.

## Impact

- Affected project-owned components: canonical ontology and provenance models, OpenSpec extractor, future Jira/Bitbucket/Graphify adapter boundary contracts, graph merge and integrity validation, local LadybugDB-compatible persistence serialization/readback and migration, pipeline metadata, and fixture-based tests.
- Canonical schemas and persisted evidence records are affected; canonical node and edge identity contracts remain compatible.
- External infrastructure remains unchanged: Graphify, Jira MCP, Bitbucket MCP, and LadybugDB are sources or persistence targets only. No live-service calls or changes to their internal implementations are in scope.
- Non-goals: defining provider payload schemas, resolving sources by display name, using filesystem location as a source identity, source-content hashing, changing canonical domain IDs, semantic inference, or ingesting source bodies, credentials, tokens, or external API payloads.
