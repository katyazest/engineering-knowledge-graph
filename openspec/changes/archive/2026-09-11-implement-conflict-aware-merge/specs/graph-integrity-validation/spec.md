## MODIFIED Requirements

### Requirement: Graph integrity validation detects duplicate identity conflicts
The system SHALL validate that canonical graph object IDs identify one deterministic serialized object per node, edge, evidence, provenance, cross-graph claim, cross-graph support/lifecycle, and typed pull-request record collection. It SHALL evaluate duplicate same-identity assertions before any value is selected, permit equivalent records and compatible source-reference accumulation, and report an error diagnostic for every unresolved conflicting cohort. A conflict diagnostic SHALL identify the affected object ID and collection with deterministically ordered safe contributing record/evidence/provenance identifiers; it SHALL not expose conflicting source/property payloads or select a winner by source authority, input order, or presentation ordering.

#### Scenario: Duplicate identical objects are accepted as deterministic duplicates
- **WHEN** graph integrity validation reads duplicate graph objects with the same ID and equivalent serialized asserted values in the same collection
- **THEN** validation does not report a conflicting identity error for those objects
- **THEN** validation metadata reports the duplicate identity count deterministically

#### Scenario: Compatible evidence is accumulated without a conflict
- **WHEN** same-identity canonical records have equivalent asserted values and distinct valid evidence identifiers
- **THEN** validation accepts the canonical identity with all represented supporting evidence
- **THEN** validation does not report a duplicate identity conflict solely because the source evidence differs

#### Scenario: Duplicate conflicting objects are invalid
- **WHEN** graph integrity validation reads duplicate graph objects with the same ID and different asserted serialized values in the same collection
- **THEN** validation reports a deterministic error diagnostic identifying the conflicting object ID, collection, and safe contributing references
- **THEN** validation returns an invalid validation status without selecting, trusting, or serializing either value as the resolved object
