## ADDED Requirements

### Requirement: Local evidence-bearing queries expose as-of freshness
The local query API SHALL return deterministic freshness status (`fresh`, `stale`, or `unknown`) and a safe reason/comparison basis for each represented provenance support in existing fact, traceability, PR-evidence, scenario-test, and cross-graph query results. It SHALL expose an evidence-to-provenance association and the current-evidence eligibility of the specific represented support, not merely a whole fact's unlabeled status. The caller SHALL be able to supply optional checked current-source revisions; without a matching check the status SHALL be `unknown`. An assessed `fresh` or `stale` status SHALL identify the check's `checked_at` instant and be described as an as-of result, not a claim about the source at response time. Existing fact fields, ordering, query filters, and explicit missing-result behavior SHALL remain compatible; no source lookup or payload exposure SHALL occur.

#### Scenario: Fact has freshness for each supporting observation
- **WHEN** a requirement query returns a fact with external evidence and a caller supplies one matching and one mismatching checked source revision for two different supporting artifacts
- **THEN** the result associates each evidence/provenance reference with its own as-of `fresh` or `stale` status and current-evidence eligibility
- **THEN** the pre-existing fact identity, evidence IDs, and provenance details remain available

#### Scenario: Traceability and cross-graph support retain unknown
- **WHEN** a caller requests traceability including an edge and cross-graph support without checked revisions
- **THEN** each represented support exposes `unknown` freshness and is not current-eligible
- **THEN** its stored trust/lifecycle disposition is not reclassified as current or ready

#### Scenario: Invalid checked input yields no partial query result
- **WHEN** a query receives conflicting or unsafe checked-revision entries
- **THEN** it returns a deterministic payload-safe input error rather than a partially assessed fact/relationship list

### Requirement: Current-required query consumers cannot silently count stale support
When a query consumer explicitly requires current evidence for a particular support, the query API SHALL use the shared current-evidence eligibility decision and SHALL expose that support as ineligible unless it has a fresh complete chain. Query results SHALL NOT present stale or unknown support as satisfying that explicit requirement, even if its stored trust or verification classification is otherwise positive. The API SHALL NOT silently impose a new freshness requirement on calls that do not request one.

#### Scenario: Explicit current-required check rejects stale support
- **WHEN** a caller evaluates a represented relationship's supporting evidence with current evidence required and every chain is stale or unknown
- **THEN** the relationship's support is not eligible for that check and the result retains the observed freshness statuses
