## ADDED Requirements

### Requirement: Graph snapshots merge canonical assertions without hidden value selection
`GraphSnapshot` merge SHALL preserve the complete same-identity assertion cohort and its evidence/provenance references until the conflict-aware merge contract has determined compatible coalescing or an unresolved conflict. It SHALL not select a node name, edge/evidence property, typed-record field, or other differing asserted value by arrival order, map overwrite, lexical ordering, or another implicit tie-breaker. A successful merge SHALL contain only compatible coalesced records; an unresolved cohort SHALL return the deterministic merge-conflict outcome instead of a snapshot containing a selected record.

#### Scenario: Compatible canonical facts retain all source references
- **WHEN** two compatible canonical facts share an ID and carry different valid evidence references
- **THEN** `GraphSnapshot` merge emits one fact with the sorted union of those references
- **THEN** its canonical ID and canonical serialized values remain unchanged

#### Scenario: Differing presentation text is not selected silently
- **WHEN** two same-identity canonical records differ only in a retained presentation value
- **THEN** `GraphSnapshot` merge reports an unresolved conflict rather than choosing either value
- **THEN** it does not return a graph snapshot containing a lexically or last-arriving selected presentation value
