## ADDED Requirements

### Requirement: Derived relationships preserve complete derivation provenance
The system SHALL associate every derived relationship with first-class derived provenance that identifies the explicit derivation rule and the provenance identifiers of all admitted asserted/derived inputs used by that result. It SHALL not derive, omit, or rewrite an input's external observation metadata, and it SHALL reject derived output whose referenced input provenance is absent.

#### Scenario: Traceability derivation retains its provenance chain
- **WHEN** the OpenSpec change-to-specification derivation produces a traceability edge from evidenced asserted input
- **THEN** the derived edge retains the rule identity and referenced input provenance identifiers
- **THEN** the input evidence's source identity, revision, observation time, hash, and extractor metadata remain available through those references
