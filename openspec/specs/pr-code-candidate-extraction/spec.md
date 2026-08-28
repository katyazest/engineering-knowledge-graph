# pr-code-candidate-extraction Specification

## Purpose
TBD - created by archiving change extract-pr-code-candidates. Update Purpose after archive.
## Requirements
### Requirement: Explicitly linked merged PR change sets are normalized at the adapter boundary
The system SHALL admit a project-owned normalized input for a merged pull-request change set to candidate extraction only when it identifies an existing `JIRA_STORY` engineering-change graph subject, an explicitly asserted engineering-change-to-PR association, a non-empty PR identity, repository identity, immutable merged revision, and one or more changed-symbol mapping records. Each mapping record SHALL retain its source file and either a complete deterministic symbol identity or a deterministic unresolved/malformed outcome. Provider-specific Bitbucket, Jira, and Graphify response models, source payloads, and URL-like external links SHALL not enter normalized records or the canonical graph. Identity fields SHALL accept a payload-safe opaque URI-shaped stable ID, including `urn:example.org/link-42`, but SHALL reject hierarchical or authority-bearing URL forms, including `https://…`, `custom://…`, and `https:host/path`, and payload-like values.

#### Scenario: Eligible linked change set is normalized
- **WHEN** the adapter receives fixture input for a merged PR explicitly linked to an existing engineering-change subject and containing complete changed-symbol mappings
- **THEN** it returns a deterministic normalized change set with the asserted association, PR/repository/revision identities, and mapping outcomes
- **THEN** it does not retain the provider response payload or a URL-like external link

#### Scenario: Payload-safe opaque URI-shaped identifier is retained as an identifier
- **WHEN** an otherwise eligible fixture supplies `urn:example.org/link-42` in an identity field
- **THEN** normalization retains that identifier and does not treat it as an external link
- **THEN** it does not persist a URL-like external navigation link or source payload

#### Scenario: Hierarchical URL or payload-like identity is rejected
- **WHEN** a fixture supplies `https://host/path`, `custom://host/path`, `https:host/path`, or a payload-like value in a retained identity field
- **THEN** normalization returns or raises a deterministic invalid-identity validation outcome
- **THEN** candidate extraction emits no claim, observation, lifecycle entry, or provenance record for that invalid input

#### Scenario: Ineligible change set is rejected before candidate extraction
- **WHEN** the adapter receives a change set with a missing subject, missing explicit association, blank identity field, non-merged PR state, or malformed mapping record
- **THEN** it returns or raises a deterministic validation outcome identifying the invalid field or eligibility condition
- **THEN** candidate extraction does not emit a claim, observation, lifecycle entry, trusted link, or ordinary graph edge for that input

#### Scenario: Existing non-story subject is rejected during candidate admission
- **WHEN** an otherwise eligible normalized change set identifies an existing `WORKSPACE` or any graph node whose kind is not `JIRA_STORY`
- **THEN** extraction emits no claim, observation, lifecycle entry, or trusted link for that change set
- **THEN** it reports a deterministic ineligible-subject-kind diagnostic

### Requirement: Eligible resolved symbols emit stable observed-provenance candidates
The system SHALL convert every unique, deterministically resolved changed-symbol mapping from an eligible normalized change set into a `CrossGraphLinkClaim` from the explicitly linked engineering-change subject to a complete `CodeLocator`. The claim relation kind SHALL identify an observed PR change rather than implementation semantics. For each emitted claim, the system SHALL create an attributable `CrossGraphLinkEvidence` observation using a stable PR-extraction strategy identifier and a provenance `Evidence` record that identifies the asserted association, PR change set, merged revision, and source mapping identity without retaining external payload bodies. It SHALL create an initial `candidate` lifecycle entry with provenance.

#### Scenario: Resolved mapping produces an auditable candidate
- **WHEN** an eligible linked merged PR change set contains a deterministically resolved symbol with non-empty repository, revision, file, and symbol values
- **THEN** extraction emits one candidate claim whose target has exactly those `CodeLocator` identity values
- **THEN** extraction emits attributable observed-provenance evidence and an initial candidate lifecycle entry linked to the claim

#### Scenario: Equivalent extraction is idempotent
- **WHEN** the same eligible normalized change set is extracted repeatedly or appears more than once in a pipeline input
- **THEN** the merged graph retains one record for each stable claim, observation, provenance evidence, and initial lifecycle identity
- **THEN** serialized candidates and diagnostics have deterministic ordering

### Requirement: Unresolved or ambiguous changed symbols are not guessed
The system SHALL emit a code-link candidate only when the changed-symbol mapping supplies one complete deterministic `CodeLocator` identity. It SHALL not construct a candidate from a changed file alone, a line range, a symbol name without its deterministic identity, multiple ambiguous symbol matches, a branch name, or a mutable PR reference. It SHALL record a deterministic non-emission diagnostic and preserve admissible source provenance for each skipped mapping.

#### Scenario: Changed file without resolved symbol is skipped
- **WHEN** an eligible linked change set identifies a changed file but no deterministic symbol mapping
- **THEN** extraction emits no claim or observation for that file
- **THEN** extraction reports a deterministic unresolved-symbol diagnostic with the source mapping identity and provenance reference

#### Scenario: Ambiguous symbol mapping is skipped
- **WHEN** a changed-symbol mapping has more than one possible symbol target or lacks a complete immutable revision-qualified locator
- **THEN** extraction emits no candidate for the mapping
- **THEN** extraction reports a deterministic ambiguity or incomplete-locator diagnostic without selecting a target

### Requirement: Candidate extraction reports payload-safe admission evidence and outcomes
The reusable extraction result SHALL expose deterministic counts and diagnostics for accepted change sets, emitted candidates, and skipped inputs grouped by admission reason. Each emitted candidate SHALL be traceable through its observation and provenance evidence to the explicit engineering-change/PR association and source mapping identity. Result metadata and graph records SHALL exclude source code, diff bodies, symbol bodies, provider payloads, hierarchical or authority-bearing URL-like external links, credentials, tokens, and OpenLore analysis data. A payload-safe opaque URI-shaped stable identifier, including `urn:example.org/link-42`, is permitted only as an identifier and is not an external navigation link.

#### Scenario: Mixed input has explainable admission results
- **WHEN** extraction receives a deterministic mixture of eligible resolved mappings and skipped ineligible, unresolved, or ambiguous mappings
- **THEN** its result reports stable accepted, emitted, and skipped counts and deterministically sorted diagnostics for every non-emission
- **THEN** every emitted candidate can be traced to its asserted association and source mapping through retained evidence identifiers

#### Scenario: Extraction is local and fixture-testable
- **WHEN** extraction runs with normalized local fixtures while network access is unavailable
- **THEN** it completes without calling Jira, Bitbucket, Graphify, OpenLore, or any external service
