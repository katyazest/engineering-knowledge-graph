## ADDED Requirements

### Requirement: Derivation produces only catalog-conformant relationships
Graph derivation SHALL validate each proposed output against the canonical relationship catalog before it is emitted. It SHALL derive the existing OpenSpec change-to-specification relationship as `TRACES_TO` only from valid asserted support and complete input provenance, and SHALL skip with a deterministic diagnostic any output with an unsupported kind, endpoint contract, cardinality violation, or absent provenance.

#### Scenario: Invalid derived relationship is skipped
- **WHEN** a derivation input would produce a relationship outside the catalog contract
- **THEN** derivation emits no edge for that input
- **THEN** it reports a deterministic diagnostic without changing other valid derivation output
