## ADDED Requirements

### Requirement: Ontology represents OpenSpec extraction facts
The system SHALL provide canonical graph vocabulary for OpenSpec-originated specifications, requirements, scenarios, active changes, archived changes, and change artifacts.

#### Scenario: OpenSpec node kinds are available
- **WHEN** local code constructs canonical graph nodes for OpenSpec extraction output
- **THEN** it can represent `openspec-active-change`, `openspec-archived-change`, `openspec-spec`, `openspec-requirement`, `openspec-scenario`, and `openspec-artifact` node kinds
- **THEN** the nodes can be serialized deterministically without external services, API keys, cloud services, database access, or OpenLore queries

#### Scenario: OpenSpec relationship kinds are available
- **WHEN** local code constructs canonical graph edges for OpenSpec extraction output
- **THEN** it can represent relationships from specs to requirements, requirements to scenarios, changes to change artifacts, changes to change-scoped specs, and specs to related specs
- **THEN** the edges can be serialized deterministically

### Requirement: Ontology supports non-confident graph relationships
The system SHALL represent relationship confidence so manually maintained OpenSpec metadata can be distinguished from directly extracted structural facts.

#### Scenario: Related spec edge is non-confident
- **WHEN** local code constructs an edge derived from `related` spec frontmatter
- **THEN** the edge can be marked non-confident
- **THEN** serialization preserves the confidence value deterministically

#### Scenario: Structural OpenSpec edge remains confident by default
- **WHEN** local code constructs an edge directly derived from OpenSpec file structure, such as spec contains requirement
- **THEN** the edge can be represented as confident or without a non-confident marker
- **THEN** serialization distinguishes it from manually maintained related-spec metadata

### Requirement: Ontology supports OpenSpec source evidence
The system SHALL represent source evidence for OpenSpec-originated graph facts without embedding full OpenSpec or implementation content.

#### Scenario: OpenSpec source evidence is serializable
- **WHEN** local code constructs evidence for a fact extracted from an OpenSpec file
- **THEN** the evidence can identify a local source file path, artifact type, heading name, and OpenSpec object identity
- **THEN** the serialized evidence excludes full markdown bodies, implementation source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads

#### Scenario: Opaque change identity is preserved
- **WHEN** local code constructs OpenSpec evidence or nodes for a change directory whose name includes a date, Jira issue ID, both, or only a Jira issue ID
- **THEN** the full directory name can be preserved as the stable OpenSpec change identity
- **THEN** any Jira-looking token can be represented only as optional metadata or a reference hint
