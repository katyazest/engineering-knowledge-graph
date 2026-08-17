## MODIFIED Requirements

### Requirement: Derivation links OpenSpec changes to durable specifications
The system SHALL derive traceability between OpenSpec change-scoped specification facts and durable specification facts only when both facts already exist in the canonical graph snapshot and share the same OpenSpec capability identity, including namespaced capability identities emitted by extraction.

#### Scenario: Change-scoped spec maps to durable spec
- **WHEN** the graph contains an OpenSpec active or archived change node, a change-scoped spec node for capability `payments`, and a durable spec node for capability `payments`
- **THEN** derivation creates a deterministic relationship from the change or change-scoped spec context to the durable spec
- **THEN** the relationship preserves evidence or derivation metadata identifying the rule that created it

#### Scenario: Namespaced change-scoped spec maps to namespaced durable spec
- **WHEN** the graph contains an OpenSpec active or archived change node, a change-scoped spec node for capability `service/payments`, and a durable spec node for capability `service/payments`
- **THEN** derivation creates a deterministic relationship from the change or change-scoped spec context to the durable spec
- **THEN** the relationship preserves capability `service/payments`
- **THEN** the relationship preserves evidence or derivation metadata identifying the rule that created it

#### Scenario: Same final directory name does not create suffix match
- **WHEN** the graph contains a change-scoped spec node for capability `service-a/payments` and a durable spec node for capability `service-b/payments`
- **THEN** derivation does not create traceability between those specs
- **THEN** derivation reports the skipped or unresolved derivation input in deterministic metadata

#### Scenario: Missing durable spec is not invented
- **WHEN** the graph contains a change-scoped spec node for a capability with no matching durable spec node
- **THEN** derivation does not invent a durable spec node
- **THEN** derivation reports the skipped or unresolved derivation input in deterministic metadata
