## Why

The MVP pipeline now starts, but later stages still lack a shared canonical vocabulary for engineering graph data. This change adds the smallest in-memory ontology core so service registry, extractors, normalization, persistence, derivation, and validation can all produce and consume the same deterministic objects.

## What Changes

- Add minimal canonical ontology models for graph nodes, graph edges, evidence, code locators, and graph snapshots.
- Add a minimal Confluence page identity/reference to the ontology schema for linking evidence or document-originated graph facts to a source page ID.
- Add deterministic stable ID generation for canonical graph objects.
- Add JSON/dict serialization for model tests and future persistence/adapters.
- Extend the bootstrap pipeline result with an empty canonical graph snapshot.
- Keep the ontology purely local and in-memory.
- Keep this change free of LadybugDB persistence, registry YAML loading, OpenSpec parsing, OpenLore MCP calls, Jira/Bitbucket adapters, semantic extraction, cloud services, API keys, publishing, and graph derivation rules.

## Capabilities

### New Capabilities
- `canonical-ontology`: Defines the minimal in-memory Engineering KG model vocabulary, stable IDs, code locators, Confluence page references, evidence, and graph snapshot serialization.

### Modified Capabilities
- `pipeline-runner`: Pipeline results include an empty canonical graph snapshot while preserving the local-first bootstrap behavior.

## Impact

- Affects `src/engineering_kg/`, especially schema/model modules and the pipeline result contract.
- Affects tests for model serialization, stable IDs, CodeLocator scope, Confluence page ID scope, and pipeline bootstrap output.
- Affects the existing `pipeline-runner` specification because the empty result/status now includes an empty canonical graph container.
- Does not affect LadybugDB storage, OpenLore indexes, external enterprise systems, MCP wrappers, registry loading, wiki/MkDocs/llmwiki-cli/dotMD, semantic extraction, or cloud LLM integrations.
