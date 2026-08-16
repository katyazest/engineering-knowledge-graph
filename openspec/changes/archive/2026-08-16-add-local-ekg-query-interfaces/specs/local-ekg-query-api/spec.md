## ADDED Requirements

### Requirement: Query API reads canonical graph snapshots
The system SHALL provide a reusable local Python query API that reads Engineering KG facts from canonical `GraphSnapshot` data without requiring network access, API keys, cloud services, external MCP servers, source repository reads, OpenLore queries, Jira calls, Bitbucket calls, Confluence calls, compilation, publishing, semantic extraction, or LLM services.

#### Scenario: Query API starts from snapshot
- **WHEN** local code constructs the query API from a canonical `GraphSnapshot`
- **THEN** the query API can inspect nodes, edges, evidence records, properties, and locator identity fields from that snapshot
- **THEN** the query API does not read source repositories, generated documentation, external systems, credentials, tokens, source code, call graphs, dependency graphs, symbol bodies, or OpenLore analysis payloads

#### Scenario: Query API remains local-first
- **WHEN** the query API is used in an environment without network access
- **THEN** query execution completes using only local project code and the provided canonical graph input

### Requirement: Query API reads persisted local graph store
The system SHALL allow local code to construct the query API from the existing LadybugDB-compatible Engineering KG store by using the canonical persistence readback boundary.

#### Scenario: Query API reads through persistence boundary
- **WHEN** local code constructs the query API from a configured local graph store path
- **THEN** the query API reads the graph through the existing canonical persistence readback function
- **THEN** query behavior is based on the returned `GraphSnapshot`

#### Scenario: Query API avoids storage internals
- **WHEN** the query API reads a persisted graph
- **THEN** it does not parse LadybugDB-compatible storage files directly
- **THEN** it does not depend on LadybugDB-native APIs outside the existing persistence boundary

### Requirement: Query API lists requirements deterministically
The system SHALL provide deterministic requirement query operations over canonical requirement and OpenSpec requirement facts.

#### Scenario: Requirements are listed
- **WHEN** local code requests requirements from a graph containing requirement nodes
- **THEN** the query API returns requirement identifiers, kinds, names, properties, evidence identifiers, and supported locator identity fields
- **THEN** results are ordered deterministically by stable graph identity

#### Scenario: Requirements can be filtered by graph facts
- **WHEN** local code requests requirements filtered by an explicit graph fact such as capability, service, OpenSpec change, or evidence reference
- **THEN** the query API returns only requirements connected by existing canonical or derived graph relationships
- **THEN** the query API does not infer missing relationships from names, repository hints, prompt context, or service-specific assumptions

### Requirement: Query API lists services deterministically
The system SHALL provide deterministic service query operations over canonical workspace registry service and repository facts.

#### Scenario: Services are listed
- **WHEN** local code requests services from a graph containing service nodes
- **THEN** the query API returns service identifiers, names, properties, related repository identifiers when present, and evidence identifiers
- **THEN** results are ordered deterministically by stable graph identity

#### Scenario: Service query preserves service boundaries
- **WHEN** local code queries services and their related facts
- **THEN** the query API returns only relationships represented in the graph
- **THEN** it does not merge logic across repositories or services that are not connected by canonical graph relationships

### Requirement: Query API lists OpenSpec changes deterministically
The system SHALL provide deterministic query operations for active and archived OpenSpec change facts.

#### Scenario: Changes are listed
- **WHEN** local code requests OpenSpec changes from a graph containing active or archived change nodes
- **THEN** the query API returns change identifiers, kinds, names, properties, artifact links, touched specification links, traceability links, and evidence identifiers represented in the graph
- **THEN** results are ordered deterministically by stable graph identity

#### Scenario: Missing durable specification link is explicit
- **WHEN** a change-scoped specification has no derived or canonical link to a durable specification
- **THEN** the query API reports the absence of that link explicitly
- **THEN** it does not invent a durable specification or traceability relationship

### Requirement: Query API returns traceability from existing graph relationships
The system SHALL provide traceability query operations based only on canonical edges and deterministic derived edges already present in the graph.

#### Scenario: Traceability is returned for a graph object
- **WHEN** local code requests traceability for a known graph object identifier
- **THEN** the query API returns connected source and target graph object identifiers, edge kinds, confidence values when present, evidence identifiers, and locator identity fields
- **THEN** results are ordered deterministically by relationship identity

#### Scenario: Non-confident relationships remain non-confident
- **WHEN** traceability includes a non-confident relationship from the graph
- **THEN** the query API returns the relationship confidence value as stored
- **THEN** it does not upgrade the relationship to authoritative traceability

### Requirement: Query API output excludes source-owned payloads
The system SHALL exclude source-owned payload bodies and sensitive values from serialized query results.

#### Scenario: Code locator fields are returned without code intelligence
- **WHEN** a query result includes a `CodeLocator`
- **THEN** the serialized result contains repository, revision, file, and symbol
- **THEN** the serialized result excludes source code, call graphs, dependency graphs, class bodies, function bodies, symbol bodies, OpenLore analysis details, credentials, tokens, and external API responses

#### Scenario: External references are returned without payload bodies
- **WHEN** a query result includes OpenSpec, Confluence, Jira, Bitbucket, or other external-system reference identities represented in the graph
- **THEN** the serialized result includes only graph-stored identity, properties, evidence identifiers, and supported locator identity fields
- **THEN** the serialized result excludes full markdown bodies, page content, comments, attachments, API payloads, credentials, and tokens
