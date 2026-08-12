## 1. Canonical Ontology

- [x] 1.1 Add OpenSpec node kind support for active changes, archived changes, specs, requirements, scenarios, and artifacts.
- [x] 1.2 Add OpenSpec relationship kind support for spec-to-requirement, requirement-to-scenario, change-to-artifact, change-to-spec, and related-spec edges.
- [x] 1.3 Add deterministic relationship confidence serialization so manually maintained related-spec edges can be marked non-confident.
- [x] 1.4 Add OpenSpec source evidence fields for relative file path, artifact type, heading name, and OpenSpec object identity without embedding full source bodies.

## 2. OpenSpec Extraction

- [x] 2.1 Add an OpenSpec graph extraction module that accepts the validated OpenSpec store source result.
- [x] 2.2 Parse durable spec files under the validated `specs` path using local OpenSpec heading rules for `### Requirement:` and `#### Scenario:`.
- [x] 2.3 Parse optional durable spec frontmatter keys `repo`, `created`, `updated`, `title`, and `related` without requiring frontmatter to exist.
- [x] 2.4 Extract active changes from non-archive change directories using the directory name as an opaque stable change identity.
- [x] 2.5 Extract archived changes from archive directories as distinct archived-change facts using archive path and available archive metadata.
- [x] 2.6 Extract change-local spec delta files as active-change-scoped or archive-scoped spec facts without merging them into current durable spec facts.
- [x] 2.7 Create non-confident related-spec edges for uniquely matched `related` frontmatter titles and unresolved reference metadata for ambiguous or missing matches.
- [x] 2.8 Generate deterministic extraction metadata, graph counts, node IDs, edge IDs, and evidence IDs for repeated runs.

## 3. Pipeline Integration

- [x] 3.1 Add `openspec-graph-extraction` as a configured pipeline stage that requires successful `openspec-store-source` validation before reading OpenSpec files.
- [x] 3.2 Merge OpenSpec extraction graph output into the current pipeline `GraphSnapshot` before persistence, derivation, validation, or MCP query stages.
- [x] 3.3 Serialize OpenSpec extraction metadata in `PipelineResult.as_dict()` without full markdown bodies, source code, generated graph records, credentials, tokens, or external API payloads.
- [x] 3.4 Update the script wrapper output to report OpenSpec graph extraction execution and graph counts through the reusable pipeline function.

## 4. Tests and Fixtures

- [x] 4.1 Add fixture OpenSpec stores covering durable specs, active changes, archived changes, change-local delta specs, optional frontmatter, related-spec matches, unresolved related references, and Jira-like change directory names.
- [x] 4.2 Add ontology tests for OpenSpec node kinds, relationship kinds, confidence serialization, and OpenSpec source evidence serialization.
- [x] 4.3 Add extractor tests for durable spec requirement/scenario granularity and rejection of unsupported `## Requirement:` headings.
- [x] 4.4 Add extractor tests for active versus archived change identity and archive-scoped delta spec duplication with current durable specs.
- [x] 4.5 Add extractor tests for optional frontmatter, non-confident related-spec edges, unresolved related references, and deterministic repeated extraction.
- [x] 4.6 Add pipeline runner tests for stage ordering, missing store-source dependency errors, metadata serialization, graph snapshot merging, and script wrapper reporting.

## 5. Validation

- [x] 5.1 Run focused unit tests for ontology, OpenSpec extraction, and pipeline integration.
- [x] 5.2 Run the full project test suite.
- [x] 5.3 Run `openspec validate "extract-openspec-graph"` and resolve any planning artifact issues.
