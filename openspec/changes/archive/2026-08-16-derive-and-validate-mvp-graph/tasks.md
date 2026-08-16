## 1. Derivation Core

- [x] 1.1 Add `engineering_kg.derivation` result models for deterministic derivation status, derived edge counts, skipped or unresolved input counts, diagnostics, and graph counts.
- [x] 1.2 Implement `derive_graph_relationships(snapshot)` so it consumes only a canonical `GraphSnapshot` and returns a canonical graph snapshot plus derivation metadata.
- [x] 1.3 Implement deterministic OpenSpec change-scoped spec to durable spec derivation when source and target spec nodes share the same capability identity.
- [x] 1.4 Preserve non-confident related-spec relationships and prevent repository hints or names from creating implementation mappings.
- [x] 1.5 Add unit tests proving derivation is local-first, deterministic across repeated runs, does not duplicate derived edges, and does not invent missing durable spec nodes.

## 2. Validation Core

- [x] 2.1 Add `engineering_kg.validation` result and diagnostic models with deterministic severity, rule ID, affected object ID, message, severity counts, duplicate counts, and graph counts.
- [x] 2.2 Implement canonical reference validation for broken edge endpoints and missing evidence references.
- [x] 2.3 Implement duplicate identity conflict validation for nodes, edges, and evidence records.
- [x] 2.4 Implement traceability-shape validation for OpenSpec change-to-spec relationships.
- [x] 2.5 Implement warning handling for unresolved non-confident related-spec metadata while keeping required unresolved references as errors.
- [x] 2.6 Add unit tests proving validation diagnostics are complete, sorted deterministically, payload-safe, and stable across repeated runs.

## 3. Pipeline Integration

- [x] 3.1 Extend `PipelineResult` with optional graph derivation and graph integrity validation metadata, preserving existing serialized output when stages are not configured.
- [x] 3.2 Extend pipeline stage execution so `graph-derivation` runs after graph-producing stages and after `ladybugdb-persistence` readback when persistence is configured.
- [x] 3.3 Extend pipeline stage execution so `graph-integrity-validation` runs after derivation when configured, or after the latest prior graph snapshot when derivation is not configured.
- [x] 3.4 Ensure invalid graph integrity validation blocks later query wrapper, projection, wiki, or MCP wrapper stages in the same run.
- [x] 3.5 Add pipeline tests for derivation with and without persistence, validation with and without derivation, empty derivation behavior, invalid validation failure, and deterministic metadata.

## 4. Configuration, Scripts, and Fixtures

- [x] 4.1 Add fixture `repo-index.yaml` variants that configure `graph-derivation`, `graph-integrity-validation`, and both stages together with OpenSpec extraction and persistence.
- [x] 4.2 Keep `scripts/build.py` as a thin wrapper that delegates derivation and validation behavior to `run_pipeline` and reports serialized metadata.
- [x] 4.3 Decide whether `scripts/derive.py` should become a thin derivation wrapper or remain unused for this change, then implement or document that decision.
- [x] 4.4 Add script-level tests proving configured derivation and validation are reported without network access or credentials.

## 5. Verification

- [x] 5.1 Run focused unit tests for derivation, validation, pipeline runner, and script wrappers.
- [x] 5.2 Run the full local test suite.
- [x] 5.3 Run `openspec validate derive-and-validate-mvp-graph --strict`.
