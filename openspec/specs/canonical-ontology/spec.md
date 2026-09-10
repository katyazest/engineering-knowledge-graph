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
The system SHALL provide deterministic stable ID generation for canonical ontology objects based on object kind and explicit source-independent identity parts.

#### Scenario: Same canonical identity produces same ID
- **WHEN** local code generates a stable ID twice using the same canonical object kind and natural-key identity parts
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
The system SHALL provide source-independent canonical graph vocabulary for specifications, requirements, and scenarios, and source-specific vocabulary only for OpenSpec active changes, archived changes, and change artifacts.

#### Scenario: Canonical OpenSpec-backed facts are available
- **WHEN** local code constructs graph nodes for facts extracted from OpenSpec specifications
- **THEN** it can represent the facts as `specification`, `requirement`, and `scenario` node kinds without an OpenSpec-prefixed domain kind
- **THEN** each node can retain OpenSpec source evidence and serialize deterministically without external services

#### Scenario: Source-owned OpenSpec entities remain available
- **WHEN** local code constructs graph nodes for an OpenSpec change or planning artifact
- **THEN** it can represent `openspec-active-change`, `openspec-archived-change`, and `openspec-artifact` node kinds
- **THEN** their OpenSpec lifecycle identity does not become the identity of a canonical specification, requirement, or scenario

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

### Requirement: Canonical facts preserve source provenance
The system SHALL attach evidence identifiers to canonical nodes and relationships and SHALL keep provider-specific locators and payload metadata outside canonical identity and domain vocabulary.

#### Scenario: Canonical fact has OpenSpec evidence
- **WHEN** an OpenSpec adapter emits a canonical specification, requirement, scenario, or relationship
- **THEN** the fact references OpenSpec evidence containing its supported locator identity
- **THEN** the canonical fact does not expose `openspec_identity`, scope, or source path as a required identity field

### Requirement: Canonical ontology represents cross-graph link claims and evidence
The system SHALL provide in-memory canonical models for cross-graph link claims, attributable candidate-evidence observations, their lifecycle states, and trusted semantic-link projections. These models SHALL use stable IDs and `CodeLocator` targets without adding OpenLore-specific graph or analysis models to the canonical ontology.

#### Scenario: Cross-graph models can be constructed locally
- **WHEN** local code constructs valid cross-graph link claims and candidate-evidence observations
- **THEN** the objects are created and serialized without requiring external services, API keys, database access, or OpenLore queries

#### Scenario: Existing graph construction remains compatible
- **WHEN** local code constructs a graph snapshot using only existing node, edge, and evidence collections
- **THEN** the snapshot remains constructible and serializes with empty cross-graph link collections

### Requirement: Graph snapshots merge cross-graph link data safely
The system SHALL include cross-graph link claims and candidate-evidence observations in graph snapshot merge semantics. It SHALL coalesce identical stable records, accumulate compatible candidate-evidence observations for the same claim, and reject conflicting immutable record values or dangling claim references.

#### Scenario: Compatible cross-graph snapshots merge
- **WHEN** two snapshots contain the same compatible claim and different valid observations that reference it
- **THEN** the merged snapshot contains one claim and all distinct observations in deterministic order

#### Scenario: Conflicting cross-graph snapshot data is rejected
- **WHEN** two snapshots contain records with the same cross-graph stable identifier but conflicting immutable values
- **THEN** snapshot merging raises a deterministic conflict error

### Requirement: Ontology uses catalog-defined relationship values
The canonical ontology SHALL expose relationship kind values and relationship metadata through the canonical relationship catalog. It SHALL preserve stable IDs for unchanged valid canonical relationship identities and SHALL not encode source-specific mapping labels, candidate lifecycle state, confidence, display names, or evidence content into semantic relationship identity. It SHALL persist and read back only the current canonical relationship representation; legacy aliases and reversed relationship encodings are not accepted or migrated. EKG-38 is anchored to the greenfield baseline that EKG has no historical deployment or persisted graph data, so it SHALL NOT add compatibility, migration, backup, or rollback behavior; any such behavior requires a future explicit requirement supported by concrete evidence of pre-canonical data.

#### Scenario: Canonical identity remains stable
- **WHEN** a valid relationship is represented by its catalog-defined canonical kind and unchanged endpoints
- **THEN** its stable identity remains unchanged after the catalog is introduced

#### Scenario: Canonical relationship format round-trips
- **WHEN** a graph containing only catalog-valid current canonical relationships is persisted and read back
- **THEN** the readback preserves its canonical kinds, ordered endpoints, and stable identities deterministically
- **THEN** it does not apply a legacy-alias or reversed-relationship conversion

#### Scenario: Candidate state does not change semantic identity
- **WHEN** a supported cross-graph claim has the same subject, catalog kind, and complete `CodeLocator` target at different candidate lifecycle states
- **THEN** its claim identity remains unchanged

### Requirement: Canonical ontology represents typed pull-request implementation evidence
The canonical ontology SHALL provide immutable, deterministic, payload-free records for revision-bounded pull-request evidence, its explicit intended-change association, and a PR reference from an observed cross-graph candidate. A represented PR SHALL be a canonical `PULL_REQUEST` node with a stable identity separate from display data and must retain its repository node reference, base revision, head revision, explicit source evidence reference, and provenance reference. A PR-scoped candidate reference SHALL not change the identity of the underlying cross-graph claim. A graph snapshot containing no PR implementation-evidence records SHALL remain constructible with empty PR-evidence collections.

#### Scenario: PR evidence is modeled without provider payloads
- **WHEN** local code constructs valid typed PR implementation evidence and an association to an eligible intended change
- **THEN** the canonical snapshot serializes deterministic PR, relation-origin, source-reference, and provenance identifiers with base/head revision values
- **THEN** it does not serialize provider models, PR titles/descriptions, source bodies, diff bodies, URLs, credentials, tokens, or source code

#### Scenario: PR source reference does not change candidate identity
- **WHEN** equivalent `TOUCHES` claims have the same intended-change subject and complete code locator but different valid attributable PR observations
- **THEN** the claims retain the same existing stable claim identity and accumulate distinct PR-scoped observations
- **THEN** each observation retains its own PR and provenance reference

