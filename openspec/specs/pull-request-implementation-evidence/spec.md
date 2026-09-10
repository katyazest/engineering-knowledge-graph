# pull-request-implementation-evidence Specification

## Purpose
TBD - created by archiving change add-pull-request-implementation-evidence-model. Update Purpose after archive.
## Requirements
### Requirement: Merged pull-request evidence has stable revision-bounded identity and provenance
The system SHALL admit a pull request as implementation evidence only when normalized input supplies a payload-safe source-qualified PR identity, an existing canonical `REPOSITORY` identifier, immutable complete base and head Git revisions, an explicit PR source reference, and complete first-class external provenance. The pull-request identity SHALL remain stable across equivalent runs and SHALL NOT depend on title, branch name, display URL, source content, changed paths, mappings, or observation order. The retained PR evidence SHALL identify the repository and both revisions; its external source-artifact identity SHALL be revision-bounded by the head revision. Only merged pull requests are eligible to provide implementation evidence.

#### Scenario: Complete merged PR evidence is admitted
- **WHEN** a normalized merged PR supplies one payload-safe source-qualified identity, an existing repository, complete immutable base and head revisions, an explicit PR source reference, and complete external provenance
- **THEN** the system emits one deterministic pull-request evidence identity with those repository and revision values
- **THEN** repeated equivalent input coalesces without changing the PR identity, source-artifact identity, or provenance reference

#### Scenario: Incomplete or mutable PR evidence is rejected without a partial graph record
- **WHEN** a proposed PR evidence record has a missing repository, source reference, base revision, or head revision; an unknown repository; a branch, tag, abbreviated commit, or other mutable revision; a payload-bearing identity; or missing complete provenance
- **THEN** admission returns a deterministic reason-coded validation outcome
- **THEN** it emits no PR node, relationship, source-artifact evidence, provenance, cross-graph observation, lifecycle record, or persisted record for that input

### Requirement: Explicit PR-to-intended-change association is declared and endpoint-bounded
The system SHALL associate a PR with an intended change only through an explicit source-backed association that names exactly one admitted PR and exactly one existing `OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, or `JIRA_STORY` work-item node. The association SHALL retain its payload-safe declared source reference and complete provenance, and SHALL materialize the catalog-valid directed `PULL_REQUEST REFERENCES intended-change` relation as `declared`. The system SHALL also represent the PR's `PULL_REQUEST TOUCHES REPOSITORY` relation as `observed`, using the admitted PR's repository identity and complete provenance. It SHALL not infer either relation from issue-like tokens, PR title or description text, branch names, commits, repository names, changed files, or changed symbols.

#### Scenario: Explicit source-backed association is represented
- **WHEN** an admitted PR has an explicit source-backed association to an existing active OpenSpec change, archived OpenSpec change, or Jira work item
- **THEN** the graph retains the declared `REFERENCES` relation to that exact intended-change node and the observed `TOUCHES` relation to that exact repository node
- **THEN** queryable relation evidence identifies the represented declared or observed origin and its provenance references without source payloads

#### Scenario: Unsupported or inferred association is not represented
- **WHEN** an association omits its source reference, references a missing PR or intended-change node, targets another node kind, or is derived only from coincident identifiers or source content
- **THEN** the system rejects or deterministically skips the association with a reason-coded outcome
- **THEN** it emits neither the declared association nor observed candidate evidence scoped by it

### Requirement: PR-scoped code observations narrow candidates without asserting implementation coverage
The system SHALL create a PR-scoped cross-graph code candidate only from a declared PR-to-intended-change association and a deterministically resolved changed-symbol observation for that PR. The candidate SHALL be an observed, untrusted `TOUCHES` claim from the associated intended-change node to a complete `CodeLocator`; the locator repository and revision SHALL equal the admitted PR repository and head revision, and its support SHALL retain the canonical PR reference and complete provenance. The association narrows observations to that intended-change/PR/repository/revision scope only. It SHALL NOT create an `IMPLEMENTS` relation, trusted implementation projection, requirement-to-file/symbol relation, or assertion that every changed file or symbol implements the intended change or any requirement contained by it.

#### Scenario: Resolved PR mapping creates a scoped observed candidate
- **WHEN** one declared association has a resolved changed-symbol observation with a complete locator at that PR's repository and head revision
- **THEN** the system records one observed, untrusted candidate tied to that PR and intended-change scope
- **THEN** the candidate remains distinguishable from both the declared association and trusted implementation truth

#### Scenario: PR scope does not fan out to requirements or implementation claims
- **WHEN** an associated PR contains multiple changed files or symbols and the associated OpenSpec change contains one or more requirements
- **THEN** the graph records only the individually resolved observed candidates supplied for that PR and change scope
- **THEN** it does not derive an `IMPLEMENTS` relation or a requirement-to-file/symbol claim from the association, changed-file set, symbol count, PR merge status, or evidence count

#### Scenario: Candidate with inconsistent PR scope is rejected
- **WHEN** a proposed PR-scoped observation references another PR, repository, or revision, has no complete resolved symbol locator, or has no declared association to the claim subject
- **THEN** the system reports a deterministic non-admission outcome for that observation
- **THEN** it emits no partial claim, observation, lifecycle entry, or trusted projection

### Requirement: PR implementation-evidence verification matrix bounds admission testing
The change SHALL document and exercise this verification matrix at normalized-adapter, ontology, relationship, cross-graph, validation, persistence/readback, query, and pipeline boundaries. Cases outside this matrix SHALL be reported as change candidates unless they violate another approved requirement or applicable baseline.

| Input class | Expected admission or projection behavior | Compatibility anchor |
| --- | --- | --- |
| Merged PR with payload-safe source-qualified identity, existing repository, immutable base/head revisions, explicit source reference, complete provenance, and explicit intended-change association | Admit deterministic PR evidence; retain declared PR-to-change and observed PR-to-repository relations | EKG-44 PR identity, revision, source-reference, and provenance scope |
| Same complete PR evidence and association repeated | Coalesce identities and relations deterministically | Existing idempotency and provenance baselines |
| Missing/unknown repository or intended-change endpoint; missing source reference/provenance; blank or payload-bearing identity | Reject before graph emission | EKG-44 explicit evidence and payload-free boundaries |
| Branch, tag, abbreviated, or otherwise mutable/malformed base or head revision | Reject before graph emission | EKG-44 revision-bounded evidence; immutable-revision baseline |
| Association inferred from names, title, branch, commits, files, or symbols | Do not emit declared association or scoped candidate | EKG-44 explicit association boundary |
| Resolved symbol locator whose repository/head revision equals the admitted PR and whose subject has a declared association | Admit one observed untrusted `TOUCHES` candidate with PR and provenance references | EKG-44 candidate-scope rule; EKG-41 observed-evidence boundary |
| Unresolved symbol, or locator/PR/association repository or revision mismatch | Deterministic non-admission; no partial candidate | EKG-44 scope consistency; existing complete-locator baseline |
| Associated PR changes multiple files/symbols or OpenSpec change contains multiple requirements | Retain only supplied resolved candidates; do not infer requirement coverage, `IMPLEMENTS`, or trust | EKG-44 negative scope rule; EKG-41 implementation-trust boundary |
| New-format snapshot with no PR implementation-evidence records | Remains readable with empty PR-evidence collections | Additive current-format behavior |
| Earlier persisted catalog snapshot or prior PR candidate lacking base/head revisions or explicit association | Reject at the version/readback boundary; do not backfill, migrate, or infer missing PR evidence | EKG-44 has no approved legacy mapping; EKG-38 greenfield baseline |

#### Scenario: Matrix cases are executable
- **WHEN** automated tests exercise each verification-matrix row at its applicable owned boundary
- **THEN** each row has the documented admission, rejection, coalescing, retention, or projection outcome
- **THEN** tests verify that source/provider payloads, credentials, tokens, URLs, and unrepresented implementation conclusions are not serialized, persisted, or queryable

