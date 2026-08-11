## MODIFIED Requirements

### Requirement: Registry identifies one requirements repository for OpenSpec cross-check and fallback
The system SHALL validate that the Engineering KG registry identifies exactly one requirements repository for durable requirements, specifications, OpenSpec changes, wiki content, and versioned Engineering KG configuration, and SHALL preserve that repository as an independent repository entry for OpenSpec store cross-checking and fallback when no OpenSpec store is registered.

#### Scenario: Configured store repository is valid
- **WHEN** `engineering_kg.store_repository` references an existing repository entry with the `requirements` role
- **THEN** the registry loader accepts that repository as the requirements repository for OpenSpec store cross-check and fallback
- **THEN** the registry exposes the configured requirements repository id for downstream OpenSpec store source validation

#### Scenario: Store repository role is invalid
- **WHEN** `engineering_kg.store_repository` references an existing repository entry that does not have the `requirements` role
- **THEN** the registry loader reports a validation error before producing canonical graph objects

#### Scenario: Store repository reference is unknown
- **WHEN** `engineering_kg.store_repository` references no repository entry in the registry
- **THEN** the registry loader reports a validation error before producing canonical graph objects

#### Scenario: Generated state does not become OpenSpec store
- **WHEN** the registry contains workspace-level generated OpenLore or Engineering KG graph storage paths
- **THEN** the registry keeps those generated-state paths separate from the configured requirements repository identity
