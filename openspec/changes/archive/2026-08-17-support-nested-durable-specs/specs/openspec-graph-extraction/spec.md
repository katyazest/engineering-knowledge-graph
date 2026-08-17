## MODIFIED Requirements

### Requirement: Durable specifications are extracted with requirement and scenario granularity
The system SHALL extract durable OpenSpec specifications, requirements, and scenarios from every `spec.md` file discovered recursively under `openspec/specs/` into canonical graph facts.

#### Scenario: Current specification graph facts are produced
- **WHEN** the extractor reads a durable spec file containing `### Requirement:` and `#### Scenario:` headings
- **THEN** it produces an OpenSpec specification node for the capability identity derived from the spec path
- **THEN** it produces one OpenSpec requirement node for each `### Requirement: <name>` heading
- **THEN** it produces one OpenSpec scenario node for each `#### Scenario: <name>` heading under a requirement
- **THEN** it links the specification to its requirements and each requirement to its scenarios

#### Scenario: Nested durable specification graph facts are produced
- **WHEN** the extractor reads `openspec/specs/service/payments/spec.md`
- **THEN** it produces an OpenSpec specification node with capability `service/payments`
- **THEN** the specification node uses the same namespaced capability identity in its deterministic OpenSpec identity
- **THEN** source evidence identifies the nested spec file path

#### Scenario: Flat durable capability identity is preserved
- **WHEN** the extractor reads `openspec/specs/payments/spec.md`
- **THEN** it produces an OpenSpec specification node with capability `payments`
- **THEN** it does not rename the capability to a namespaced value

#### Scenario: Local heading schema is respected
- **WHEN** the extractor reads a durable spec file
- **THEN** it treats `### Requirement: <name>` as the supported requirement heading shape
- **THEN** it treats `#### Scenario: <name>` as the supported scenario heading shape
- **THEN** it does not treat `## Requirement: <name>` as a valid requirement heading

### Requirement: Change-local specs remain scoped to their change artifact state
The system SHALL extract change-local spec delta files discovered recursively under a change's `specs/` directory as change-scoped or archive-scoped facts without blindly merging them into current durable specification facts.

#### Scenario: Archived delta spec duplicates durable spec
- **WHEN** an archived change contains a delta spec for a capability that also exists under `openspec/specs`
- **THEN** the extractor preserves the archived delta spec as an archive-scoped spec fact
- **THEN** the extractor preserves the durable spec as the current specification fact
- **THEN** it does not collapse the two facts into one node solely because their capability names match

#### Scenario: Active delta spec is linked to active change
- **WHEN** an active change contains `specs/<capability>/spec.md`
- **THEN** the extractor links the change-scoped spec fact to the active change
- **THEN** the extractor preserves the capability identity from the delta spec path

#### Scenario: Nested active delta spec preserves namespaced capability identity
- **WHEN** an active change contains `specs/service/payments/spec.md`
- **THEN** the extractor links the change-scoped spec fact to the active change
- **THEN** the change-scoped spec fact has capability `service/payments`
- **THEN** the change-to-spec relationship preserves capability `service/payments`

#### Scenario: Nested archived delta spec preserves namespaced capability identity
- **WHEN** an archived change contains `specs/service/payments/spec.md`
- **THEN** the extractor preserves the archived delta spec as an archive-scoped spec fact
- **THEN** the archived spec fact has capability `service/payments`
- **THEN** the change-to-spec relationship preserves capability `service/payments`

## ADDED Requirements

### Requirement: OpenSpec spec capability identity is derived from relative spec path
The system SHALL derive OpenSpec spec capability identity from the spec file path relative to the relevant `specs/` directory with the trailing `/spec.md` segment removed.

#### Scenario: Durable nested capability identity is namespaced
- **WHEN** the extractor reads a durable spec at `openspec/specs/service/directory1-n/spec.md`
- **THEN** it derives capability `service/directory1-n`
- **THEN** it uses `service/directory1-n` in specification, requirement, scenario, and relationship properties that identify capability

#### Scenario: Change-scoped nested capability identity is namespaced
- **WHEN** the extractor reads a change-scoped spec at `openspec/changes/add-x/specs/service/directory1-n/spec.md`
- **THEN** it derives capability `service/directory1-n`
- **THEN** it uses `service/directory1-n` in specification, requirement, scenario, and relationship properties that identify capability

#### Scenario: Recursive discovery remains deterministic
- **WHEN** local code runs OpenSpec graph extraction multiple times against unchanged nested and flat spec files
- **THEN** each extraction result contains the same node IDs, edge IDs, evidence IDs, graph counts, and serialized extraction metadata
