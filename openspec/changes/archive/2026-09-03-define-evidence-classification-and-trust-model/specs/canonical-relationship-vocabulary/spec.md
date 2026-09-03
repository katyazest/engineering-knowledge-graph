## ADDED Requirements

### Requirement: Catalog admission applies evidence-trust eligibility to implementation relations
The system SHALL apply the cross-graph evidence-trust model after relationship kind and endpoint validation and before trusted-link projection. Catalog validity and complete provenance are necessary but not sufficient for trusted `IMPLEMENTS`: the implementation-trust boundary SHALL require qualifying authoritative declared support and an explicit trusted lifecycle decision. The catalog SHALL not treat confidence labels, observed PR/file mappings, or inferred support as aliases for declared implementation authority.

#### Scenario: Catalog-valid observed implementation claim remains non-trusted
- **WHEN** an `IMPLEMENTS` claim satisfies the catalog endpoint contract but has only observed PR/file or LLM-only inferred support
- **THEN** it remains non-trusted and is not counted as a trusted semantic implementation relationship
