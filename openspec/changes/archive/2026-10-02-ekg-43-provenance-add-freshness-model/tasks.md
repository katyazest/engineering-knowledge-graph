## 1. Checked-revision boundary and assessment model

- [x] 1.1 Add project-owned validated checked-source-revision input and payload-safe freshness result DTOs without changing persisted provenance or stable IDs; verify complete key/revision/offset-aware check instant, equivalent duplicate coalescing, unsafe/missing/naive/conflicting input rejection with safe errors, and deterministic serialization using fixtures.
- [x] 1.2 Implement pure external provenance assessment using logical artifact identity and opaque revision equality, returning match/mismatch/no-check reasons and as-of check instant; verify matching, differing, unrelated, unavailable, check-predates-observation, and old-observation/no-check matrix rows, including changed hash/extractor metadata without revision evidence.
- [x] 1.3 Implement memoized derived-chain assessment and evidence-level independent-support aggregation, with explicit handling of missing/invalid or cyclic references; verify stale/unknown/fresh propagation, two independent chains, repeated runs, and no derived timestamp-based inference.

## 2. Current-evidence guard

- [x] 2.1 Add reusable fail-closed eligibility for explicitly selected support IDs and joint required evidence sets, reusing the shared assessment rather than changing trust/validation policy; verify stale/unknown/missing/invalid support cannot pass, fresh independent support can pass, and fresh observed PR support does not become trusted `IMPLEMENTS` proof.

## 3. Query projections and compatibility

- [x] 3.1 Extend `EngineeringKgQuery` fact and traceability results with additive `evidence_freshness` associations, individual provenance-chain statuses and current-eligibility, plus optional checked revisions; verify old fields/ordering/filters/missing behavior and no-check `unknown` on fixture snapshots.
- [x] 3.2 Extend existing PR-evidence, scenario-test, and cross-graph support projections to use the same evidence-specific assessment and eligibility; verify support references stay distinguishable, stored trust/execution/lifecycle results do not change, and derived-chain reasons and as-of check instants are visible where applicable.
- [x] 3.3 Route invalid checked-input and unresolved-support cases through deterministic safe query errors or fail-closed unknown statuses consistent with validation-required behavior; verify no partial success response, payload leak, source read, or inadvertently eligible support.

## 4. Thin agent-facing tools and documentation

- [x] 4.1 Add optional checked revisions to the four existing FactMCP query tools and forward them only to the local query API; verify omitted inputs remain accepted, no graph-store path enters tool schemas, no wrapper-side comparison/network lookup occurs, and malformed inputs return safe structured errors.
- [x] 4.2 Document the checked-revision caller trust boundary, as-of (not real-time) semantics, the shared current-required guard and its non-goals, and the missing Plane acceptance criteria for named critical readiness workflows; verify examples distinguish old timestamps from proven revision mismatch and fresh support from trusted implementation.

## 5. Persistence boundary and matrix verification

- [x] 5.1 Add fixture-based readback/query regression coverage proving unchanged snapshot codec/version, persisted bytes on read, fact/claim/provenance IDs, and deterministic output for equivalent checks; verify no migration, storage configuration, or external infrastructure change is introduced.
- [x] 5.2 Cover every evidence-freshness verification-matrix row at assessment, guard, query and wrapper boundaries with unit/fixture tests, including existing invalid-graph behavior; verify absence of source/provider payloads and that no live Graphify, Jira/Bitbucket MCP, OpenLore, or LadybugDB service is required.
