## ADDED Requirements

### Requirement: Canonical ontology represents verification facts and verification-cited support
The canonical ontology SHALL represent `TEST_CASE`, `TEST_SUITE`, `TEST_RUN`, and `VERIFICATION_EVIDENCE` node kinds and the deterministic natural-key identity contract defined by `verification-ontology`. It SHALL represent an optional verification-evidence reference on a cross-graph support record without changing the identity of the associated cross-graph claim. A graph snapshot containing no verification nodes or verification-cited support SHALL remain constructible, mergeable, and serializable with no verification-specific records; compatible verification facts and references SHALL coalesce, while same-identity immutable conflicts and dangling verification references SHALL be rejected deterministically.

#### Scenario: Verification records merge without changing claims
- **WHEN** compatible snapshots contain the same verification-evidence node and equivalent cross-graph `VERIFIED_BY` support that cites it
- **THEN** merge retains one verification node, one compatible support record, and the existing cross-graph claim identity
- **THEN** evidence and provenance references are deterministically ordered

#### Scenario: Absent or conflicting verification data is safe
- **WHEN** a graph snapshot has no verification records, has a cross-graph support reference to an absent verification-evidence node, or contains same-identity verification records with conflicting immutable values
- **THEN** the empty snapshot remains compatible, and the dangling or conflicting input is rejected deterministically
- **THEN** no value is selected by input order and no verification record is fabricated
