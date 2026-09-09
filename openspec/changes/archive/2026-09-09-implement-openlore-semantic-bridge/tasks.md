## 1. Compact bridge contract and shared validation

- [x] 1.1 Factor reusable compact repository-relative file, immutable revision, and deterministic symbol-identity validation from PR candidate extraction where it can be shared without changing existing EKG-14 observable candidate behavior; verify current PR-candidate tests retain their existing accepted and rejected outcomes.
- [x] 1.2 Add frozen project-owned semantic-bridge DTOs and serializer allowlists for changed-file requests, implementation-evidence context, per-file outcomes, navigation handoffs, and deterministic diagnostics; define the injected provider protocol without importing an OpenLore provider model; verify serializers reject or omit payload-bearing/unknown values.

## 2. Registry- and evidence-bound resolution

- [x] 2.1 Implement `OpenLoreSemanticBridge` construction from `WorkspaceRegistry` and the provider port, including exact registry repository lookup, request deduplication, and pre-provider repository/revision/evidence admission; select a non-empty federation `index_location` when the repository is included in enabled federation, otherwise select the repository-index registered resolved local path without requiring `include_in_federation` or `index_location`; verify unknown, mismatched, mutable, and applicable-federation-missing-index contexts make no provider call and yield deterministic diagnostics, while federation-disabled and non-federated registered repositories use the fallback route.
- [x] 2.2 Implement strict batch response validation and deterministic changed-file outcome mapping: one exact symbol creates an exact `CodeLocator`; zero results are `unresolved`; multiple results are `ambiguous`; unavailable, malformed, duplicate/conflicting, unsupported, or context-mismatched provider responses are explicit non-resolved outcomes; verify no branch/current-checkout/path-similarity fallback or partial locator is possible.
- [x] 2.3 Add a compact navigation-handoff operation that revalidates a complete locator against the selected registry route and emits only exact locator identity plus a federation-index or repository-index-path routing reference; verify it selects the same federation-optional route as resolution, does not invoke deeper provider analysis, accepts registered non-federated/federation-disabled contexts through the fallback route, and rejects unknown, invalid-federation-route, or mutable context.

## 3. Existing evidence-flow compatibility and boundary preservation

- [x] 3.1 Add an explicit adapter or conversion seam that lets a caller use resolved bridge outcomes with the existing EKG-14 `ChangedSymbolMapping`/candidate-extraction input while preserving the original stable changed-file/evidence identity; verify unresolved, ambiguous, invalid, and provider-failed outcomes cannot create a PR code candidate.
- [x] 3.2 Export the reusable bridge API through the appropriate package boundary and document its provider-port contract at the module API level; verify no pipeline stage, OpenLore index construction, network client, provider credentials, or provider-specific transport dependency is added.
- [x] 3.3 Add regression coverage that bridge calls make no `GraphSnapshot`, evidence, lifecycle, persistence, derivation, or query writes and that a resolved locator alone creates neither a trusted link nor an `IMPLEMENTS` relationship.

## 4. Verification matrix and regression suite

- [x] 4.1 Add local fake-provider and registry/implementation-evidence fixtures covering every row of the `openlore-semantic-bridge` verification matrix, including federation-index and repository-index-path fallback routing, singleton, repeated, invalid-context, zero, multiple, unavailable, malformed/mismatched response, navigation-handoff, and payload-bearing cases; verify stable ordering, selected-route fidelity, and payload-free results without live OpenLore access.
- [x] 4.2 Run focused bridge, workspace OpenLore-source, PR candidate, cross-graph evidence, persistence, query, and full test suites; verify existing snapshots/readback remain compatible and no OpenLore code graph, response body, credentials, or navigation result is serialized or persisted.
