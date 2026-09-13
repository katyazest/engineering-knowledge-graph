# bitbucket-source-adapter Specification

## Purpose
Bitbucket pull-request source boundary that normalizes PR, changed-file, and explicit-reference observations into existing implementation-evidence records with provenance. Synced from change implement-bitbucket-source-adapter.

## Requirements
### Requirement: Bitbucket PR observations normalize through an isolated, revision-bounded source boundary
The system SHALL provide a reusable project-owned Bitbucket source adapter that obtains a selected pull-request observation through an injected source port and converts only allowlisted identity-level fields into existing `PullRequestImplementationEvidence` and `PullRequestObservedRepositoryRelation` records. Bitbucket API, transport, MCP request/response, authentication, and provider model details SHALL remain behind that port and SHALL NOT become canonical ontology, graph, persistence, query, or pipeline-result models.

For an admitted PR, the adapter SHALL require a payload-safe source-qualified PR identity, an existing canonical `REPOSITORY` node, `merged=true`, complete immutable Git base and head commit revisions, a revision-bounded PR source artifact, and complete external provenance. The base and head commit IDs are the revision/commit boundary represented by the existing PR implementation-evidence model. The output SHALL bind its observed repository relation to that same PR and repository, retain separate source/provenance references for the PR and relation, and preserve the existing declared-versus-observed relationship semantics.

#### Scenario: Complete merged Bitbucket PR becomes existing implementation evidence
- **WHEN** an injected source port supplies one selected merged PR with a safe source-qualified identity, an existing repository node, complete immutable base/head commit IDs, and complete source-observation metadata
- **THEN** the adapter returns deterministic existing PR implementation evidence, its observed PR-to-repository relation, and their complete payload-free source-artifact evidence and external provenance
- **THEN** the PR source artifact is bounded by the exact head commit and no Bitbucket transport or response model is present in the normalized output

#### Scenario: Ineligible PR input is rejected without a partial PR graph contribution
- **WHEN** a selected source observation is unmerged; lacks a PR identity, known repository, base/head commit, source artifact, observation time, or provenance field; uses a branch, tag, abbreviated commit, unsafe identifier, or conflicting immutable value
- **THEN** the adapter returns a deterministic safe diagnostic for that selected PR
- **THEN** it returns no PR evidence, PR node, observed repository relation, association, changed-file observation, candidate, or provenance/evidence record for that invalid PR

#### Scenario: Provider failure does not leak or fabricate implementation evidence
- **WHEN** the injected source port is unavailable, raises, or supplies an unsupported or structurally malformed response for a selected PR
- **THEN** the adapter returns a deterministic unavailable or invalid-source outcome without retaining exception text or provider payload
- **THEN** it does not retry against another PR, repository, branch, revision, or provider and emits no graph contribution for that selection

### Requirement: Available Bitbucket changed files are retained as exact, provenance-complete observations
For each valid changed-file observation available from an admitted PR source record, the adapter SHALL emit a compact `BitbucketChangedFileObservation` containing a deterministic stable file-observation identity, the exact repository-relative file path, the admitted PR/repository/head-revision context, and separate source-artifact evidence and complete external provenance references. It SHALL sort observations by stable identity and coalesce repeated equivalent observations. A changed-file observation SHALL be an observed source fact and a possible input to the existing OpenLore changed-file request/PR candidate seams; it SHALL NOT be a symbol mapping, `CodeLocator`, semantic edge, implementation conclusion, or trusted projection.

The adapter SHALL retain only source information necessary to identify the changed file at the PR head revision. It SHALL NOT retain or parse diff bodies, line ranges, file contents, symbol bodies, commit messages, titles, descriptions, comments, navigation URLs, credentials, tokens, or arbitrary provider fields. If the source cannot provide changed-file observations, the adapter SHALL report an explicit deterministic unavailable outcome rather than treating unavailable data as an empty change set.

#### Scenario: Exact changed files can be handed to later resolution without a code claim
- **WHEN** an admitted PR source response contains unordered or repeated equivalent valid changed-file observations at its head revision
- **THEN** the adapter returns one deterministically ordered provenance-complete observation for each distinct file identity and exposes only its stable ID, path, PR/repository/head context, and evidence/provenance references
- **THEN** no symbol is guessed and no cross-graph claim, lifecycle record, `IMPLEMENTS` relation, requirement coverage result, or trusted projection is emitted

#### Scenario: Missing, malformed, or conflicting changed-file data remains explicit
- **WHEN** the changed-file source is unavailable, a file path is missing or unsafe, a record disagrees with the admitted PR repository/head revision, or one stable file identity conflicts with another retained path/context
- **THEN** the adapter emits deterministic payload-safe non-admission diagnostics for the affected file source data without choosing a path or context by input order
- **THEN** it emits no changed-file observation or later-resolution input for the affected record and does not alter the otherwise valid PR evidence

### Requirement: Bitbucket traceability associations require structured explicit source declarations
The adapter SHALL materialize a `PullRequestDeclaredAssociation` only from a separate structured explicit-reference record supplied through its source-port contract. A supported record SHALL identify exactly one target kind (`OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, or `JIRA_STORY`), one exact canonical target ID, and its own payload-safe source artifact and complete external provenance. The adapter SHALL materialize each valid reference as the existing directed declared `PULL_REQUEST REFERENCES intended-change` relation only when that exact target is available and has the stated eligible node kind.

The adapter SHALL NOT inspect or use PR titles, descriptions, comments, issue-like tokens, branch names, commit messages, repository names, changed paths, changed-file counts, or global textual similarity to create, select, or expand a traceability association. Missing, unsupported, ambiguous, malformed, or unresolvable structured declarations SHALL be diagnosed without materializing an association or any association-scoped candidate; the PR and changed-file observations may remain represented when independently valid.

#### Scenario: Structured explicit declaration creates only its exact association
- **WHEN** an admitted PR source response supplies one or more valid structured explicit-reference records for existing eligible OpenSpec-change or Jira-story nodes
- **THEN** the adapter emits one declared association and exact `REFERENCES` projection per distinct valid source-backed target with the association's separate provenance
- **THEN** each association remains separate from the observed PR-to-repository relation and does not imply that the PR, its files, or its revisions implement the target

#### Scenario: Textual coincidence cannot manufacture traceability
- **WHEN** a PR response contains an issue/change-like value only in free text or metadata, or a structured declaration has no source reference, an unsupported convention/type, a missing target, or a target of another node kind
- **THEN** the adapter returns a deterministic non-association diagnostic and creates no declared relation or association-scoped candidate
- **THEN** it does not substitute a best textual match, infer an OpenSpec change/work item, or expose the rejected source text

### Requirement: Bitbucket adapter outputs are deterministic, payload-safe, and verification-bounded
The adapter SHALL return immutable, deterministic result objects and safe metadata that expose only admitted IDs, revisions, repository/file identities, source/provenance references, status, counts, and frozen reason codes. It SHALL not write directly to LadybugDB, alter the canonical ontology, advance persisted catalog formats, invoke symbol resolution, or change unconfigured pipeline behavior. Existing PR implementation-evidence, source-artifact identity, provenance, OpenLore bridge, candidate-extraction, relationship, persistence, and trust boundaries SHALL remain compatible; a caller remains responsible for separately submitting exact changed files to OpenLore and exact resolved outcomes to candidate extraction.

The change SHALL document and exercise the following verification matrix at adapter DTO, injected-port fake, source/provenance, graph-merge, OpenLore handoff conversion, and result-serialization boundaries. Cases outside this matrix SHALL be reported as change candidates unless they violate another approved requirement or applicable baseline.

| Input class | Expected admission or outcome | Compatibility anchor |
| --- | --- | --- |
| Merged selected PR with safe source-qualified identity, existing repository, complete immutable base/head commits, and complete source observation | Emit deterministic existing PR evidence and observed repository relation with head-bounded source artifact/provenance | EKG-45 intent; EKG-44 PR evidence model; EKG-40 provenance |
| Same complete PR, association, and changed-file source observations in different orders or repeated | Coalesce equivalent output and preserve stable ordering/identities | Existing idempotency and stable-ID baselines |
| Unmerged PR; missing/unknown repository; missing source/provenance; mutable/abbreviated/mismatched revisions; unsafe identity | Reject that PR before any graph contribution | EKG-44 merged immutable PR admission |
| Provider unavailable, exception, malformed/unsupported response, or unavailable changed-file source | Return only safe deterministic diagnostics; never fabricate an empty file set or retry/broaden acquisition | EKG-45 deterministic source boundary |
| Valid, distinct repository-relative changed files at the admitted PR head | Emit compact file observations with separate complete provenance; no symbol/candidate/implementation conclusion | EKG-45 changed-file scope; EKG-46 bridge input; EKG-41 trust boundary |
| Invalid, conflicting, or PR-context-mismatched changed-file record | Diagnose and exclude only that file observation; do not select an arbitrary alternative | EKG-45 deterministic file admission; exact locator baseline |
| Structured explicit declaration to an existing eligible OpenSpec change or Jira story | Emit only the exact declared `REFERENCES` association with separate provenance | EKG-45 explicit-reference scope; EKG-44 association contract |
| Free-text token/similarity, unsupported convention, absent source reference, unknown target, or ineligible target kind | Emit no association or association-scoped candidate | EKG-45 no-inference requirement; EKG-44 association baseline |
| Source payload, diff/source body, title/description/comment, URL, credential, token, or provider model outside allowlisted normalized fields | Omit it; reject it if offered as a retained identity/reference; never serialize, persist, or expose it | Source-artifact and provenance payload-free baselines |

#### Scenario: Verification matrix is executable without live infrastructure
- **WHEN** fixture and injected-port-fake tests exercise every applicable matrix row through normalization and its existing downstream handoff seams
- **THEN** each row has the documented admission, coalescing, rejection, or non-emission result with deterministic ordering
- **THEN** no test requires a live Bitbucket MCP/API, network access, credentials, or changes to external infrastructure
