## Why

Engineering KG needs OpenSpec intended behavior to become traceable canonical graph facts, not just files that later stages must rediscover ad hoc. This change adds deterministic extraction of OpenSpec changes, specifications, and requirements from the validated OpenSpec store so intended behavior can be linked to sources, implementation evidence, and future derivations while preserving local-first MVP boundaries.

## What Changes

- Add an OpenSpec graph extraction stage that reads from the already validated OpenSpec store source.
- Extract active and archived OpenSpec changes as distinct canonical graph facts with deterministic identities and source evidence.
- Extract durable OpenSpec specifications, optional specification frontmatter, requirements, and scenarios as canonical graph facts.
- Preserve traceability between changes, capabilities/specifications, requirements, scenarios, source files, and archive state.
- Represent manually maintained `related` frontmatter links between specifications as non-confident relationships because the metadata is optional and may be stale or wrong.
- Represent OpenSpec-originated source evidence as local file references and OpenSpec object identities, without storing implementation code, OpenLore analysis details, external-system payloads, credentials, or generated graph state as source content.
- Normalize extracted facts into the existing in-memory canonical graph snapshot so persistence and later derivation stages can consume them through the same graph contract.
- Add pipeline runner support for executing the OpenSpec graph extraction stage after workspace registry and OpenSpec store source validation.
- Preserve deterministic, local-first execution with no network access, API keys, cloud services, OpenLore MCP calls, Jira MCP calls, Bitbucket MCP calls, Confluence calls, compilation, publishing, or semantic/LLM extraction.

## Capabilities

### New Capabilities

- `openspec-graph-extraction`: Extracts OpenSpec changes, specifications, requirements, and scenarios from the validated OpenSpec store into canonical Engineering KG graph facts with deterministic IDs and source evidence.

### Modified Capabilities

- `canonical-ontology`: Add the minimal canonical node, edge, confidence, and evidence vocabulary needed to represent active OpenSpec changes, archived OpenSpec changes, specifications, requirements, scenarios, archive state, optional frontmatter metadata, and source file references.
- `pipeline-runner`: Add execution and reporting for an OpenSpec graph extraction stage after OpenSpec store source validation and before persistence, derivation, validation, or MCP query stages.

## Impact

- Affected specs: new `openspec-graph-extraction`; modified `canonical-ontology` and `pipeline-runner`.
- Affected code will likely include reusable Python OpenSpec readers/parsers, optional YAML frontmatter parsing, canonical graph construction helpers, pipeline stage orchestration, deterministic extraction metadata, fixtures, and focused tests.
- Affected data boundaries: OpenSpec remains the durable source of intended behavior; Engineering KG stores canonical extracted facts and source references as local generated state.
- No breaking changes expected for existing workspace registry, OpenLore source validation, OpenSpec store source validation, or LadybugDB persistence behavior.
