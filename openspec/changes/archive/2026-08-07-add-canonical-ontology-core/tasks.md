## 1. Stable Identity Helpers

- [x] 1.1 Add a canonical ontology module under `src/engineering_kg/` for stable ID and model definitions.
- [x] 1.2 Implement deterministic stable ID generation from object kind and explicit identity parts.
- [x] 1.3 Add tests proving identical identity inputs produce the same ID and different identity inputs produce different IDs.

## 2. Canonical Ontology Models

- [x] 2.1 Implement minimal in-memory models for `CodeLocator`, `Evidence`, `Node`, `Edge`, and `GraphSnapshot`.
- [x] 2.2 Add minimal node and edge kind constants or enums for known MVP artifact families.
- [x] 2.3 Ensure `CodeLocator` serializes only `repository`, `revision`, `file`, and `symbol`.
- [x] 2.4 Add deterministic dict/JSON-compatible serialization for canonical ontology objects.

## 3. Pipeline Integration

- [x] 3.1 Extend `PipelineResult` to include an empty `GraphSnapshot`.
- [x] 3.2 Keep `scripts/build.py` output deterministic after adding the graph snapshot.
- [x] 3.3 Preserve the existing zero configured/executed stages behavior.

## 4. Verification

- [x] 4.1 Add model construction and serialization tests for nodes, edges, evidence, code locators, and graph snapshots.
- [x] 4.2 Update pipeline runner tests to assert the empty graph snapshot is present with zero nodes, zero edges, and zero evidence records.
- [x] 4.3 Run the local test suite and confirm the canonical ontology core passes.

## 5. Confluence Page Identity

- [x] 5.1 Add a `ConfluencePageRef` model that stores only `page_id`.
- [x] 5.2 Allow evidence locators to use `ConfluencePageRef` without fetching or storing page content.
- [x] 5.3 Add tests proving Confluence page reference serialization includes only `page_id` and excludes page content, URLs, credentials, tokens, comments, attachments, and API response data.
- [x] 5.4 Run the local test suite and confirm the ontology update passes.
