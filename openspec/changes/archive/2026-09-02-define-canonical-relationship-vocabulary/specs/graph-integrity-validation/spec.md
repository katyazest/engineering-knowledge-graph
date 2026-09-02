## ADDED Requirements

### Requirement: Graph integrity validation enforces relationship vocabulary
Graph integrity validation SHALL validate every canonical edge and trusted cross-graph link against the relationship catalog's kind, ordered endpoint contract, cardinality, semantic/trust classification, evidence references, and provenance requirements. It SHALL report deterministic error diagnostics for violations before persistence or downstream query use.

#### Scenario: Invalid trusted link fails validation
- **WHEN** a trusted cross-graph link uses a non-catalog kind or a subject kind not allowed for its `CodeLocator` target
- **THEN** validation reports an error diagnostic identifying the claim or link
- **THEN** validation returns invalid status
