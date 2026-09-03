## ADDED Requirements

### Requirement: Query API exposes cross-graph evidence classification and trust disposition
The system SHALL expose deterministic cross-graph claim projections containing the claim identity and relationship kind, current lifecycle state, trusted-projection result, and each represented observation/lifecycle support record's origin, authoritative/derived status, confidence, trust disposition, and provenance reference. For observation records it SHALL expose only the admitted payload-safe opaque `strategy_id` and `observation_id`; identifiers rejected at admission SHALL not be serializable, persisted, or queryable. It SHALL distinguish a non-trusted `IMPLEMENTS` candidate from trusted implementation truth and SHALL not calculate a new confidence score, precedence winner, trust disposition, or implementation conclusion during query execution.

#### Scenario: Query returns classified non-trusted implementation candidate
- **WHEN** a caller queries a cross-graph `IMPLEMENTS` candidate supported by observed PR/file or LLM-only inferred evidence
- **THEN** the response returns the stored classification and non-trusted disposition
- **THEN** the response does not expose it as trusted implementation truth
