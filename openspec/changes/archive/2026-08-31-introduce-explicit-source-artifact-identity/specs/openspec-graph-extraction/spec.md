## ADDED Requirements

### Requirement: Source evidence excludes full content
The system SHALL serialize source evidence for OpenSpec-originated facts with an explicit source-artifact identity containing OpenSpec source type, authoritative OpenSpec store/repository identity, artifact type, revision/version, and a stable repository-relative locator. It SHALL derive the source-artifact identity without display names, absolute paths, current working directory, headings, line ranges, or full content, and SHALL exclude full requirement bodies, full markdown artifact bodies, implementation source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads.

#### Scenario: OpenSpec source evidence has explicit artifact identity
- **WHEN** extraction serializes evidence for a durable spec, change artifact, requirement, or scenario from a validated OpenSpec store
- **THEN** evidence retains the complete explicit source-artifact identity and source-specific heading/line metadata only as non-identity locator detail
- **THEN** equivalent OpenSpec artifacts extracted repeatedly retain the same source-artifact and evidence IDs regardless of display name or local absolute store path

#### Scenario: Source evidence excludes full content
- **WHEN** extraction serializes source evidence for OpenSpec-originated facts
- **THEN** evidence identifies local source file paths, artifact types, heading names, and OpenSpec object identities as needed
- **THEN** evidence excludes full requirement bodies, full markdown artifact bodies, implementation source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads

## ADDED Requirements

### Requirement: OpenSpec extraction supplies authoritative artifact identity before canonical fact construction
The system SHALL construct and validate explicit OpenSpec source-artifact identity from the validated store source and repository-relative artifact locator before emitting canonical facts or evidence. It SHALL use the validated store repository's resolved Git `HEAD` commit as the OpenSpec artifact `revision_or_version` and SHALL reject extraction when that context cannot supply a required identity component, rather than substituting a change display name or local absolute path. Canonical specification, requirement, scenario, change, node, and edge identifiers SHALL remain source-independent and unchanged by this provenance identity.

#### Scenario: Validated OpenSpec context produces stable provenance
- **WHEN** extraction runs against the same validated OpenSpec source contents and authoritative source context from different local checkout locations
- **THEN** it produces the same canonical fact IDs, source-artifact IDs, evidence IDs, counts, and serialized metadata
- **THEN** repository-relative source locators remain available for source navigation without becoming canonical identity

#### Scenario: Required OpenSpec identity context is unavailable
- **WHEN** validated OpenSpec source context lacks a required authoritative repository/store identity or resolved Git `HEAD` commit
- **THEN** extraction fails with a deterministic source-artifact-identity diagnostic before producing graph facts
- **THEN** it does not fall back to a display name, current working directory, or absolute source path
