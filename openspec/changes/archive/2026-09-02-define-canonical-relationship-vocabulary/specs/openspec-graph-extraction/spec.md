## ADDED Requirements

### Requirement: OpenSpec relationships use the canonical source mapping
OpenSpec extraction SHALL emit hierarchy edges as `CONTAINS`, retain evidenced change-to-specification assertions only as derivation support, derive or preserve `TRACES_TO` only through the approved traceability flow, and emit uniquely resolved `related` metadata only as non-confident `REFERENCES`. It SHALL not emit a trusted semantic relationship for unsupported OpenSpec wording or metadata.

#### Scenario: Related metadata remains non-confident reference
- **WHEN** a durable OpenSpec `related` entry uniquely resolves to a specification
- **THEN** extraction emits a non-confident `REFERENCES` edge with source evidence
- **THEN** it does not emit `DEPENDS_ON`, `IMPLEMENTS`, or trusted cross-graph semantics
