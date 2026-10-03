## ADDED Requirements

### Requirement: Query API projects agent evidence-use status without changing graph facts
The local query API SHALL attach an additive deterministic evidence-use disposition and safe reason codes to represented traceability relationships and cross-graph claims, referencing their actual relationship/claim, evidence and provenance IDs and preserving existing per-support as-of freshness, trust, classification, lifecycle, ordering, filters and missing-result behavior. If a path is missing, unsupported, invalid or conflicting, it SHALL NOT synthesize a relationship or return an authoritative conclusion. An explicit current-required request SHALL apply the existing current-evidence eligibility guard to the specific required support; default calls SHALL not impose currentness on historical results. Validation-required calls on invalid graphs SHALL retain their existing safe diagnostic/no-partial-success behavior.

#### Scenario: Additive disposition leaves historical facts intact
- **WHEN** a caller queries valid represented declared support and a separate candidate or inferred support without checked revisions
- **THEN** existing relationship and provenance fields remain unchanged and each response distinguishes historical trust, `unknown` freshness and evidence-use eligibility
- **THEN** no candidate or inferred relationship is labeled authoritative implementation

#### Scenario: Missing relationship yields no replacement
- **WHEN** a caller queries traceability for a graph object without a represented relation to the proposed target
- **THEN** its existing empty/missing traceability behavior remains and no computed or name-derived relationship is returned

### Requirement: Query API explains bounded critical conclusions
The query API SHALL offer a local operation for a caller-proposed `implementation_ownership` or `change_readiness` conclusion, returning a deterministic `supported` or `unresolved` disposition, reason codes, and the represented evidence path or empty path. For implementation ownership, only the catalog-valid direct `OWNED_BY` relationship for the exact represented service or repository and requested target may be supported; other subjects or indirect attribution SHALL be unresolved. Change readiness SHALL remain unresolved without an approved readiness decision contract. Unsupported conclusion kinds, unsafe/malformed identifiers and malformed checked revisions SHALL fail with a safe input error and no partial result; a well-formed but absent graph subject/target SHALL be unresolved/`unknown`. The operation SHALL use existing validation and freshness mechanisms and SHALL not read external sources.

#### Scenario: Proposed owner is not guessed
- **WHEN** the caller requests ownership for an absent or unrelated owner ID
- **THEN** the response is `unresolved`/`unknown` with an empty path, even if that owner's name matches the repository

#### Scenario: Invalid input has no partial result
- **WHEN** a caller supplies an unsupported critical-conclusion kind or an invalid checked revision
- **THEN** the API returns a safe input error rather than a partial conclusion or source payload
