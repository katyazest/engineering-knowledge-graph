## 1. Conflict-aware canonical merge

- [x] 1.1 Add reusable, payload-free same-identity cohort comparison and aggregate conflict diagnostic/error primitives in the ontology layer, preserving `ValueError` compatibility and stable canonical IDs. **Verification:** focused ontology tests prove sorted, input-order-independent conflict descriptors contain only collection/object/reference IDs and exclude competing values/payloads.
- [x] 1.2 Replace ID-map/display-name winner behavior in `GraphSnapshot` merge with cohort evaluation for nodes, edges, evidence, provenance, cross-graph claims/support/lifecycle, and typed PR collections; retain only approved sorted evidence/provenance reference unions. **Verification:** unit tests cover equivalent duplicate idempotency, compatible multi-source support accumulation, conflicting type/value/name/source-artifact/immutable-provenance/support/lifecycle data, no partial merged snapshot, and unchanged canonical IDs.

## 2. Integrity validation and trusted-projection boundary

- [x] 2.1 Reuse cohort evaluation in graph-integrity validation for directly constructed duplicate snapshots, extend validation metadata with deterministic payload-free contributing references, and retain duplicate-count/status semantics. **Verification:** validation tests assert compatible duplicates are valid, conflicting cohorts are invalid with stable rule/collection/reference diagnostics in both input orders, and diagnostics expose no source/provider payload.
- [x] 2.2 Gate trusted cross-graph projection on the conflict-free merge/validation condition without changing EKG-41 classification or lifecycle eligibility. **Verification:** cross-graph tests prove valid declared-authoritative support still projects under existing rules, while it cannot select a generic assertion conflict; observed/inferred support remains retained and unranked.

## 3. Persistence integrity

- [x] 3.1 Route `LadybugDbStore.write_snapshot` and any shared persistence merge helper through the conflict-aware `GraphSnapshot` merge before serialization into ID-keyed storage maps. **Verification:** persistence tests prove a stored valid fact plus a conflicting incoming assertion fails with the safe deterministic diagnostic, does not replace the graph file, and later readback contains only the prior valid state.
- [x] 3.2 Preserve current-format compatibility and idempotency for conflict-free persistence without adding a conflict collection, catalog revision, or data migration. **Verification:** repeated equivalent/compatible writes round-trip to one deterministic record with sorted support references; existing valid current-format fixtures remain readable and malformed/conflicting input is never serialized as a winner.

## 4. Matrix and regression verification

- [x] 4.1 Implement every applicable row of the `conflict-aware-graph-merge` verification matrix across ontology, validation, persistence, and cross-graph tests. **Verification:** test coverage includes compatible and incompatible cohorts, reversed order, authority non-override, independently valid classified-support retention, prior-store preservation, stable IDs, and payload-free diagnostics.
- [x] 4.2 Run the complete local automated test suite and repair affected fixtures/callers that relied on implicit presentation-value selection. **Verification:** all tests pass without live Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, or LLM infrastructure, and no test reintroduces generic source-authority ranking or last-write-wins behavior.
