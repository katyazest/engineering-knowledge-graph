## Purpose

The `graph-derivation` capability defines deterministic local derivation of Engineering KG relationships from canonical graph snapshots.
## Requirements
### Requirement: Graph derivation runs from canonical graph snapshots
The system SHALL derive Engineering KG relationships from an existing canonical `GraphSnapshot` without reading source repositories, OpenLore indexes, OpenSpec files, external systems, generated documentation, or LadybugDB-native records directly.

#### Scenario: Derivation uses canonical graph input
- **WHEN** local code executes graph derivation with a canonical graph snapshot
- **THEN** derivation reads nodes, edges, evidence, locators, and properties from that snapshot
- **THEN** derivation does not read implementation source files, OpenLore analysis details, OpenSpec markdown bodies, Jira payloads, Bitbucket payloads, Confluence payloads, generated graph records, credentials, tokens, or external API responses

#### Scenario: Derivation remains local-first
- **WHEN** graph derivation runs in an environment without network access
- **THEN** derivation completes using only local project code and the provided canonical graph snapshot
- **THEN** derivation does not call cloud services, external APIs, MCP servers, compilation, publishing, semantic extraction, or LLM services

### Requirement: Derived relationships are deterministic
The system SHALL produce deterministic derived graph relationships for the same canonical graph snapshot and derivation rule set.

#### Scenario: Repeated derivation is stable
- **WHEN** local code runs graph derivation multiple times against the same canonical graph snapshot
- **THEN** each derivation result contains the same derived edge IDs, edge kinds, source IDs, target IDs, evidence IDs, properties, graph counts, and serialized metadata

#### Scenario: Derived edge identity is stable
- **WHEN** graph derivation creates a relationship between existing graph nodes
- **THEN** the derived edge ID is generated deterministically from explicit identity parts including derivation rule identity, relationship kind, source node ID, and target node ID
- **THEN** repeated derivation does not create duplicate graph edges for the same derived relationship

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

### Requirement: Derivation preserves source ownership boundaries
The system SHALL NOT derive authoritative implementation, service, or code traceability from manually maintained hints, names, or non-confident relationships alone.

#### Scenario: Manual related spec remains non-confident
- **WHEN** the input graph contains a non-confident related-spec relationship derived from manually maintained OpenSpec frontmatter
- **THEN** derivation preserves the relationship confidence value
- **THEN** derivation does not upgrade that relationship into authoritative traceability

#### Scenario: Repository hints do not create implementation mappings
- **WHEN** OpenSpec specification metadata contains a repository hint or a name matching a service or repository
- **THEN** derivation does not create implementation ownership, code reference, or service-specific traceability solely from that hint or name
- **THEN** OpenLore-owned code intelligence remains outside the derived graph unless represented as explicit canonical `CodeLocator` identity facts

### Requirement: Derivation reports deterministic metadata
The system SHALL return deterministic graph derivation metadata with status, derived relationship counts, skipped or unresolved input counts, and graph counts.

#### Scenario: Derivation metadata excludes source bodies and payloads
- **WHEN** graph derivation metadata is serialized
- **THEN** the metadata includes derivation status, rule counts, derived edge counts, skipped input counts, unresolved input counts, and graph counts
- **THEN** the metadata excludes full requirement bodies, full markdown artifact bodies, source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads

### Requirement: Derived relationships preserve complete derivation provenance
The system SHALL associate every derived relationship with first-class derived provenance that identifies the explicit derivation rule and the provenance identifiers of all admitted asserted/derived inputs used by that result. It SHALL not derive, omit, or rewrite an input's external observation metadata, and it SHALL reject derived output whose referenced input provenance is absent.

#### Scenario: Traceability derivation retains its provenance chain
- **WHEN** the OpenSpec change-to-specification derivation produces a traceability edge from evidenced asserted input
- **THEN** the derived edge retains the rule identity and referenced input provenance identifiers
- **THEN** the input evidence's source identity, revision, observation time, hash, and extractor metadata remain available through those references
