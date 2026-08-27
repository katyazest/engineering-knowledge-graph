## 1. Canonical cross-graph link contract

- [x] 1.1 Add immutable ontology models, lifecycle-state constants, and stable-ID helpers for cross-graph link claims, attributable observations, and lifecycle entries using complete `CodeLocator` targets. Verify equivalent claims have identical IDs, each locator identity change changes the ID, and missing identity/attribution fields are rejected.
- [x] 1.2 Extend `GraphSnapshot` construction, counts, deterministic dictionary/JSON serialization, and merge semantics with ordered cross-graph claim, observation, and lifecycle collections. Verify compatible observations accumulate, identical input is idempotent, and immutable identity conflicts fail deterministically.
- [x] 1.3 Implement the trusted-cross-graph-link projection from the highest valid lifecycle revision only. Verify candidate, rejected, and superseded claims never appear as trusted semantic links, while a trusted claim retains all supporting observation/provenance references.

## 2. Integrity validation

- [x] 2.1 Extend graph-integrity validation and metadata counts with deterministic diagnostics for duplicate cross-graph records, absent claims, absent provenance evidence, invalid `CodeLocator` targets, unknown states, and unusable/conflicting lifecycle revisions. Verify malformed snapshots are invalid and valid snapshots remain valid without requiring OpenLore or network access.
- [x] 2.2 Add focused validation tests for lifecycle history selection, unsupported lifecycle values, duplicate revision conflicts, and the prohibition on automatic trust promotion from candidate-evidence quantity, strategy identifier, or confidence-like metadata.

## 3. Local persistence compatibility

- [x] 3.1 Extend the LadybugDB-compatible JSON adapter's empty graph shape, snapshot serialization, deserialization, ordering, and merge/readback paths for cross-graph collections. Verify persisted valid records round-trip deterministically and the forbidden-payload scan still rejects OpenLore-owned content.
- [x] 3.2 Add persistence compatibility tests that read an existing pre-change graph JSON with absent cross-graph keys as empty collections, preserve existing node/edge/evidence data, and reject malformed or dangling cross-graph sections instead of dropping them.

## 4. Regression verification

- [x] 4.1 Update ontology, validation, and persistence test fixtures/helpers only as required by the additive snapshot contract; verify current OpenSpec extraction, derivation, query, and pipeline tests construct snapshots without cross-graph data unchanged.
- [x] 4.2 Run the full pytest suite and OpenSpec validation for this change. Verify all tests pass and `openspec validate define-cross-graph-link-evidence-model --strict` reports no artifact errors.
