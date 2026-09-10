## Purpose

The `local-ekg-query-api` capability defines reusable local Python query interfaces for inspecting canonical Engineering KG graph facts without duplicating graph traversal logic in agents, scripts, or wrappers.
## Requirements
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
The system SHALL provide deterministic requirement query operations over canonical `requirement` facts and their evidence without exposing source-prefixed requirement kinds as a query contract.

#### Scenario: Canonical requirements are listed
- **WHEN** local code requests requirements from a graph containing canonical requirement nodes
- **THEN** the query API returns canonical identifiers, kinds, names, canonical properties, evidence identifiers, and supported locator identity fields
- **THEN** results are ordered deterministically by stable graph identity

#### Scenario: Requirements are filtered by provenance
- **WHEN** local code requests requirements filtered by an OpenSpec change or evidence reference
- **THEN** the query API filters canonical requirements through represented relationships and evidence provenance
- **THEN** it does not require, return, or infer an `openspec-requirement` node

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

### Requirement: Query API exposes canonical provenance without source payloads
The system SHALL expose each returned canonical fact's source and supported locator identity as provenance while excluding provider payload bodies and source-specific ontology aliases.

#### Scenario: OpenSpec provenance is returned
- **WHEN** a query result is supported by OpenSpec evidence
- **THEN** the result includes the evidence source, identifier, and supported OpenSpec locator identity fields
- **THEN** the result does not include full markdown content, an OpenSpec-prefixed canonical kind, or a duplicated source-owned domain object

### Requirement: Query results expose represented first-class provenance
The system SHALL return the complete represented provenance records and stable IDs associated with queried facts and traceability relationships, including source identity/revision, observation time, content-hash algorithm/digest, extractor identity/version, derivation rule, and input provenance references where present. Results SHALL be deterministic and SHALL exclude source bodies, provider payloads, credentials, tokens, and URLs.

#### Scenario: Query returns external and derived explanation chain
- **WHEN** a caller queries a fact or traceability relationship supported by external and derived provenance
- **THEN** the result includes its deterministic provenance records and reference chain
- **THEN** it does not return authoritative source content or infer unrepresented provenance

### Requirement: Query API exposes cross-graph evidence classification and trust disposition
The system SHALL expose deterministic cross-graph claim projections containing the claim identity and relationship kind, current lifecycle state, trusted-projection result, and each represented observation/lifecycle support record's origin, authoritative/derived status, confidence, trust disposition, and provenance reference. For observation records it SHALL expose only the admitted payload-safe opaque `strategy_id` and `observation_id`; identifiers rejected at admission SHALL not be serializable, persisted, or queryable. It SHALL distinguish a non-trusted `IMPLEMENTS` candidate from trusted implementation truth and SHALL not calculate a new confidence score, precedence winner, trust disposition, or implementation conclusion during query execution.

#### Scenario: Query returns classified non-trusted implementation candidate
- **WHEN** a caller queries a cross-graph `IMPLEMENTS` candidate supported by observed PR/file or LLM-only inferred evidence
- **THEN** the response returns the stored classification and non-trusted disposition
- **THEN** the response does not expose it as trusted implementation truth

### Requirement: Query API exposes represented PR evidence and scope without inferring coverage
The local query API SHALL return deterministic PR implementation-evidence projections containing the canonical PR identifier, repository identifier, base/head revisions, declared intended-change association, declared/observed relation origins, source/provenance references, and linked observed candidate identifiers when represented in the graph. It SHALL return only admitted payload-safe identity-level fields and SHALL not retrieve external systems, expose URLs or provider payloads, infer a requirement-to-file/symbol mapping, or label PR-derived candidates as `IMPLEMENTS` or trusted implementation truth.

#### Scenario: Query distinguishes declared association from observed candidates
- **WHEN** a caller queries represented PR evidence linked to an OpenSpec change or Jira work item with resolved symbol candidates
- **THEN** the response distinguishes the declared PR-to-intended-change relation from observed PR-to-repository and candidate evidence
- **THEN** it does not claim that every changed file/symbol or any unrepresented requirement is implemented

