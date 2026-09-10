## ADDED Requirements

### Requirement: Query API exposes represented PR evidence and scope without inferring coverage
The local query API SHALL return deterministic PR implementation-evidence projections containing the canonical PR identifier, repository identifier, base/head revisions, declared intended-change association, declared/observed relation origins, source/provenance references, and linked observed candidate identifiers when represented in the graph. It SHALL return only admitted payload-safe identity-level fields and SHALL not retrieve external systems, expose URLs or provider payloads, infer a requirement-to-file/symbol mapping, or label PR-derived candidates as `IMPLEMENTS` or trusted implementation truth.

#### Scenario: Query distinguishes declared association from observed candidates
- **WHEN** a caller queries represented PR evidence linked to an OpenSpec change or Jira work item with resolved symbol candidates
- **THEN** the response distinguishes the declared PR-to-intended-change relation from observed PR-to-repository and candidate evidence
- **THEN** it does not claim that every changed file/symbol or any unrepresented requirement is implemented
