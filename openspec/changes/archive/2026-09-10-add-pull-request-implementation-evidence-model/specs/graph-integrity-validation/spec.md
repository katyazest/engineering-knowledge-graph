## ADDED Requirements

### Requirement: Integrity validation enforces PR evidence, relation origin, and candidate scope consistency
Graph integrity validation SHALL validate PR evidence stable identity, payload-safe source references, repository endpoint, merged status, immutable base/head revisions, source-artifact/provenance resolution, declared intended-change association endpoint, and observed PR-to-repository relation. It SHALL validate that each PR-scoped cross-graph observation references its represented PR and declared association and that its locator repository/head revision agree with the PR evidence. It SHALL report deterministic errors and SHALL not repair, infer, default, or promote invalid PR evidence.

#### Scenario: Inconsistent PR evidence makes the snapshot invalid
- **WHEN** a snapshot contains a PR evidence record with a dangling source/provenance reference, unsupported association endpoint, duplicate-conflicting revision identity, or a candidate locator that differs from the PR repository or head revision
- **THEN** validation returns invalid status with a deterministic diagnostic naming the affected record and violated PR-evidence rule
- **THEN** later persistence-required query and trusted projection boundaries reject the invalid snapshot
