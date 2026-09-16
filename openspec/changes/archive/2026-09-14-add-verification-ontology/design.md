## Context

Plane task EKG-48 (source backlog item EKG-25) requires a framework-neutral way to represent tests and verification evidence. The existing canonical graph has generic `Node`, `Edge`, `Evidence`, and `ProvenanceRecord` models, a versioned relationship catalog at revision 3, and a cross-graph candidate/lifecycle model. It already recognizes `VERIFIED_BY`, but it has no test-case, suite, run, or verification-evidence entity kinds. Its cross-graph support records have no link to a represented verification-evidence fact.

The implementation must preserve existing local-first boundaries: adapters normalize provider inputs; canonical records remain payload-free; the persistence adapter is the only store boundary; and trusted cross-graph links require an explicit lifecycle decision. EKG-48 adds no source adapter or execution stage, so real test-management, test-framework, CI, and manual-verification systems remain future adapter boundaries rather than runtime dependencies.

## Goals / Non-Goals

**Goals:**

- Add deterministic, source-neutral test, suite, run, and verification-evidence facts to the canonical graph.
- Make the required verification relationship directions executable and validated.
- Bind verification evidence to a `VERIFIED_BY` cross-graph support record without changing the claim identity or bypassing existing provenance, trust, and lifecycle checks.
- Keep test-code and verification facts distinct from implementation assertions.
- Round-trip the current expanded schema deterministically and expose its represented traceability through the existing local query boundary.

**Non-Goals:**

- Test-framework, CI-vendor, test-management, Jira, Bitbucket, or OpenLore adapters; network calls; test execution; collecting logs; and outcome/coverage computation.
- Persisting test output, reports, source bodies, URLs, credentials, tokens, framework payloads, or provider-specific models.
- Inferring suite membership, execution, validation, test coverage, verification truth, trusted lifecycle revisions, or implementation truth.
- Migrating, backing up, or rolling back persisted graph data from an earlier catalog revision. EKG-48 has no approved historical verification-data migration.
- New CLI, MCP tool, pipeline stage, or public query operation.

## Decisions

### 1. Reuse the generic node/edge graph shape with strongly validated verification natural keys

Add `TEST_CASE`, `TEST_SUITE`, `TEST_RUN`, and `VERIFICATION_EVIDENCE` values to `NodeKind`; retain the existing generic `Node` and `Edge` storage shape rather than adding provider-specific record collections. Introduce a small internal verification-identity helper/factory in `engineering_kg.ontology` that:

- accepts a permitted verification node kind, a payload-safe `verification_scope_id`, and the matching opaque kind-specific key;
- derives the node ID as `stable_id("node", kind, verification_scope_id, kind_specific_key)`;
- emits only `verification_scope_id` and the matching key as identity properties; and
- uses the stable opaque key as `Node.name`, so provider display-name changes cannot form a same-ID `Node` conflict.

The helper rejects blank, path-like, display-name, or payload-bearing identity values using the existing payload-safe identifier rules. Framework/CI labels, timestamps, test output, outcome text, source locator, and source-artifact identity are not stored in the canonical identity properties. A suite is a normal optional node; it is not synthesized when the source does not identify one.

**Why:** The repository already merges `Node` values by stable ID and rejects divergent immutable values. Retaining a display name would cause equivalent source-neutral inputs from different providers to conflict, even though display text must not define identity. A narrow helper gives callers one deterministic contract without adding a provider model.

**Alternatives considered:**

- Store arbitrary verification fields in generic node properties: rejected because natural-key validation, deterministic IDs, and payload safety would be inconsistent across producers.
- Add separate classes for each test framework/CI provider: rejected because it violates the framework-neutral canonical boundary and would force new dependencies.
- Make `test-suite` mandatory: rejected because EKG-48 says it is useful, not universally present.

### 2. Extend the versioned relationship catalog, not ad-hoc edges

Add `EXECUTED_IN` and `VALIDATES` to `EdgeKind`, `RelationshipKind`, the executable catalog, catalog serialization, and the published catalog reference. Add the new verification node kinds to the canonical-kind set used for catalog validation, then advance `CATALOG_REVISION` from 3 to 4.

The catalog will enforce these directed contracts:

```text
TEST_SUITE          --CONTAINS-->    TEST_CASE          (optional grouping)
verification target --VERIFIED_BY--> TEST_CASE|TEST_SUITE|CodeLocator
TEST_CASE|TEST_SUITE --EXECUTED_IN--> TEST_RUN
VERIFICATION_EVIDENCE --VALIDATES--> TEST_CASE|TEST_SUITE|TEST_RUN|verification target
```

The full preserved endpoint sets are defined by the delta spec. `VERIFIED_BY` remains the only verification relationship that can target a complete `CodeLocator`; `VALIDATES` deliberately cannot target code. `IMPLEMENTS` retains its existing source-kind contract and does not gain test kinds. Every regular verification edge must use the established evidence ID and complete first-class provenance validation.

Add generic normalized-verification source mappings only for these verification relations and fail closed for every other claimed mapping. In particular, test/test-code inputs have no `IMPLEMENTS` mapping.

**Why:** Relationship admission is already centralized in the catalog and validation. Extending it preserves directionality, cardinality, provenance, query behavior, and a single documented compatibility revision.

**Alternatives considered:**

- Model relation names only as free-form edge properties: rejected because endpoint direction and implementation-safety could not be centrally enforced.
- Represent test code as `IMPLEMENTS`: rejected because a test relationship verifies behavior; it does not assert a production implementation mapping.
- Add reverse relation inference: rejected by the existing directed-relationship baseline and would turn incomplete source facts into assertions.

### 3. Bind verification evidence to cross-graph support only for `VERIFIED_BY`

Extend `CrossGraphLinkEvidence` and its identity/serialization/deserialization helpers with an optional `verification_evidence_id`. Include this value in the immutable support-record identity when present, so two distinct verification-evidence records cannot be silently coalesced. Do not add it to `CrossGraphLinkClaim` identity.

Admission and validation will require all of the following when the optional field is present:

1. the claim kind is `verified_by`;
2. the reference resolves to a `VERIFICATION_EVIDENCE` node;
3. the referenced node has existing complete source evidence and external provenance;
4. an existing `VALIDATES` edge joins the referenced evidence node to the claim subject; and
5. the cross-graph support record independently has its existing provenance, classification, and trust disposition.

The existing trusted-link projection remains the only promotion boundary. The verification reference makes support auditable and eligible to participate in a `VERIFIED_BY` lifecycle decision; it neither creates a lifecycle revision nor promotes a claim. The existing `IMPLEMENTS` eligibility logic remains strict and an `IMPLEMENTS` support record cannot carry this field.

**Why:** The model needs evidence that is connected to graph facts rather than an opaque annotation, but support provenance and lifecycle intent must remain independent. Restricting the association to `VERIFIED_BY` prevents a test-code reference from entering implementation semantics.

**Alternatives considered:**

- Add verification evidence directly to the cross-graph claim: rejected because a claim can retain multiple support records and its stable identity must not vary with evidence.
- Allow verification evidence on all relation kinds: rejected because EKG-48 only establishes verification promotion and would create unsupported trust semantics for other relationships.
- Automatically trust a `VERIFIED_BY` claim when evidence is present: rejected because it conflicts with the explicit lifecycle/trust baseline.

### 4. Validate at construction, merge, integrity, persistence, and query-required boundaries

The implementation will use the identity helper at construction and extend `GraphSnapshot` merge/reference checks so verification node identity conflicts and dangling support references fail before a merged graph is emitted. `validate_graph_integrity` will add deterministic rule IDs for invalid verification natural keys, endpoint direction, missing evidence/provenance, wrong referenced node kind, absent/mismatched `VALIDATES` edge, and `IMPLEMENTS`-scoped verification references. Diagnostics will name safe graph IDs and rule IDs only.

The generic source-artifact identity and provenance model remains authoritative for externally sourced verification records; no new provenance format is introduced. Verification evidence and cross-graph support retain separate evidence/provenance references because one does not prove the other.

**Why:** Defense in depth matches the existing ontology: direct construction catches malformed values, merge catches reference cohorts, validation covers manually constructed fixtures and readback, and persistence/query-required validation prevents invalid projections.

### 5. Treat revision 4 as a breaking persisted format and retain in-memory empty-graph compatibility

Update persistence maps, orders, and record decoders for the extended support-record field and catalog revision. Current-format snapshots with no verification nodes or support records remain valid because node/edge collections are already generic and the new support field defaults to absent. A persisted revision-3 graph is rejected before readback or write with the existing unsupported-revision style diagnostic; no inferred default, migration, backup, or rewrite is attempted.

**Why:** The approved change explicitly names the catalog/persistence revision as breaking and provides no evidence of historical verification data. Silent migration would need to invent source-neutral verification identities or support bindings.

### 6. Reuse existing traceability query projections; add fields, not a new query surface

`EngineeringKgQuery.get_traceability` already projects adjacent catalog-valid semantic edges and cross-graph support for a known subject. Update its cross-graph serialization to return an admitted `verification_evidence_id`, and ensure existing node/edge projection sanitization handles the four new kinds through the existing generic paths. Querying a verification node or a verification target will therefore expose its represented directed relation IDs, provenance, lifecycle, and trusted-projection result without a new public method, CLI command, or MCP wrapper.

**Why:** This meets the required query observability while keeping the public surface minimal and local-first. It also avoids inventing filters or aggregation semantics not specified by EKG-48.

## Affected Components and Data Flow

```text
future provider/manual input
  -> future adapter normalizes scope + opaque key + SourceArtifactIdentity
  -> verification identity helper / Node + Evidence + ProvenanceRecord
  -> catalog-valid verification Edge(s)
  -> GraphSnapshot merge and integrity validation
  -> persistence revision 4 read/write
  -> local get_traceability projection

verification evidence bound to a cross-graph VERIFIED_BY claim
  -> CrossGraphLinkEvidence(verification_evidence_id)
  -> reference and VALIDATES-subject validation
  -> existing explicit lifecycle/trust projection
  -> trusted VERIFIED_BY only when otherwise eligible
```

No production source adapter is introduced by this change. Unit tests construct normalized, payload-safe fixtures directly and do not require a live test framework, CI service, database, or network connection.

## Risks / Trade-offs

- **[Identity keys are unavailable or unstable in a future source]** → Reject the record rather than deriving an ID from display text, a filesystem path, or a timestamp; a future adapter/change must establish a stable source-neutral key strategy.
- **[A source emits large logs or vendor payloads]** → Retain only the existing source-artifact identity and provenance; use existing forbidden-field/sanitization guards and test that payloads do not cross serialization, persistence, or query boundaries.
- **[Users mistake test-code evidence for implementation evidence]** → Catalog endpoint contracts, support binding restrictions, explicit lifecycle checks, and regression tests forbid `IMPLEMENTS` promotion from verification data.
- **[Catalog revision prevents reading an existing local store]** → This is the approved breaking behavior. The greenfield baseline has no approved historical verification migration; retain the old runtime/store until a separately approved migration exists.
- **[Outcome and coverage semantics are desired later]** → EKG-48 deliberately models evidence identity/provenance and relationships, not pass/fail or coverage interpretation; introduce those semantics only with a future explicit requirement and trust policy.
- **[Additional integrity scans add cost]** → Verification checks are deterministic in-memory ID/edge lookups and scans comparable to current cross-graph validation; no network or source read is added.

## Migration Plan

1. Implement and unit-test the revision-4 canonical model, catalog, validation, persistence codec, published catalog reference, and query projection as one coherent change.
2. New or reinitialized stores write `catalog_revision: "4"`; valid snapshots without verification data remain representable.
3. Do not migrate or overwrite a revision-3 store. Readback fails before data is exposed or replaced.
4. If deployment must be reverted, restore the prior application version before attempting to read a revision-3 store. There is no automated data rollback because EKG-48 performs no data migration or write conversion.

## Open Questions

None for the EKG-48 scope. Test outcome/coverage semantics and source-adapter priorities are intentionally excluded rather than implicit decisions; they require a future approved change.
