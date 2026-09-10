# source-artifact-identity Specification

## Purpose
TBD - created by archiving change introduce-explicit-source-artifact-identity. Update Purpose after archive.
## Requirements
### Requirement: Authoritative source artifacts have an explicit deterministic identity
The system SHALL represent every authoritative source artifact admitted into extraction, adapter-normalized output, graph evidence, or persistence with a source-artifact identity containing non-empty `source_type`, `source_identity`, `artifact_type`, `revision_or_version`, and `stable_locator` fields. The stable source-artifact ID SHALL be derived only from those five fields using deterministic, field-delimited serialization. Display names, local absolute paths, process working directory, line ranges, heading names, timestamps, and source content SHALL NOT participate in that ID.

#### Scenario: Equivalent authoritative artifact has one identity across boundaries
- **WHEN** an extractor or adapter supplies equivalent values for all five source-artifact identity fields in separate runs or pipeline boundaries
- **THEN** each normalized record and persisted evidence record uses the same source-artifact ID
- **THEN** the graph retains one compatible source-artifact/evidence identity with deterministically ordered references

#### Scenario: Distinct identity component prevents conflation
- **WHEN** two admitted artifacts differ in source type, source identity, artifact type, revision/version, or stable locator
- **THEN** they receive different source-artifact IDs
- **THEN** the system does not deduplicate them solely because they have the same display name or local path suffix

### Requirement: Source-artifact identity admission is complete and payload-safe
The system SHALL reject an artifact record before graph emission or persistence when any required source-artifact identity field is missing, blank, malformed for its declared field, or contains source payload content, credentials, tokens, or an external navigation URL. Rejection SHALL produce a deterministic validation outcome naming the invalid field or condition and SHALL emit no partial authoritative-artifact record or evidence for that input.

#### Scenario: Complete identity is admitted without source content
- **WHEN** a normalized artifact supplies all required identity fields using payload-safe identifier and locator values
- **THEN** the system admits the artifact and retains only the identity fields and allowed provenance metadata
- **THEN** it does not retain the source body or provider response payload

#### Scenario: Incomplete or unsafe identity is rejected
- **WHEN** a normalized artifact has a blank revision/version, an incidental absolute path as its stable locator, a display name substituted for source identity, or a payload, credential, token, or navigation URL in an identity field
- **THEN** the system returns or raises a deterministic invalid-source-artifact-identity outcome
- **THEN** no node, edge, evidence, or persisted record is emitted for that invalid artifact

### Requirement: Source-artifact conflicts and persisted compatibility are deterministic
The system SHALL coalesce identical source-artifact records during graph merge and persistence readback, and SHALL reject records with the same stable source-artifact ID and conflicting retained identity or provenance values. It SHALL read existing persisted evidence that lacks explicit source-artifact identity without silently fabricating identity from a display name or incidental path; it SHALL either deterministically migrate it from sufficient retained authoritative fields or report a deterministic migration/compatibility diagnostic before accepting the snapshot.

#### Scenario: Identical artifacts remain idempotent through persistence
- **WHEN** the same valid source artifact is extracted and persisted more than once
- **THEN** readback contains one compatible source-artifact/evidence record and stable serialized ordering
- **THEN** repeated persistence produces the same graph identity and counts

#### Scenario: Identity collision is rejected
- **WHEN** two records have the same source-artifact ID but different retained identity or provenance values
- **THEN** merge or persistence readback fails with a deterministic conflict diagnostic
- **THEN** it does not select one record based on ingestion order

#### Scenario: Legacy evidence cannot be identified safely
- **WHEN** a persisted legacy evidence record lacks explicit source-artifact identity and does not retain sufficient authoritative fields for deterministic migration
- **THEN** readback reports a deterministic compatibility diagnostic or fails with a deterministic integrity error
- **THEN** it does not derive identity from a display name, absolute path, or current filesystem layout

### Requirement: Source-artifact identity verification matrix bounds admission testing
The change SHALL verify the following matrix at reusable model, adapter/extractor, merge, and persistence boundaries. Cases outside this matrix are change candidates unless they violate another requirement or baseline contract.

| Input class | Expected behavior | Compatibility anchor |
| --- | --- | --- |
| Five complete payload-safe authoritative fields | Admit; derive stable identity; retain fields | Explicit source-artifact identity |
| Repeated equivalent artifact | Coalesce deterministically | Idempotent persistence |
| Different source type, source identity, artifact type, revision/version, or locator | Keep distinct | Explicit source-artifact identity |
| Blank/missing required field, display-name identity, incidental absolute path, payload/credential/token/navigation URL | Reject before graph emission | Payload-safe admission |
| Same derived ID with conflicting retained values | Reject deterministically | Conflict handling |
| Legacy evidence with sufficient retained authoritative fields | Deterministically migrate and preserve canonical IDs | Persisted compatibility |
| Legacy evidence without sufficient authoritative fields | Diagnostic/fail; do not invent identity | Persisted compatibility |

#### Scenario: Verification matrix is exercised
- **WHEN** automated tests exercise each input class in the source-artifact identity verification matrix
- **THEN** each case produces the matrix's specified admission, deduplication, migration, or rejection outcome
- **THEN** tests verify that canonical node and edge IDs remain unchanged by source-artifact provenance identity

### Requirement: Source-artifact identity anchors external provenance
The system SHALL use the existing complete `SourceArtifactIdentity` as the authoritative source identity and revision component of every external provenance record. It SHALL preserve the identity unchanged across normalization, evidence association, merge, persistence, queries, and cross-graph linking; navigation detail remains non-authoritative and SHALL NOT substitute for provenance fields.

#### Scenario: Source identity remains stable in provenance
- **WHEN** one authoritative artifact supports facts across multiple graph boundaries
- **THEN** every associated external provenance record references the same validated source-artifact ID and retained revision
- **THEN** display names, paths, line ranges, and navigation details do not replace it

### Requirement: Pull-request source artifacts retain revision-bounded references without becoming URLs
For admitted PR implementation evidence, the system SHALL construct a complete `SourceArtifactIdentity` for the provider-normalized PR source with a payload-safe source-qualified PR locator and the immutable PR head revision as `revision_or_version`. It SHALL retain the existing repository reference and immutable base/head revision pair only as validated PR evidence/navigation data and SHALL retain the explicit association source reference separately from the PR artifact identity. Provider navigation URLs, raw PR payloads, titles, descriptions, comments, and diffs SHALL NOT substitute for those fields or be retained.

#### Scenario: PR source identity and navigation data agree with the evidence record
- **WHEN** a complete PR implementation-evidence record is normalized
- **THEN** its source-artifact identity is deterministic and revision-bounded by the retained head revision
- **THEN** its payload-safe source references and base/head revisions remain queryable only as represented identity-level data

#### Scenario: URL or source payload cannot stand in for a PR source reference
- **WHEN** a PR source identity, locator, navigation field, or explicit association source reference contains a provider URL, source body, diff, title/description payload, credential, or token
- **THEN** source-artifact admission rejects the PR evidence deterministically
- **THEN** it emits no source-artifact evidence, provenance, PR relation, or cross-graph candidate

