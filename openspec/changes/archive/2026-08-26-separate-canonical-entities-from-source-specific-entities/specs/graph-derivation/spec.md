## MODIFIED Requirements

### Requirement: Derivation links OpenSpec changes to durable specifications
The system SHALL derive traceability from a source-specific OpenSpec active or archived change to a canonical specification when the graph contains an asserted change-to-canonical-specification relationship with valid evidence.

#### Scenario: Change assertion produces canonical traceability
- **WHEN** the graph contains an OpenSpec change, an asserted evidenced link to a canonical specification, and the derivation rule is executed
- **THEN** derivation creates one deterministic canonical traceability relationship from the change to that specification
- **THEN** the derived relationship records `derived: true`, its derivation rule identity, the asserted input relationship, and the input evidence identifiers

#### Scenario: Traceability does not require a scoped duplicate
- **WHEN** the graph contains a canonical specification supported by both durable and change-scoped OpenSpec evidence
- **THEN** derivation uses that canonical specification identity directly
- **THEN** it does not require or create a change-scoped `openspec-spec` node

#### Scenario: Invalid asserted input is skipped
- **WHEN** a purported OpenSpec change-to-specification assertion has a missing endpoint, missing evidence, or a non-canonical target kind
- **THEN** derivation does not create traceability from that input
- **THEN** it reports a deterministic diagnostic identifying the skipped input
