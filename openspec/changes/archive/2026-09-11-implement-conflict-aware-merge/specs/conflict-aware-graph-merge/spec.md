## ADDED Requirements

### Requirement: Merge evaluates complete same-identity assertion cohorts before producing a graph result
The system SHALL evaluate all records with the same canonical stable identity as one assertion cohort before coalescing, rejecting, serializing, or persisting that identity. The cohort SHALL retain every independently supplied valid record's evidence and provenance references while compatibility is evaluated. This applies to canonical nodes, edges, evidence, provenance, cross-graph claims and support/lifecycle records, and typed pull-request evidence and relation records. Canonical object IDs, source-artifact identities, provenance IDs, and classified-support IDs SHALL remain unchanged by cohort evaluation.

#### Scenario: Independently sourced compatible assertions coalesce
- **WHEN** two snapshots contain compatible records with the same canonical ID and distinct valid evidence or provenance references
- **THEN** merge produces one canonical record with the deterministically ordered union of compatible references
- **THEN** it preserves every contributing record's source-artifact and provenance references without changing the canonical ID

#### Scenario: Repeated equivalent assertion is idempotent
- **WHEN** one valid snapshot is merged repeatedly with an equivalent snapshot
- **THEN** the resulting serialized snapshot and graph counts are identical on every merge
- **THEN** no duplicate record, evidence reference, or provenance reference is created

### Requirement: Merge resolution is conservative and source authority never silently overrides a canonical assertion
The system SHALL coalesce a same-identity assertion cohort only when its asserted canonical values are equivalent under the canonical serialization contract and any allowed reference sets can be unioned. A differing asserted value, record type, source-artifact field, immutable provenance field, classified-support field, lifecycle revision value, or presentation value SHALL be a conflict unless another approved canonical contract explicitly defines that difference as non-assertional.

The existing EKG-41 authority rule remains narrowly scoped: declared, authoritative, explicitly trusted support together with an explicit valid lifecycle decision can determine trusted cross-graph projection eligibility. It SHALL NOT select, rewrite, discard, or make compatible a conflicting generic canonical node, edge, evidence, provenance, pull-request, claim, observation, or lifecycle record. The merge SHALL NOT use source type, source-artifact identity, source revision, declared/observed/inferred origin, authoritative/derived status, trust disposition, lifecycle state, confidence, timestamp, evidence count, lexical presentation ordering, or input order as a generic assertion-winner rule.

#### Scenario: Different source assertions cannot become a last-write-wins fact
- **WHEN** two individually valid independently sourced assertions share a canonical ID but differ in an asserted value
- **THEN** merge reports a deterministic unresolved conflict that identifies the canonical ID, collection, and safe contributing record/evidence/provenance references
- **THEN** it does not return, serialize, persist, or project either asserted value as the selected canonical fact

#### Scenario: Existing declared authority is not a generic merge override
- **WHEN** a same-identity canonical assertion conflict is accompanied by declared authoritative trusted cross-graph support or a trusted lifecycle decision
- **THEN** the merge conflict remains unresolved and is reported
- **THEN** the support may affect only the existing trusted cross-graph projection eligibility after the graph is otherwise valid

### Requirement: Conflict outcomes and diagnostics are deterministic and payload-free
The system SHALL return a deterministic merge-conflict outcome before exposing a merged snapshot when a cohort is unresolved. The outcome and graph-integrity diagnostics SHALL include a stable rule identifier, affected canonical ID, collection, and deterministically ordered safe contributing record, evidence, and provenance identifiers sufficient to audit the conflict. They SHALL exclude competing source bodies, provider payloads, source code, credentials, tokens, URLs, and full conflicting property values. The system SHALL not partially mutate a supplied snapshot or expose a partial merged result.

#### Scenario: Reversing input order changes neither outcome nor diagnostic
- **WHEN** the same incompatible assertion cohort is merged in either input order
- **THEN** both attempts yield the same conflict status, rule identifier, affected ID, collection, and ordered safe references
- **THEN** neither attempt selects a different record or emits a trusted fact

### Requirement: Conflict-aware merge verification matrix bounds testing
The change SHALL document and exercise the following verification matrix at the graph snapshot, validation, persistence, and applicable cross-graph projection boundaries. Cases outside this matrix are change candidates unless they violate another approved requirement or baseline contract.

| Input class | Expected behavior | Compatibility anchor |
| --- | --- | --- |
| Repeated equivalent same-identity assertion | Coalesce once; preserve stable IDs and deterministic ordering | Existing idempotency baseline |
| Compatible same-identity assertions with distinct valid evidence/provenance | Coalesce canonical fact; retain union of all supporting references | Existing multi-evidence provenance contract |
| Same identity with a different asserted value, type, presentation value, source-artifact field, immutable provenance field, classified-support value, or lifecycle revision value | Retain cohort through evaluation; return/report deterministic conflict; do not select, persist, or trust a winner | EKG-42 conflict-aware merge intent |
| Same conflict in reversed input/persistence-write order | Identical conflict status and safe diagnostic | Determinism baseline |
| Declared authoritative trusted support and explicit lifecycle accompanying a generic conflict | Do not override generic conflict; apply only existing trusted-projection eligibility after valid merge | EKG-41 authority boundary |
| Valid declared/observed/inferred support for one claim with distinct stable identities | Retain independently; do not rank by source authority, confidence, count, or order | EKG-41 evidence precedence |
| Persisted valid state plus conflicting incoming write | Reject before replacement; preserved readback contains prior valid state | Persistence integrity baseline |

#### Scenario: Verification matrix is executable
- **WHEN** automated tests exercise every applicable row in the conflict-aware merge verification matrix
- **THEN** each case produces the documented coalescing, retention, rejection, persistence, or projection result
- **THEN** tests verify that no source or provider payload is included in a conflict diagnostic or persisted as a result of the conflict
