## ADDED Requirements

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
