## 1. Canonical Ontology

- [x] 1.1 Replace retired OpenSpec-prefixed specification, requirement, scenario, and domain relationship vocabulary in `ontology.py` with source-independent canonical node and edge kinds while retaining source-owned change and artifact kinds; verify serialized graph objects use only the revised vocabulary.
- [x] 1.2 Define reusable canonical natural-key and stable-ID helpers for OpenSpec-backed specifications, requirements, and scenarios using repository/capability and canonical parent identities; verify paths, headings, source names, line ranges, and display names do not change canonical IDs.
- [x] 1.3 Update graph snapshot record merging to coalesce compatible evidence IDs deterministically and reject incompatible canonical records rather than overwriting them; add unit tests for idempotent merging, stable ordering, and identity conflicts.
- [x] 1.4 Update canonical ontology tests for canonical domain facts, source-owned OpenSpec entities, deterministic serialization, and OpenSpec evidence without payload leakage.

## 2. OpenSpec Normalization And Derivation

- [x] 2.1 Refactor the OpenSpec extractor to emit canonical specification, requirement, and scenario candidates with OpenSpec evidence while emitting only changes and planning artifacts as source-specific nodes; verify provider-specific fields remain in evidence or locators.
- [x] 2.2 Coalesce durable and change-scoped OpenSpec assertions by canonical natural key, including a change-only capability with no durable file; add fixtures and tests for provenance preservation, conflict rejection, nested capabilities, and repeat-run idempotency.
- [x] 2.3 Replace source-prefixed containment, related-specification, and asserted change-to-specification edges with canonical relationship kinds and update deterministic extraction metadata and tests.
- [x] 2.4 Update graph derivation to consume asserted OpenSpec-change-to-canonical-specification edges and emit deterministic derived traceability with rule ID, input references, `derived: true`, and inherited evidence; test valid, invalid, and duplicate inputs.

## 3. Persistence Migration

- [x] 3.1 Implement in-memory migration of legacy OpenSpec-prefixed domain nodes, relationships, IDs, and derived-edge references to canonical records before persistence readback or write completion; verify evidence is coalesced and endpoints are rewritten.
- [x] 3.2 Add validated, atomic graph-store replacement with a recoverable pre-migration backup and explicit failure handling; verify migration conflicts and write failures leave the original graph recoverable.
- [x] 3.3 Ensure persistence migration is a no-op for an already canonical snapshot and preserves deterministic readback across repeated migration and write cycles; add regression fixtures for legacy and canonical graph files.

## 4. Integrity Validation And Pipeline

- [x] 4.1 Update graph integrity validation to enforce canonical kinds and natural-key consistency, valid evidence references, source-owned OpenSpec change endpoints, and canonical specification traceability targets; test retired vocabulary and incompatible IDs as invalid.
- [x] 4.2 Add ontology migration as a deterministic pipeline stage before persistence readback, derivation, validation, and query-ready output; verify failed migration prevents later graph, projection, wiki, and MCP stages.
- [x] 4.3 Update pipeline result metadata, CLI/script output, and pipeline tests to report migration status, migrated counts, diagnostics, and final canonical graph counts without source payload leakage.

## 5. Query And FactMCP Contracts

- [x] 5.1 Update local query DTOs and filters to return canonical requirement and traceability facts with evidence-based OpenSpec provenance; remove source-prefixed domain-kind response assumptions and test deterministic results.
- [x] 5.2 Update FactMCP requirement and traceability wrappers to delegate the revised canonical DTO contract unchanged; verify tool schemas and responses expose provenance without source payload bodies or reconstructed source-prefixed entities.
- [x] 5.3 Update query, FactMCP, CLI, and fixture expectations that refer to retired OpenSpec-prefixed domain kinds or relationships; verify missing relationships remain explicit and are never inferred.

## 6. End-To-End Verification

- [x] 6.1 Add an end-to-end fixture covering durable and change-scoped OpenSpec evidence, legacy persisted data, migration, derivation, validation, and local query readback; verify migrated and clean-rebuild graphs serialize identically for equivalent input.
- [x] 6.2 Run the focused ontology, extraction, derivation, validation, persistence, pipeline, query, and FactMCP test suites; resolve regressions and verify all tests run without live external infrastructure.
- [x] 6.3 Run the complete project test suite and OpenSpec validation for this change; verify no retired source-prefixed canonical entities or relationships remain in project-owned observable contracts.
