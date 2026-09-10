## ADDED Requirements

### Requirement: Canonical ontology represents typed pull-request implementation evidence
The canonical ontology SHALL provide immutable, deterministic, payload-free records for revision-bounded pull-request evidence, its explicit intended-change association, and a PR reference from an observed cross-graph candidate. A represented PR SHALL be a canonical `PULL_REQUEST` node with a stable identity separate from display data and must retain its repository node reference, base revision, head revision, explicit source evidence reference, and provenance reference. A PR-scoped candidate reference SHALL not change the identity of the underlying cross-graph claim. A graph snapshot containing no PR implementation-evidence records SHALL remain constructible with empty PR-evidence collections.

#### Scenario: PR evidence is modeled without provider payloads
- **WHEN** local code constructs valid typed PR implementation evidence and an association to an eligible intended change
- **THEN** the canonical snapshot serializes deterministic PR, relation-origin, source-reference, and provenance identifiers with base/head revision values
- **THEN** it does not serialize provider models, PR titles/descriptions, source bodies, diff bodies, URLs, credentials, tokens, or source code

#### Scenario: PR source reference does not change candidate identity
- **WHEN** equivalent `TOUCHES` claims have the same intended-change subject and complete code locator but different valid attributable PR observations
- **THEN** the claims retain the same existing stable claim identity and accumulate distinct PR-scoped observations
- **THEN** each observation retains its own PR and provenance reference
