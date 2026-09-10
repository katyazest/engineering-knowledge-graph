## MODIFIED Requirements

### Requirement: Explicitly linked merged PR change sets are normalized at the adapter boundary
The system SHALL admit a project-owned normalized input for a merged pull-request change set to candidate extraction only when it constructs complete PR implementation evidence with a payload-safe source-qualified PR identity, an existing canonical `REPOSITORY` node, immutable complete base and head revisions, an explicit PR source reference, complete provenance, and an explicitly asserted source-backed association to one existing `OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, or `JIRA_STORY` intended-change subject. It SHALL retain one or more changed-symbol mapping records, each with its source file and either a complete deterministic symbol identity or a deterministic unresolved/malformed outcome. Provider-specific Bitbucket, Jira, and Graphify response models, source payloads, and URL-like external links SHALL not enter normalized records or the canonical graph. Identity fields SHALL accept a payload-safe opaque URI-shaped stable ID, including `urn:example.org/link-42`, but SHALL reject hierarchical or authority-bearing URL forms, including `https://…`, `custom://…`, and `https:host/path`, and payload-like values.

#### Scenario: Eligible linked change set is normalized
- **WHEN** the adapter receives fixture input for a merged PR explicitly source-linked to an existing OpenSpec change or Jira work item and containing its repository, complete base/head revisions, source references, provenance inputs, and complete changed-symbol mappings
- **THEN** it returns deterministic normalized PR evidence with the asserted association, PR/repository/revision identities, and mapping outcomes
- **THEN** it does not retain the provider response payload or a URL-like external link

#### Scenario: Payload-safe opaque URI-shaped identifier is retained as an identifier
- **WHEN** an otherwise eligible fixture supplies `urn:example.org/link-42` in a retained PR identity or association source-reference field
- **THEN** normalization retains that identifier and does not treat it as an external link
- **THEN** it does not persist a URL-like external navigation link or source payload

#### Scenario: Hierarchical URL or payload-like identity is rejected
- **WHEN** a fixture supplies `https://host/path`, `custom://host/path`, `https:host/path`, or a payload-like value in a retained identity or source-reference field
- **THEN** normalization returns or raises a deterministic invalid-identity validation outcome
- **THEN** candidate extraction emits no PR record, declared association, observed repository relation, claim, observation, lifecycle entry, or provenance record for that invalid input

#### Scenario: Ineligible change set is rejected before candidate extraction
- **WHEN** the adapter receives a change set with a missing PR identity, repository, base/head revision, explicit association, source reference, complete provenance input, merged PR state, or valid mapping record
- **THEN** it returns or raises a deterministic validation outcome identifying the invalid field or eligibility condition
- **THEN** candidate extraction does not emit a PR record, association, claim, observation, lifecycle entry, trusted link, or ordinary graph edge for that input

#### Scenario: Existing non-story subject is rejected during candidate admission
- **WHEN** an otherwise eligible normalized change set identifies an existing `WORKSPACE` or any graph node whose kind is not `OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, or `JIRA_STORY`
- **THEN** extraction emits no PR association, claim, observation, lifecycle entry, or trusted link for that change set
- **THEN** it reports a deterministic ineligible-intended-change-kind diagnostic

### Requirement: Eligible resolved symbols emit stable observed-provenance candidates
The system SHALL convert every unique, deterministically resolved changed-symbol mapping from eligible normalized PR evidence into a `CrossGraphLinkClaim` from the explicitly associated intended-change subject to a complete `CodeLocator` whose repository and revision equal the represented PR repository and head revision. The claim relation kind SHALL identify an observed PR change rather than implementation semantics. For each emitted claim, the system SHALL create an attributable observed `CrossGraphLinkEvidence` using a stable PR-extraction strategy identifier, source mapping identity, canonical PR reference, declared-association reference, and provenance `Evidence` record that identifies the asserted association, PR change set, base/head revision pair, and source mapping identity without retaining external payload bodies. It SHALL create an initial `candidate` lifecycle entry with provenance.

#### Scenario: Resolved mapping produces an auditable candidate
- **WHEN** eligible linked merged PR evidence contains a deterministically resolved symbol with non-empty repository, head revision, file, and symbol values matching that PR
- **THEN** extraction emits one candidate claim whose target has exactly those `CodeLocator` identity values
- **THEN** extraction emits declared-association and observed PR/provenance references plus an initial candidate lifecycle entry linked to the claim

#### Scenario: Equivalent extraction is idempotent
- **WHEN** the same eligible normalized PR evidence is extracted repeatedly or appears more than once in a pipeline input
- **THEN** the merged graph retains one record for each stable PR, association, observed repository relation, claim, observation, provenance evidence, and initial lifecycle identity
- **THEN** serialized candidates and diagnostics have deterministic ordering

## ADDED Requirements

### Requirement: Candidate extraction reports PR-evidence admission outcomes without coverage conclusions
The reusable extraction result SHALL expose deterministic counts and reason-coded diagnostics for admitted PR evidence, declared associations, emitted PR-scoped candidates, and skipped inputs. Each emitted candidate SHALL be traceable through its PR reference, declared association, observation, and provenance evidence to the explicit association and source mapping identity. Result metadata and graph records SHALL exclude source code, diff bodies, symbol bodies, provider payloads, hierarchical or authority-bearing URL-like external links, credentials, tokens, and OpenLore analysis data. It SHALL not report requirement coverage or an implementation conclusion for a PR, changed file, or changed symbol.

#### Scenario: Mixed PR input has explainable but non-implementing admission results
- **WHEN** extraction receives a deterministic mixture of eligible PR evidence and skipped ineligible, unresolved, ambiguous, or scope-inconsistent mappings
- **THEN** its result reports stable admitted, declared, emitted, and skipped counts with deterministically sorted diagnostics for every non-emission
- **THEN** every emitted candidate can be traced to its PR, asserted association, and source mapping through retained evidence identifiers without claiming requirement coverage or trusted implementation
