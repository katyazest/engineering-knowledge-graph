## ADDED Requirements

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
