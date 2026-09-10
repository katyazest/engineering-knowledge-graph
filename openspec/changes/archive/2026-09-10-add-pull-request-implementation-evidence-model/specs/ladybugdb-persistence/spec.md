## ADDED Requirements

### Requirement: Persistence round-trips PR implementation evidence and scoped observations deterministically
The persistence boundary SHALL serialize, merge, and read PR implementation-evidence records, their declared/observed relation references, and PR-scoped cross-graph observation references in deterministic order. It SHALL coalesce equivalent records, reject immutable conflicts and dangling references before replacing persisted state, and preserve the existing claim identity and provenance chains. A new-format valid snapshot with no PR implementation-evidence records SHALL read back with empty corresponding collections. Persistence SHALL reject a prior catalog revision or PR candidate that lacks the required base/head revisions or explicit association; it SHALL NOT invent, backfill, or migrate those fields.

#### Scenario: PR evidence round-trip is stable
- **WHEN** a valid snapshot with one declared PR association and one observed scoped candidate is persisted and read repeatedly
- **THEN** each readback has the same PR identity, repository/base/head revisions, relation origins, source/provenance references, candidate identity, and deterministic ordering
- **THEN** no provider payload, URL, source code, or implementation conclusion is added during persistence
