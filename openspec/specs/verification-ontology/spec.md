# Verification Ontology

## Purpose

This capability defines source-neutral test/verification evidence model with stable canonical identities, explicit relationship semantics, and promotion-safe verification support.

## Requirements

### Requirement: Source-neutral verification facts have stable canonical identities
The system SHALL represent source-neutral `test-case`, `test-suite`, `test-run`, and `verification-evidence` canonical node kinds. A `test-suite` fact is optional and SHALL be emitted only when a source supplies an explicit suite identity. Each verification fact SHALL have a deterministic node ID derived only from its node kind, a non-empty payload-safe `verification_scope_id`, and its non-empty payload-safe kind-specific opaque key (`test_case_key`, `test_suite_key`, `test_run_key`, or `verification_evidence_key`). Display names, test-framework or CI-vendor labels, provider payloads, local paths, source-code paths or line numbers, timestamps, execution outcome text, and source-artifact locators SHALL NOT participate in the canonical node ID. Each admitted externally sourced verification fact SHALL reference evidence with a complete existing `SourceArtifactIdentity` and first-class external provenance; provider-specific data remains in the adapter boundary and is not canonicalized.

#### Scenario: Equivalent normalized verification fact is stable across sources
- **WHEN** two normalized inputs describe the same `test-case` with the same verification scope and test-case key but differ in display name, framework/CI representation, source locator, or observation time
- **THEN** the system emits one canonical `test-case` identity with its source evidence and provenance references accumulated deterministically
- **THEN** the canonical node ID does not contain or depend on either provider representation

#### Scenario: Incomplete or unsafe verification identity is rejected
- **WHEN** a verification fact has a blank scope or kind-specific key, uses display text or a local/source-code path as that key, or has missing, malformed, or payload-bearing source identity or provenance
- **THEN** admission rejects the input with a deterministic identity or provenance diagnostic
- **THEN** it emits no partial verification node, relationship, cross-graph support, serialized record, persistence record, or query projection

### Requirement: Verification relationship semantics are explicit and provenanced
The verification-specific use of `VERIFIED_BY` SHALL link a verification target to an explicit `test-case` or `test-suite`; `EXECUTED_IN` SHALL link an explicit `test-case` or `test-suite` to a `test-run`; and `VALIDATES` SHALL link `verification-evidence` to the represented test/run fact or to the verification target it evidences. A `test-suite` MAY structurally `CONTAINS` an explicit `test-case`. The system SHALL represent only catalog-conformant verification relationships with complete evidence provenance, SHALL retain no relationship when an endpoint is missing, reversed, unsupported, or lacks complete provenance, and SHALL not infer omitted suite membership, test execution, validation, or verification coverage.

#### Scenario: Explicit verification chain is admitted
- **WHEN** an admitted requirement has a provenanced `VERIFIED_BY` relationship to a test case, that test case has a provenanced `EXECUTED_IN` relationship to a test run, and admitted verification evidence has a provenanced `VALIDATES` relationship to the requirement or one represented member of that chain
- **THEN** the graph retains each directed relationship with deterministic identities and ordering
- **THEN** graph traversal can distinguish the target, test case, run, and evidence facts without provider payloads

#### Scenario: Missing verification links are not inferred
- **WHEN** the graph contains a test case, test run, or verification-evidence fact without an explicit catalog-valid relation to another verification fact or target
- **THEN** the system retains only the represented facts and relationships
- **THEN** it does not manufacture a `VERIFIED_BY`, `EXECUTED_IN`, `VALIDATES`, `CONTAINS`, or coverage relationship

### Requirement: Verification evidence supports only explicit verification promotion
The system SHALL permit an admitted `verification-evidence` node to be cited by a cross-graph support record only for a catalog-valid `VERIFIED_BY` claim. The cited verification evidence SHALL have complete evidence/provenance and a represented `VALIDATES` relationship to that claim's subject; the support record's own provenance, classification, trust disposition, and explicit lifecycle requirements remain independently mandatory. A cited verification-evidence identity SHALL NOT change the claim identity, infer a lifecycle revision, or create a trusted projection by itself. A test/test-code association and verification evidence SHALL NOT be mapped to, treated as, or promoted to an `IMPLEMENTS` assertion; `IMPLEMENTS` remains governed by its existing authoritative-declared support and explicit-lifecycle boundary.

#### Scenario: Verification evidence can support an explicitly trusted verification claim
- **WHEN** a catalog-valid `VERIFIED_BY` claim has a complete classified support record that cites an admitted verification-evidence node validating the claim subject and a separately valid explicit trusted lifecycle revision
- **THEN** the verification evidence is retained as auditable support and the claim is eligible for trusted projection under the existing cross-graph admission rules
- **THEN** the claim retains its original stable identity

#### Scenario: Test evidence cannot prove implementation
- **WHEN** a test-case, test-run, verification-evidence fact, or test-code association is supplied as the sole support for an `IMPLEMENTS` claim or requests an `IMPLEMENTS` mapping
- **THEN** the system rejects the unsupported mapping or leaves the claim non-trusted according to the existing implementation-trust contract
- **THEN** it emits no trusted implementation relationship from that verification input

### Requirement: Verification ontology verification matrix bounds admission testing
The change SHALL document and exercise this verification matrix at model, normalization/admission, merge, persistence/readback, validation, and query boundaries. Cases outside it SHALL be reported as change candidates unless they violate another approved requirement or baseline.

| Input class | Expected admission or projection behavior | Compatibility anchor |
| --- | --- | --- |
| Complete payload-safe scope/key for each verification node kind with complete source-artifact identity and external provenance | Admit with deterministic kind-specific canonical ID and payload-free source references | EKG-48 source-neutral stable identity; fact-provenance baseline |
| Equivalent normalized verification input with changed display/framework/CI representation, locator, or observation time | Coalesce canonical fact; accumulate compatible evidence/provenance; retain canonical ID | EKG-48 framework independence; idempotency baseline |
| Different verification scope, node kind, or kind-specific key | Retain distinct canonical facts | EKG-48 stable identity |
| Blank/unsafe scope or key; display/path/line-number identity; missing or invalid source-artifact identity or provenance | Reject before graph emission or persistence | EKG-48 stable identity/provenance; payload-free baseline |
| Complete explicit `VERIFIED_BY`, `EXECUTED_IN`, `VALIDATES`, or suite `CONTAINS` relation with permitted direction and provenance | Admit in deterministic order | EKG-48 required relations; canonical relationship catalog |
| Reversed, unsupported, dangling, or unprovenanced verification relation | Reject with deterministic diagnostic; do not infer replacement relation | EKG-48 required relations; graph-integrity baseline |
| Cited verification evidence validating a `VERIFIED_BY` claim subject plus separately valid classified support and explicit trusted lifecycle | Retain support; eligible for trusted `VERIFIED_BY` projection without claim-ID change | EKG-48 promotion-safe design; cross-graph lifecycle baseline |
| Verification evidence/test-code association presented as `IMPLEMENTS`, or verification evidence without the required `VALIDATES` binding | Reject unsupported support/mapping or leave non-trusted; never project trusted implementation | EKG-48 promotion-safe design; EKG-41 implementation-trust boundary |
| In-memory graph snapshot with no verification facts | Remains constructible with no verification-specific records | Existing canonical-ontology compatibility baseline |
| Persisted graph at a prior catalog revision | Reject before readback; do not infer or migrate verification records | EKG-48 approved breaking catalog revision; no historical verification migration |

#### Scenario: Verification matrix cases are executable
- **WHEN** automated tests exercise each matrix row at its applicable boundary
- **THEN** each row has the documented admission, coalescing, rejection, retention, or projection outcome
- **THEN** tests verify that test-framework/CI payloads, source content, credentials, URLs, and inferred implementation conclusions are not serialized, persisted, or queryable
