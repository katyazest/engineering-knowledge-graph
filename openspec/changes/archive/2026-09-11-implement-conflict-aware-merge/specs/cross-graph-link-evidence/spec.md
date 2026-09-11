## MODIFIED Requirements

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
