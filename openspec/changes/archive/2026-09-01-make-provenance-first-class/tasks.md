## 1. Provenance schema and admission boundary

- [x] 1.1 Add the immutable first-class provenance model, stable field-delimited ID generation, deterministic serialization, and associations to evidence/graph snapshots; verify canonical node, edge, source-artifact, and cross-graph-claim IDs are unchanged.
- [x] 1.2 Implement reusable validation for external and derived provenance: source/revision, offset-aware timestamp, algorithm-qualified SHA-256 digest, extractor ID/version, derivation rule/input references, and payload-safe constraints; verify deterministic field-specific failures and no partial admission.
- [x] 1.3 Add model tests for all approved/rejected fact-provenance verification-matrix classes, equivalent coalescing, identity conflicts, deterministic order, and absence of source/provider content from serialization.

## 2. Producers and derivation

- [x] 2.1 Update project-owned external extractor/adapter normalization contracts (including OpenSpec and PR/Graphify candidate paths) to construct complete external provenance before graph emission, hash only their defined useful normalized representation, and discard source/provider payloads; verify fixtures require no live service.
- [x] 2.2 Update deterministic graph derivation to create derived provenance with the rule ID, deterministic derived-input hash, and sorted input provenance references; reject derivation output with missing provenance inputs and verify asserted-versus-derived distinction.
- [x] 2.3 Classify existing fixture/review/internal-generated evidence explicitly so it is neither mislabeled as complete external provenance nor silently promoted to an external fact; verify existing permitted internal behavior remains payload-free.

## 3. Graph integrity and cross-graph behavior

- [x] 3.1 Extend graph merge and integrity validation for provenance IDs, immutable conflicts, evidence/fact associations, external/derived semantic consistency, and dangling derived-input references; verify deterministic diagnostics and invalid status.
- [x] 3.2 Update cross-graph candidate observation and lifecycle validation/merge behavior to require resolvable complete supporting provenance and retain explanation chains by reference; verify no claim, observation, or lifecycle record copies source content or code intelligence.
- [x] 3.3 Add integration fixtures covering external fact → derived edge → cross-graph observation/lifecycle provenance traversal, duplicate merge, conflict rejection, and unchanged cross-graph claim/trust semantics.

## 4. Persistence and compatibility

- [x] 4.1 Extend LadybugDB-compatible snapshot serialization and readback for deterministic provenance storage, association references, stable ordering, and integrity validation before write/read exposure.
- [x] 4.2 Implement guarded atomic migration of legacy evidence only when all required provenance fields are retained; rewrite affected references together, create/retain backup, and fail diagnostically without fabrication when fields are absent.
- [x] 4.3 Add persistence tests for first write/readback, repeated writes, compatible migration, incomplete legacy rejection, conflict rollback/backup, payload exclusion, and stable canonical fact IDs.

## 5. Query projection and end-to-end verification

- [x] 5.1 Extend local query DTOs and traceability results to return deterministic payload-free provenance records and input chains for represented facts, edges, and cross-graph support; preserve existing query behavior for facts without applicable external/derived provenance.
- [x] 5.2 Add query and wrapper-facing tests for external and derived explanations, deterministic ordering, absent/dangling provenance errors, and exclusion of source bodies, payloads, credentials, tokens, URLs, and code intelligence.
- [x] 5.3 Run the complete test suite and a fixture-only pipeline/readback/query scenario; verify every EKG-40 verification-matrix row at its applicable boundary and record no network or external-infrastructure dependency.
