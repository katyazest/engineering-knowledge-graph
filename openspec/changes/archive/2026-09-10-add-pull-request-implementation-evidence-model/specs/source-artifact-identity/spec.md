## ADDED Requirements

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
