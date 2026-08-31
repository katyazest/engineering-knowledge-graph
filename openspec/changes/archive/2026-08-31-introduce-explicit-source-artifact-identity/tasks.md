## 1. Source-context resolution

- [x] 1.1 Extend validated OpenSpec source context to resolve and expose the store repository's Git `HEAD` commit as `revision_or_version`, preserving the existing dirty-worktree warning behavior. **Verification:** fixture tests show a non-empty commit is propagated without display-name, absolute-path, or source-content fallback, and unavailable Git revision context fails deterministically.

## 2. Canonical source-artifact model

- [x] 2.1 Add the reusable immutable source-artifact identity model, field validators, payload-safe locator checks, and field-delimited stable-ID generation in the canonical ontology. **Verification:** unit fixtures prove equivalent five-field identities are stable, each differing component is distinct, and incomplete/unsafe values are rejected deterministically.
- [x] 2.2 Refactor evidence and source-specific locator serialization to carry the shared identity plus non-identity navigation detail while preserving canonical node and edge ID generation. **Verification:** ontology serialization fixtures show heading/line metadata is retained but does not change source-artifact or canonical fact IDs.

## 3. Producer and normalization boundaries

- [x] 3.1 Update OpenSpec extraction to construct the resolved-Git-`HEAD` revision-qualified identity before canonical fact/evidence emission. **Verification:** local fixtures extracted from distinct checkout roots yield identical canonical, source-artifact, and evidence IDs; missing required context yields no graph output and a deterministic diagnostic.
- [x] 3.2 Add shared normalized-adapter entry points or contracts for future Jira, Bitbucket, and Graphify producers so they accept/emit the common source-artifact identity without provider payload leakage. **Verification:** fixture-only tests admit complete payload-safe records and reject missing fields, display-name identity, absolute paths, navigation URLs, payloads, credentials, and tokens before graph emission.

## 4. Merge, validation, and persistence

- [x] 4.1 Extend graph merge and integrity validation to recompute/validate source-artifact IDs, coalesce compatible records in deterministic order, and reject same-ID immutable conflicts. **Verification:** tests cover repeated equivalent inputs, every distinct identity component, conflict rejection independent of input order, and the full verification matrix.
- [x] 4.2 Extend LadybugDB-compatible persistence serialization and readback for the identity model and implement guarded legacy-evidence migration with backup and deterministic diagnostics for insufficient data. **Verification:** tests cover round-trip idempotency, compatible migration preserving canonical node/edge IDs, backup creation, and ambiguous legacy rejection without path/name inference.
- [x] 4.3 Ensure pipeline result metadata and any evidence-exposing query DTOs serialize only payload-safe identity/navigation fields and do not expose source content. **Verification:** pipeline/query fixtures exclude bodies, provider payloads, credentials, tokens, and navigation URLs while preserving source-artifact traceability.

## 5. End-to-end verification and cleanup

- [x] 5.1 Add deterministic extraction-to-persistence integration fixtures covering all rows of the source-artifact identity verification matrix, repeated runs, and changed authoritative revision/version. **Verification:** repeated unchanged runs have identical serialized graphs/counts; changed revision/version is distinct; invalid inputs create no partial graph records.
- [x] 5.2 Update affected documentation and fixture schemas to describe the source-artifact contract, legacy migration diagnostic, and Git-`HEAD` OpenSpec version policy; remove obsolete provider-specific identity assumptions. **Verification:** documented examples use all five fields and no production module relies on display names or incidental absolute paths for authoritative artifact identity. If there is no permission for the `docs/**`, provide the exact path to the denied file and the exact error.
