## MODIFIED Requirements

### Requirement: Durable specifications are extracted with requirement and scenario granularity
The system SHALL extract every durable `spec.md` file beneath `openspec/specs/` into canonical specification, requirement, and scenario facts, each supported by OpenSpec evidence.

#### Scenario: Current specification graph facts are produced
- **WHEN** the extractor reads a durable spec containing `### Requirement:` and `#### Scenario:` headings
- **THEN** it produces canonical specification, requirement, and scenario nodes using source-independent identities
- **THEN** it links the specification to its requirements and each requirement to its scenarios with canonical relationship kinds
- **THEN** every emitted fact references evidence for the source file and supported heading

### Requirement: Change-local specs remain scoped to their change artifact state
The system SHALL retain an active or archived OpenSpec change as a source-specific fact while emitting its delta specification, requirement, and scenario content as canonical facts supported by change-scoped OpenSpec evidence.

#### Scenario: Change delta converges on a canonical specification
- **WHEN** an active or archived change contains `specs/<capability>/spec.md`
- **THEN** the extractor emits or reuses the canonical specification for that repository and capability
- **THEN** it links the source-specific change to the canonical specification with asserted OpenSpec evidence
- **THEN** it does not create an `openspec-spec` node or encode the change identity in the canonical specification ID

#### Scenario: Durable specification is absent
- **WHEN** a change delta names a capability that has no durable spec file
- **THEN** the extractor creates the canonical specification using the same repository-and-capability identity
- **THEN** the emitted fact remains supported by the change-scoped OpenSpec evidence without inventing a durable source file

### Requirement: OpenSpec spec capability identity is derived from relative spec path
The system SHALL derive the capability component of a canonical OpenSpec-backed specification identity from the relative spec path with the trailing `/spec.md` segment removed.

#### Scenario: Same capability across OpenSpec scopes has one identity
- **WHEN** durable and change-scoped spec files represent the same repository and capability
- **THEN** extraction assigns the same canonical specification ID to their compatible facts
- **THEN** both source locations are retained as provenance rather than separate scoped specification nodes

## ADDED Requirements

### Requirement: OpenSpec extraction merges canonical provenance deterministically
The system SHALL coalesce compatible OpenSpec assertions of one canonical identity, sort resulting records and evidence identifiers deterministically, and reject conflicting canonical identity fields.

#### Scenario: Repeated extraction is idempotent
- **WHEN** extraction runs repeatedly against unchanged durable and change-scoped OpenSpec files
- **THEN** it returns the same canonical node IDs, relationship IDs, evidence IDs, ordering, and extraction metadata
- **THEN** it does not duplicate canonical facts or discard existing source evidence
