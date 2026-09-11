## ADDED Requirements

### Requirement: Persistence merge rejects conflicts without replacing valid state
The persistence boundary SHALL evaluate the complete cohort formed by stored and incoming same-identity assertions using the conflict-aware merge contract before replacing persisted state. It SHALL persist compatible coalesced records with deterministic ordering and all valid source/provenance references. On an unresolved conflict, it SHALL return a deterministic persistence integrity failure with the safe conflict diagnostic, leave the prior persisted snapshot unchanged, and expose no selected conflicting value through readback.

#### Scenario: Conflicting incoming assertion does not overwrite persisted fact
- **WHEN** a store contains a valid canonical assertion and an incoming write supplies an independently sourced same-identity assertion with a different asserted value
- **THEN** the write fails before replacement with a deterministic conflict diagnostic
- **THEN** subsequent readback returns the original valid assertion and none of the incoming conflicting value

#### Scenario: Compatible repeated write remains stable
- **WHEN** a valid stored snapshot is written again with an equivalent or compatible same-identity assertion and distinct valid support references
- **THEN** readback contains one canonical record with all deterministically ordered compatible references
- **THEN** repeated writes produce the same serialized snapshot
