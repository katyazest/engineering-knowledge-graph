# fact-provenance Specification

## Purpose
TBD - created by archiving change make-provenance-first-class. Update Purpose after archive.
## Requirements
### Requirement: Every admitted external or derived fact has complete first-class provenance
The system SHALL represent provenance as a payload-free immutable record associated with each admitted externally sourced fact and each derived fact it supports. External provenance SHALL retain a valid `SourceArtifactIdentity` (including source identity and revision), observation time, useful content hash, extractor identity, and extractor version. Derived provenance SHALL additionally retain a non-empty derivation-rule identity and references to the input provenance records. Observation time SHALL be an offset-aware ISO 8601 instant; the content hash SHALL be an algorithm-qualified digest of the useful source content or deterministic derived input representation, not that content itself.

#### Scenario: External fact retains explainable observation provenance
- **WHEN** a normalized external adapter emits a valid fact and complete source observation metadata
- **THEN** its graph evidence/provenance exposes the source-artifact identity, observation time, content-hash algorithm and digest, extractor identity, and extractor version
- **THEN** it does not expose the authoritative source body or provider response payload

#### Scenario: Derived fact retains rule and input provenance
- **WHEN** deterministic derivation emits a fact from valid canonical input facts
- **THEN** the result retains its derivation-rule identity and the stable identifiers of its input provenance records
- **THEN** the result remains distinguishable from an externally asserted fact

### Requirement: Provenance identity and conflicts are deterministic
The system SHALL derive a provenance record's stable ID from immutable retained provenance fields, including its source-artifact identity or derivation identity as applicable. Repeated equivalent provenance SHALL coalesce; records with the same provenance ID but different immutable retained fields SHALL be rejected deterministically without selecting a record by ingestion order. Canonical node, edge, and cross-graph claim IDs SHALL NOT change because provenance is added or updated.

#### Scenario: Equivalent provenance is idempotent
- **WHEN** equivalent admitted provenance is merged or persisted repeatedly
- **THEN** one record with the same stable provenance ID and deterministic reference ordering is retained
- **THEN** referenced canonical fact IDs remain unchanged

#### Scenario: Provenance identity collision is rejected
- **WHEN** two provenance records share an ID but disagree on an immutable source, observation, hash, extractor, or derivation field
- **THEN** merge, validation, and persistence reject the input with a deterministic conflict diagnostic

### Requirement: Incomplete, unsafe, and semantically inconsistent provenance is rejected at admission
The system SHALL reject external provenance missing or containing blank/malformed source identity, revision, observation time, content-hash algorithm/digest, extractor identity/version, or derived provenance missing its rule identity or input provenance references. It SHALL reject payload content, credentials, tokens, URLs, raw source text, or provider response data in provenance fields. It SHALL reject a provenance record marked derived without a rule or with external observation-only semantics, and an external observation marked derived. Rejection SHALL emit no partial fact, evidence, provenance, link observation, or persistence record for that input.

#### Scenario: Invalid provenance does not partially enter the graph
- **WHEN** an adapter or derivation supplies a blank extractor version, invalid timestamp, unqualified hash, source body, or missing derivation rule
- **THEN** it receives a deterministic invalid-provenance outcome identifying the violated condition
- **THEN** no partial graph records are emitted

### Requirement: Provenance verification matrix bounds admission testing
The change SHALL verify the following matrix at reusable model, adapter/extractor, derivation, merge, persistence, query, and cross-graph-link boundaries. Cases outside this matrix are change candidates unless they violate another requirement or baseline contract.

| Input class | Expected behavior | Compatibility anchor |
| --- | --- | --- |
| Complete external source identity/revision, valid instant, algorithm-qualified digest, extractor ID/version | Admit and expose payload-free provenance | EKG-40 external explainability |
| Complete derived record with rule ID and valid input provenance references | Admit and preserve derivation chain | EKG-40 derived explainability |
| Repeated equivalent provenance | Deterministically coalesce | Existing idempotency baseline |
| Same provenance ID with conflicting immutable field | Deterministically reject | Existing conflict baseline |
| Missing/blank/malformed timestamp, hash, extractor ID/version, source/revision, rule, or input reference | Reject before graph emission | EKG-40 completeness |
| Payload, credentials, token, URL, source body, or provider response data in provenance | Reject and do not retain it | Existing payload-free boundary |
| Legacy persisted evidence with all required retained provenance fields | Deterministically migrate without changing canonical fact IDs | Persisted compatibility |
| Legacy evidence lacking required provenance fields | Diagnostic/fail; do not fabricate provenance | Persisted compatibility |

#### Scenario: Verification matrix is exercised
- **WHEN** automated tests exercise every matrix input class at its applicable boundary
- **THEN** each case produces the specified admission, preservation, coalescing, migration, or rejection outcome
- **THEN** tests verify that no authoritative source content is serialized

### Requirement: Provenance-associated cross-graph support preserves evidence classification
The system SHALL preserve a cross-graph support record's declared/observed/inferred origin and authoritative/derived status with its complete provenance association without copying source content. A derived status SHALL remain consistent with the referenced provenance chain; an authoritative status SHALL be rejected when the associated provenance does not represent an authoritative external source observation. Provenance completeness alone SHALL NOT establish a support record's trust disposition or implementation proof.

#### Scenario: Derived support remains classified through provenance
- **WHEN** a cross-graph support record with derived status references a complete derived provenance chain
- **THEN** persistence and query retain the derived classification and provenance references
- **THEN** they do not infer trusted implementation from the complete chain
