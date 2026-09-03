## ADDED Requirements

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
