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

### Requirement: Query API exposes represented verification traceability without inference
The local query API SHALL expose deterministic, payload-free projections of catalog-valid `VERIFIED_BY`, `EXECUTED_IN`, `VALIDATES`, and test-suite `CONTAINS` relationships adjacent to a requested represented graph object, and any represented cross-graph `verification_evidence_id` support reference. Query output SHALL retain only canonical IDs, kind, approved properties, relationship/evidence/provenance references, and supported locator identity fields in deterministic order. It SHALL not retrieve test systems, return framework/CI payloads, test logs, URLs, credentials, tokens, source code, source-code line content, inferred test coverage or outcome, automatically trusted verification, or an implementation conclusion not represented by an existing trusted projection.

#### Scenario: Query distinguishes verification support from implementation truth
- **WHEN** a caller queries a requirement with represented test/run/evidence facts and a cross-graph `VERIFIED_BY` candidate supported by verification evidence
- **THEN** the response distinguishes the verification relationships, support classification/lifecycle, and trusted-projection result deterministically
- **THEN** it does not label the candidate or related test-code association as `IMPLEMENTS`

### Requirement: Local evidence-bearing queries expose as-of freshness
The local query API SHALL return deterministic freshness status (`fresh`, `stale`, or `unknown`) and a safe reason/comparison basis for each represented provenance support in existing fact, traceability, PR-evidence, scenario-test, and cross-graph query results. It SHALL expose an evidence-to-provenance association and the current-evidence eligibility of the specific represented support, not merely a whole fact's unlabeled status. The caller SHALL be able to supply optional checked current-source revisions; without a matching check the status SHALL be `unknown`. An assessed `fresh` or `stale` status SHALL identify the check's `checked_at` instant and be described as an as-of result, not a claim about the source at response time. Existing fact fields, ordering, query filters, and explicit missing-result behavior SHALL remain compatible; no source lookup or payload exposure SHALL occur.

#### Scenario: Fact has freshness for each supporting observation
- **WHEN** a requirement query returns a fact with external evidence and a caller supplies one matching and one mismatching checked source revision for two different supporting artifacts
- **THEN** the result associates each evidence/provenance reference with its own as-of `fresh` or `stale` status and current-evidence eligibility
- **THEN** the pre-existing fact identity, evidence IDs, and provenance details remain available

#### Scenario: Traceability and cross-graph support retain unknown
- **WHEN** a caller requests traceability including an edge and cross-graph support without checked revisions
- **THEN** each represented support exposes `unknown` freshness and is not current-eligible
- **THEN** its stored trust/lifecycle disposition is not reclassified as current or ready

#### Scenario: Invalid checked input yields no partial query result
- **WHEN** a query receives conflicting or unsafe checked-revision entries
- **THEN** it returns a deterministic payload-safe input error rather than a partially assessed fact/relationship list

### Requirement: Current-required query consumers cannot silently count stale support
When a query consumer explicitly requires current evidence for a particular support, the query API SHALL use the shared current-evidence eligibility decision and SHALL expose that support as ineligible unless it has a fresh complete chain. Query results SHALL NOT present stale or unknown support as satisfying that explicit requirement, even if its stored trust or verification classification is otherwise positive. The API SHALL NOT silently impose a new freshness requirement on calls that do not request one.

#### Scenario: Explicit current-required check rejects stale support
- **WHEN** a caller evaluates a represented relationship's supporting evidence with current evidence required and every chain is stale or unknown
- **THEN** the relationship's support is not eligible for that check and the result retains the observed freshness statuses

### Requirement: Query API projects agent evidence-use status without changing graph facts
The local query API SHALL attach an additive deterministic evidence-use disposition and safe reason codes to represented traceability relationships and cross-graph claims, referencing their actual relationship/claim, evidence and provenance IDs and preserving existing per-support as-of freshness, trust, classification, lifecycle, ordering, filters and missing-result behavior. If a path is missing, unsupported, invalid or conflicting, it SHALL NOT synthesize a relationship or return an authoritative conclusion. An explicit current-required request SHALL apply the existing current-evidence eligibility guard to the specific required support; default calls SHALL not impose currentness on historical results. Validation-required calls on invalid graphs SHALL retain their existing safe diagnostic/no-partial-success behavior.

#### Scenario: Additive disposition leaves historical facts intact
- **WHEN** a caller queries valid represented declared support and a separate candidate or inferred support without checked revisions
- **THEN** existing relationship and provenance fields remain unchanged and each response distinguishes historical trust, `unknown` freshness and evidence-use eligibility
- **THEN** no candidate or inferred relationship is labeled authoritative implementation

#### Scenario: Missing relationship yields no replacement
- **WHEN** a caller queries traceability for a graph object without a represented relation to the proposed target
- **THEN** its existing empty/missing traceability behavior remains and no computed or name-derived relationship is returned

### Requirement: Query API explains bounded critical conclusions
The query API SHALL offer a local operation for a caller-proposed `implementation_ownership` or `change_readiness` conclusion, returning a deterministic `supported` or `unresolved` disposition, reason codes, and the represented evidence path or empty path. For implementation ownership, only the catalog-valid direct `OWNED_BY` relationship for the exact represented service or repository and requested target may be supported; other subjects or indirect attribution SHALL be unresolved. Change readiness SHALL remain unresolved without an approved readiness decision contract. Unsupported conclusion kinds, unsafe/malformed identifiers and malformed checked revisions SHALL fail with a safe input error and no partial result; a well-formed but absent graph subject/target SHALL be unresolved/`unknown`. The operation SHALL use existing validation and freshness mechanisms and SHALL not read external sources.

#### Scenario: Proposed owner is not guessed
- **WHEN** the caller requests ownership for an absent or unrelated owner ID
- **THEN** the response is `unresolved`/`unknown` with an empty path, even if that owner's name matches the repository

#### Scenario: Invalid input has no partial result
- **WHEN** a caller supplies an unsupported critical-conclusion kind or an invalid checked revision
- **THEN** the API returns a safe input error rather than a partial conclusion or source payload
