## Why

The ontology currently represents shared domain concepts with OpenSpec-prefixed node kinds, tying their identities and downstream behavior to a single source system. This blocks source expansion and risks duplicating the same Requirement, Specification, Scenario, Service, Repository, Contract, Decision, Test, and WorkItem once Jira, Bitbucket, wiki, or other evidence is ingested.

## What Changes

- Define canonical, source-independent identities and graph vocabulary for domain concepts that can be evidenced by multiple sources.
- Retain source-specific entities only where their semantics are genuinely provider-bound, including OpenSpec changes and change artifacts.
- **BREAKING** replace affected OpenSpec-prefixed canonical node and relationship usage with canonical entities plus provenance that identifies the source evidence.
- Migrate persisted graph data deterministically and preserve graph identity, provenance, derivation, validation, and query behavior across the new ontology.
- Update OpenSpec extraction, derivation, pipeline orchestration, persistence, local queries, and FactMCP responses to use canonical entities without duplicating source-owned payloads.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `canonical-ontology`: Define source-independent domain entities, stable identities, and provenance while retaining truly OpenSpec-specific entities.
- `openspec-graph-extraction`: Emit canonical specification, requirement, and scenario facts with OpenSpec provenance rather than parallel source-prefixed domain types.
- `graph-derivation`: Derive traceability using canonical entity identities while preserving source evidence and deterministic behavior.
- `graph-integrity-validation`: Validate canonical relationship shapes, provenance, and migration-safe identity consistency.
- `ladybugdb-persistence`: Persist, read back, and migrate the revised canonical graph model deterministically.
- `local-ekg-query-api`: Query canonical entities and expose their source provenance without source-specific ontology coupling.
- `ekg-mcp-query-wrappers`: Return canonical query results and provenance through thin FactMCP wrappers.
- `pipeline-runner`: Orchestrate ontology migration and the updated extraction, persistence, derivation, validation, and query-ready pipeline stages.

## Impact

Affected project-owned components include Pydantic canonical schemas, stable ID and provenance models, OpenSpec extraction, persistence adapters and stored graph data, derivation and validation rules, local query DTOs, FactMCP wrappers, pipeline orchestration, and their tests. External infrastructure involved is LadybugDB for storage and the Jira, Bitbucket, Graphify, llmwiki-cli, and MkDocs integration boundaries; this change does not modify those tools' internal implementations or require infrastructure configuration changes.
