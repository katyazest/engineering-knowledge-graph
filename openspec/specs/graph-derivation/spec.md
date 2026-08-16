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
The system SHALL derive traceability between OpenSpec change-scoped specification facts and durable specification facts only when both facts already exist in the canonical graph snapshot and share the same OpenSpec capability identity.

#### Scenario: Change-scoped spec maps to durable spec
- **WHEN** the graph contains an OpenSpec active or archived change node, a change-scoped spec node for capability `payments`, and a durable spec node for capability `payments`
- **THEN** derivation creates a deterministic relationship from the change or change-scoped spec context to the durable spec
- **THEN** the relationship preserves evidence or derivation metadata identifying the rule that created it

#### Scenario: Missing durable spec is not invented
- **WHEN** the graph contains a change-scoped spec node for a capability with no matching durable spec node
- **THEN** derivation does not invent a durable spec node
- **THEN** derivation reports the skipped or unresolved derivation input in deterministic metadata

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
