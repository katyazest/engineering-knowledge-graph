# cross-graph-link-evidence Specification

## Purpose
TBD - created by archiving change define-cross-graph-link-evidence-model. Update Purpose after archive.
## Requirements
### Requirement: Cross-graph link claims use stable code-locator targets
The system SHALL represent a proposed cross-graph link as a canonical link claim containing an existing EKG subject identifier, a semantic relationship kind, and a complete `CodeLocator` target containing non-empty repository, revision, file, and symbol values. The claim's stable identifier SHALL be derived from those identity fields and SHALL not depend on display text, evidence contents, strategy attribution, lifecycle state, source-code line numbers, or OpenLore query output.

#### Scenario: Equivalent claim identity is stable
- **WHEN** local code constructs two link claims with the same subject identifier, semantic relationship kind, and `CodeLocator` field values
- **THEN** both claims have the same stable identifier even when their evidence, strategy attribution, or lifecycle states differ

#### Scenario: Target identity changes the claim
- **WHEN** local code constructs link claims that differ in any `CodeLocator` repository, revision, file, or symbol field
- **THEN** the claims have different stable identifiers

#### Scenario: Incomplete code locator is rejected
- **WHEN** local code constructs a link claim with a missing or blank code-locator identity field
- **THEN** the system rejects the claim rather than creating a partial or inferred code target

### Requirement: Candidate evidence is attributable and accumulates independently
The system SHALL represent candidate link evidence as an attributable observation associated with exactly one cross-graph link claim. Each observation SHALL retain an opaque non-empty strategy identifier and its source/provenance reference; a link claim SHALL retain all non-conflicting observations rather than replacing a prior observation from another strategy.

#### Scenario: Evidence from multiple strategies accumulates
- **WHEN** two valid candidate-evidence observations support the same claim and have distinct observation identities or strategy attributions
- **THEN** the serialized claim support retains both observations and their individual attribution and provenance reference

#### Scenario: Duplicate observation is idempotent
- **WHEN** the same candidate-evidence observation is added repeatedly to a graph snapshot or persisted store
- **THEN** the result contains one observation with its original stable identifier

#### Scenario: Conflicting evidence identity is rejected
- **WHEN** candidate-evidence observations with the same stable identifier disagree on immutable claim, strategy, provenance, or target identity fields
- **THEN** the system rejects the conflicting graph data rather than selecting one observation

### Requirement: Candidate evidence and trusted semantic links are distinct
The system SHALL preserve candidate evidence separately from a trusted semantic link. A claim in the `candidate`, `rejected`, or `superseded` lifecycle state SHALL not be emitted or interpreted as a trusted semantic relationship; only a claim explicitly in the `trusted` lifecycle state SHALL be available as a trusted semantic link, with the claim's attributable evidence retained as support. The existing declared-authoritative and explicit-lifecycle eligibility rules SHALL determine only trusted cross-graph projection eligibility after a valid graph merge; they SHALL NOT resolve a conflicting same-identity canonical assertion, discard independently valid declared/observed/inferred support, or override conflict-aware merge diagnostics.

#### Scenario: Candidate claim is not a semantic relationship
- **WHEN** a snapshot contains a claim with one or more active candidate-evidence observations and lifecycle state `candidate`
- **THEN** the snapshot serializes the claim and its evidence without creating a trusted semantic edge or otherwise presenting the claim as semantic truth

#### Scenario: Trusted claim retains its support
- **WHEN** a valid claim is recorded with lifecycle state `trusted`
- **THEN** the snapshot exposes a trusted semantic link to the same `CodeLocator` target and retains the claim's attributable evidence identifiers

#### Scenario: Rejected or superseded claim remains auditable
- **WHEN** a claim moves to `rejected` or `superseded`
- **THEN** its locator identity and accumulated evidence remain serializable for audit
- **THEN** it is not exposed as a trusted semantic link

#### Scenario: Authority eligibility does not repair an assertion conflict
- **WHEN** a claim has support eligible for trusted projection but another same-identity canonical assertion cohort is unresolved
- **THEN** the conflict-aware merge rejects the graph before trusted projection is exposed
- **THEN** the trusted lifecycle does not choose or rewrite a conflicting canonical record

### Requirement: Link lifecycle is explicit and valid
The system SHALL retain an ordered lifecycle history for each link claim and derive its current lifecycle state from the highest lifecycle revision. The permitted states SHALL be `candidate`, `trusted`, `rejected`, and `superseded`; the system SHALL reject unknown states, duplicate conflicting revisions, and histories without a determinable current revision. It SHALL not infer promotion to `trusted` from evidence count, strategy name, confidence, or any OpenLore result.

#### Scenario: Unsupported lifecycle state is rejected
- **WHEN** local code deserializes or persists a claim lifecycle entry with an unsupported value, conflicting revision, or unusable revision
- **THEN** the system fails with a deterministic validation error

#### Scenario: Trust is explicit
- **WHEN** a claim has any number of active candidate-evidence observations but lifecycle state `candidate`
- **THEN** the system keeps the claim as a candidate and does not promote it automatically

### Requirement: Cross-graph link records preserve the OpenLore boundary
The system SHALL store only `CodeLocator` identity, canonical link/evidence metadata, lifecycle state, and provenance references for cross-graph links. It SHALL not resolve the locator, query OpenLore, or store source code, symbol bodies, call graphs, dependency graphs, architecture analysis, impact analysis, or OpenLore response payloads.

#### Scenario: Link records remain local and payload-free
- **WHEN** local code constructs, serializes, merges, or persists cross-graph link claims and evidence
- **THEN** the operation completes without an OpenLore call or network access
- **THEN** the serialized records exclude OpenLore-owned code-intelligence content and external payloads

### Requirement: Cross-graph link records are deterministic and persistence-compatible
The system SHALL serialize, merge, and persist cross-graph link claims and candidate-evidence observations deterministically. It SHALL preserve existing graph snapshots that contain no cross-graph link records, and it SHALL reject a trusted link or candidate-evidence observation that references an absent link claim.

#### Scenario: Repeated merge and readback are stable
- **WHEN** the same valid snapshot containing link claims and candidate evidence is merged and read back repeatedly
- **THEN** stable identifiers, record ordering, lifecycle state, attribution, provenance references, and trusted-link visibility remain unchanged

#### Scenario: Existing snapshot remains readable
- **WHEN** the persistence adapter reads a valid graph snapshot created before cross-graph link records were introduced
- **THEN** it returns the existing nodes, edges, and evidence unchanged with empty cross-graph link collections

#### Scenario: Dangling cross-graph record is rejected
- **WHEN** a snapshot contains candidate evidence or a trusted semantic link that references a link claim not present in the snapshot
- **THEN** validation and persistence reject the snapshot with a deterministic integrity error

### Requirement: PR-derived observations remain observed candidates, not implementation truth
The system SHALL represent a candidate emitted from an explicitly linked PR changed-symbol mapping as observed-provenance cross-graph evidence with a lifecycle state of `candidate`. It SHALL not create an `Edge` of kind `IMPLEMENTS`, expose a trusted semantic link, or otherwise promote the claim to `trusted` solely because the PR is merged, explicitly linked, or changed the resolved symbol. Promotion, rejection, and supersession SHALL remain independent lifecycle actions supported by separately supplied evidence.

#### Scenario: Merged PR candidate is not trusted
- **WHEN** PR code-candidate extraction emits a claim and observation from an explicitly linked merged PR changed-symbol mapping
- **THEN** the claim's current lifecycle state is `candidate`
- **THEN** the graph has no trusted cross-graph link or `IMPLEMENTS` edge created solely from that extraction

#### Scenario: Independent lifecycle evidence can later change the outcome
- **WHEN** a separately supplied valid lifecycle revision promotes, rejects, or supersedes a PR-derived candidate with its own provenance evidence
- **THEN** the graph applies that explicit lifecycle revision according to the existing lifecycle contract
- **THEN** the original PR-derived observation remains retained for audit

### Requirement: Cross-graph evidence retains first-class provenance by reference
The system SHALL require each cross-graph candidate observation and lifecycle evidence reference to resolve to complete first-class provenance and SHALL preserve those references through merge, persistence, and query. It SHALL not copy authoritative source content, provider payloads, or code intelligence into cross-graph claim, observation, or lifecycle records.

#### Scenario: Cross-graph candidate remains explainable without copied content
- **WHEN** a valid external or derived provenance record supports a cross-graph candidate observation or lifecycle revision
- **THEN** the persisted and queried cross-graph record retains its provenance reference and explanation chain
- **THEN** the cross-graph record contains no copied source content or authoritative provider payload

### Requirement: Cross-graph claims use catalog relationship kinds
Cross-graph link claims SHALL use only catalog-defined relationship kinds that permit the claim subject kind and a complete `CodeLocator` target. Candidate observations SHALL remain candidate evidence until an explicit trusted lifecycle revision; trusted projection SHALL reject a claim that no longer conforms to the catalog.

#### Scenario: PR observation is a candidate TOUCHES claim
- **WHEN** PR-code candidate extraction produces a valid explicitly linked merged-PR changed-symbol observation
- **THEN** it produces a `TOUCHES` candidate claim and attributable evidence
- **THEN** it does not produce a trusted semantic link or an `IMPLEMENTS` edge

### Requirement: Cross-graph support records carry the evidence trust classification
The system SHALL require each cross-graph candidate observation and lifecycle entry to retain the evidence origin, authoritative/derived status, confidence, and explicit trust disposition defined by `cross-graph-evidence-trust-model`. Candidate observations and lifecycle entries with incomplete classification SHALL be rejected before merge, persistence, or trusted-link projection. Existing lifecycle state remains a claim disposition and SHALL NOT substitute for the support record's trust disposition.

#### Scenario: Candidate lifecycle does not replace evidence classification
- **WHEN** a valid candidate observation and its candidate lifecycle entry are recorded
- **THEN** both records retain their required evidence classification and trust disposition
- **THEN** the `candidate` lifecycle state alone does not imply an origin, status, confidence, or trust disposition

### Requirement: Trusted cross-graph implementation projection requires declared authority
The system SHALL project a trusted `IMPLEMENTS` cross-graph link only when the claim has catalog-valid endpoints, complete provenance, an explicit trusted lifecycle decision, and qualifying authoritative declared support. Observed PR/file support and LLM-only inferred support SHALL remain non-trusted for implementation even when their lifecycle state is `trusted` or their confidence value is present.

#### Scenario: Invalid trusted implementation lifecycle is not projected
- **WHEN** a trusted lifecycle decision for an `IMPLEMENTS` claim is supported by observed PR/file or LLM-only inferred evidence
- **THEN** validation rejects the trusted implementation projection deterministically
- **THEN** the claim is not exposed as a trusted cross-graph link

### Requirement: PR-scoped cross-graph observations retain their observed source and declared scope
The system SHALL require every cross-graph observation produced from PR implementation evidence to retain a canonical `PULL_REQUEST` reference and an explicit declared PR-to-intended-change association reference in addition to its existing observation and provenance references. The referenced PR, association subject, `CodeLocator` repository, and `CodeLocator` revision SHALL agree exactly. Such support SHALL be classified `observed` and remain untrusted; the separately represented PR-to-intended-change relation SHALL be classified `declared`. Existing non-PR cross-graph observations are not required to acquire a PR reference.

#### Scenario: PR-scoped observation is explainable end to end
- **WHEN** a valid PR-derived changed-symbol observation supports a `TOUCHES` candidate
- **THEN** the graph and query projection identify the candidate's PR source, declared scope association, observed classification, and provenance references deterministically
- **THEN** the candidate is not exposed as trusted implementation truth

#### Scenario: Dangling or inconsistent PR observation support is invalid
- **WHEN** PR-derived support references no PR or declared association, references a non-PR node, or disagrees with the represented PR repository or head revision
- **THEN** validation rejects the support with a deterministic PR-scope diagnostic
- **THEN** persistence and query-required validation expose no trusted projection or partial support record

### Requirement: Cross-graph verification support cites admitted verification evidence explicitly
The system SHALL permit a cross-graph support record to retain an optional `verification_evidence_id` only when the associated claim kind is `VERIFIED_BY`. The reference SHALL resolve to an admitted `VERIFICATION_EVIDENCE` node with complete evidence/provenance and to an admitted `VALIDATES` relationship from that node to the claim subject. The support record SHALL retain its independent complete provenance, classification, and trust disposition; the reference SHALL participate in immutable support-record conflict validation but SHALL NOT participate in cross-graph claim identity. A missing, mismatched, dangling, unprovenanced, or `IMPLEMENTS`-scoped verification-evidence reference SHALL be rejected before serialization, merge, persistence, query projection, or trusted-link projection.

#### Scenario: Bound verification evidence is queryable as support
- **WHEN** a `VERIFIED_BY` claim support record cites a complete verification-evidence node that validates the claim subject and has independently complete classified support provenance
- **THEN** serialization, persistence/readback, and query retain the verification-evidence reference and provenance without changing the claim identity
- **THEN** a separately valid trusted lifecycle can evaluate the claim using the existing trusted-projection rules

#### Scenario: Verification reference cannot relabel implementation
- **WHEN** a support record cites verification evidence for an `IMPLEMENTS` claim, cites a verification-evidence node that does not validate the claim subject, or lacks complete verification provenance
- **THEN** admission or validation returns a deterministic verification-support diagnostic
- **THEN** no partial support record or trusted implementation projection is exposed

### Requirement: Reliable test-to-code observations remain observed non-implementation candidates
The cross-graph evidence model SHALL retain a normalized reliable test-to-code resolution produced with the `reliable-test-code-resolution` strategy only as an attributable `REFERENCES` claim from an existing mapped `TEST_CASE` to a complete `CodeLocator`, with observed origin, untrusted disposition, complete source evidence/provenance, and an explicit `candidate` lifecycle. It SHALL retain the resolution's payload-safe strategy and observation identities without changing test, OpenSpec target, or claim identity. It SHALL reject a test-to-code observation using that strategy when it is incomplete, unprovenanced, unscoped to a mapped test, uses a relation other than `REFERENCES`, requests a trusted lifecycle/projection, or requests `IMPLEMENTS`; it shall not use the observation count, confidence, declared mapping, test execution, or resolver name to promote the claim. Existing catalog-valid cross-graph records from other sources remain governed by their existing contracts.

#### Scenario: Reliable test-code observation is auditable but not implementation truth
- **WHEN** a complete observed candidate references an admitted mapped test case and exact code locator with its evidence/provenance and candidate lifecycle
- **THEN** merge, persistence, and query retain the candidate and its attribution deterministically
- **THEN** no trusted semantic link or `IMPLEMENTS` conclusion is exposed from that observation

#### Scenario: Test-code promotion attempt is rejected
- **WHEN** test-to-code input requests `IMPLEMENTS`, trusted support/lifecycle, a non-candidate lifecycle, or lacks the required mapped-test scope and provenance
- **THEN** admission or validation rejects it with a deterministic candidate-boundary diagnostic
- **THEN** it emits no trusted implementation projection or replacement candidate

