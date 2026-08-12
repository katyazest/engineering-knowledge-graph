## Purpose

The `canonical-ontology` capability defines the minimal local, in-memory Engineering KG model vocabulary used by MVP pipeline stages.

## Requirements

### Requirement: Canonical graph models exist
The system SHALL provide in-memory canonical graph models for nodes, edges, evidence records, code locators, Confluence page references, and graph snapshots.

#### Scenario: Models can be constructed
- **WHEN** local code constructs canonical graph objects with valid required fields
- **THEN** the objects are created without requiring external services, API keys, cloud services, database access, or OpenLore queries

#### Scenario: Snapshot contains graph collections
- **WHEN** local code constructs an empty graph snapshot
- **THEN** the snapshot exposes empty node, edge, and evidence collections

### Requirement: CodeLocator stores only code reference identity
The system SHALL represent code references with a CodeLocator containing only repository, revision, file, and symbol fields.

#### Scenario: CodeLocator excludes code graph details
- **WHEN** local code serializes a CodeLocator
- **THEN** the serialized representation contains repository, revision, file, and symbol
- **THEN** the serialized representation does not contain source code, call graph, dependency graph, class body, function body, or OpenLore analysis details

### Requirement: Confluence page reference stores only page identity
The system SHALL represent Confluence page references with a ConfluencePageRef containing only a page_id field.

#### Scenario: Confluence page reference excludes page content
- **WHEN** local code serializes a ConfluencePageRef
- **THEN** the serialized representation contains page_id
- **THEN** the serialized representation does not contain page content, page URL, comments, attachments, credentials, tokens, or Confluence API response data

### Requirement: Stable IDs are deterministic
The system SHALL provide deterministic stable ID generation for canonical ontology objects based on object kind and explicit identity parts.

#### Scenario: Same identity produces same ID
- **WHEN** local code generates a stable ID twice using the same object kind and identity parts
- **THEN** both generated IDs are identical

#### Scenario: Different identity produces different ID
- **WHEN** local code generates stable IDs using different object kinds or identity parts
- **THEN** the generated IDs are different

### Requirement: Canonical objects serialize deterministically
The system SHALL serialize canonical ontology objects to dictionaries or JSON-compatible data structures with stable values.

#### Scenario: Node serialization is stable
- **WHEN** local code serializes the same node multiple times
- **THEN** each serialized representation has the same stable fields and values

#### Scenario: Graph snapshot serialization is stable
- **WHEN** local code serializes the same graph snapshot multiple times
- **THEN** each serialized representation has the same stable fields and values

### Requirement: Ontology remains local and in-memory
The system SHALL keep the canonical ontology core local and in-memory for this MVP change.

#### Scenario: Ontology construction has no persistence side effects
- **WHEN** local code constructs and serializes canonical ontology objects
- **THEN** the system does not create or update LadybugDB storage, external systems, OpenLore indexes, Confluence pages, generated wiki content, or published artifacts

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
