## Purpose

The `canonical-relationship-vocabulary` capability defines the versioned, deterministic vocabulary and admission contracts for canonical Engineering KG relationships.

## Requirements

### Requirement: Stable canonical relationship catalog
The system SHALL expose one versioned, deterministic canonical relationship catalog for EKG semantic edges and trusted cross-graph links. The catalog SHALL define the following directed relationship kinds, their meanings, allowed source and target entity-kind sets, and cardinality: `TRACES_TO`, `IMPLEMENTS`, `VERIFIED_BY`, `TOUCHES`, `DEPENDS_ON`, `REFERENCES`, `OWNED_BY`, and `PROVIDES`. It SHALL also retain `CONTAINS` as the structural containment relationship required by the existing OpenSpec model. Relationship kinds outside this catalog SHALL NOT be admitted as canonical semantic edges or trusted links.

#### Scenario: Catalog is serializable and stable
- **WHEN** a caller reads the relationship catalog repeatedly
- **THEN** it receives the same kind names, direction, semantics, endpoint-kind sets, and cardinality definitions in deterministic order

#### Scenario: Unsupported relationship is not admitted
- **WHEN** a caller supplies an edge or trusted link with a kind not in the catalog
- **THEN** canonical admission rejects it with a deterministic vocabulary diagnostic

### Requirement: Relationship direction and endpoint contracts are enforced
The catalog SHALL define these directed endpoint contracts and maximum cardinality per ordered endpoint pair: `CONTAINS` (`SPECIFICATION` to `REQUIREMENT`, `REQUIREMENT` to `SCENARIO`, or source-specific `OPENSPEC_*_CHANGE` to `OPENSPEC_ARTIFACT`; many-to-many); `TRACES_TO` (`OPENSPEC_*_CHANGE`, `REQUIREMENT`, `SCENARIO`, or `JIRA_STORY` to `SPECIFICATION`, `REQUIREMENT`, `SCENARIO`, or `JIRA_STORY`; many-to-many); `IMPLEMENTS` (`JIRA_STORY`, `PULL_REQUEST`, `SERVICE`, `REPOSITORY`, `CONTRACT`, or `BUSINESS_PROCESS` to `SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, or a complete `CodeLocator`; many-to-many); `VERIFIED_BY` (`REQUIREMENT`, `SCENARIO`, `JIRA_STORY`, `CONTRACT`, `SERVICE`, or `BUSINESS_PROCESS` to `SCENARIO`, `PULL_REQUEST`, `CONTRACT`, or a complete `CodeLocator`; many-to-many); `TOUCHES` (`JIRA_STORY` or `PULL_REQUEST` to `SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, or a complete `CodeLocator`; many-to-many); `DEPENDS_ON` (`SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, `JIRA_STORY`, `PULL_REQUEST`, `SPECIFICATION`, `REQUIREMENT`, or `SCENARIO` to the same set; many-to-many); `REFERENCES` (any canonical node kind to any canonical node kind or complete `CodeLocator`; many-to-many); `OWNED_BY` (`SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, `SPECIFICATION`, or `ADR` to `WORKSPACE`, `SERVICE`, or `EXTERNAL_SYSTEM`; exactly zero or one target per source); and `PROVIDES` (`SERVICE`, `REPOSITORY`, or `EXTERNAL_SYSTEM` to `CONTRACT`, `BUSINESS_PROCESS`, or `EXTERNAL_SYSTEM`; many-to-many). A relationship SHALL be interpreted only source-to-target as listed; its inverse SHALL NOT be inferred.

#### Scenario: Valid directed relationship is admitted
- **WHEN** a relationship has a catalog kind, valid source and target kinds, complete required provenance, and does not exceed its cardinality
- **THEN** the system admits it without reversing its endpoints or creating an inverse edge

#### Scenario: Reversed or invalid endpoint is rejected
- **WHEN** a relationship uses a valid catalog kind but its ordered endpoint kinds are not permitted
- **THEN** the system rejects it with a deterministic endpoint-contract diagnostic

#### Scenario: Single-owner cardinality is rejected
- **WHEN** a source has two distinct admitted `OWNED_BY` targets
- **THEN** the system rejects the graph with a deterministic cardinality diagnostic

### Requirement: Trusted semantic relationships are separate from candidates and evidence
The system SHALL represent a catalog-defined relationship as a trusted semantic edge or trusted cross-graph link only when its asserted or derived provenance is complete and its trust status is explicit. Candidate observations, asserted source mappings awaiting derivation, raw evidence records, and rejected or superseded cross-graph claims SHALL remain non-semantic support records and SHALL NOT be serialized, queried, or counted as trusted canonical relationships.

#### Scenario: Candidate observation remains non-semantic
- **WHEN** a candidate cross-graph claim has valid evidence but its current lifecycle is `candidate`
- **THEN** it is retained as candidate evidence
- **THEN** no trusted `IMPLEMENTS`, `VERIFIED_BY`, `TOUCHES`, `REFERENCES`, or other semantic relationship is emitted from it

#### Scenario: Explicitly trusted cross-graph claim is constrained by the catalog
- **WHEN** a cross-graph claim is explicitly trusted and its relationship kind and subject kind satisfy a catalog contract for a `CodeLocator` target
- **THEN** the system exposes one trusted semantic link with its supporting evidence and provenance references

### Requirement: Source mappings are explicit and conservative
The system SHALL maintain a deterministic source-mapping table that identifies the source-specific input, canonical relationship kind, relationship classification, and unsupported input behavior. OpenSpec hierarchy headings map to `CONTAINS`; an OpenSpec change's evidenced specification assertion is support for derived `TRACES_TO`, not a trusted edge by itself; OpenSpec `related` metadata maps only to non-confident `REFERENCES`; and explicitly linked merged-PR changed-symbol observations map only to candidate `TOUCHES` claims. No currently supported source mapping SHALL produce `IMPLEMENTS`, `VERIFIED_BY`, `DEPENDS_ON`, `OWNED_BY`, or `PROVIDES` without separately supplied catalog-conformant asserted or derived evidence.

#### Scenario: Supported sources map deterministically
- **WHEN** equivalent supported OpenSpec or normalized merged-PR inputs are processed repeatedly
- **THEN** they produce the same mapped kind, classification, record identities, and ordering

#### Scenario: Unsupported source claim is not guessed
- **WHEN** a supported adapter receives a relationship assertion for which no mapping exists
- **THEN** it emits no semantic edge or trusted link
- **THEN** it returns a deterministic diagnostic identifying the source mapping as unsupported

### Requirement: Relationship verification matrix bounds admission testing
The change SHALL document and test the following verification matrix: catalog kind with permitted ordered endpoints and complete provenance is admitted; catalog kind with reversed/disallowed endpoints is rejected; two `OWNED_BY` targets for one source are rejected; relationship kinds outside the current canonical vocabulary are rejected rather than migrated; OpenSpec hierarchy, traceability support, related metadata, and PR changed-symbol observations are mapped as specified; candidate, rejected, and superseded claims are not trusted; and only an explicitly trusted, catalog-conformant claim is projected as trusted. The matrix is anchored to the EKG-38 greenfield baseline that EKG has no historical deployment or persisted graph data; it therefore includes no compatibility, migration, backup, or rollback case. Such a case is a change candidate unless a future explicit requirement is supported by concrete evidence of pre-canonical data. Other cases outside this matrix SHALL be reported as change candidates unless another approved requirement or baseline is violated.

#### Scenario: Matrix cases are executable
- **WHEN** the relationship test suite runs the approved matrix cases
- **THEN** every case has the documented admission or rejection outcome

#### Scenario: No historical-data compatibility is assumed
- **WHEN** EKG-38 verification considers compatibility, migration, backup, or rollback work for relationship data
- **THEN** it treats that work as out of scope for the documented greenfield baseline
- **THEN** it identifies the work as requiring a future explicit requirement and concrete evidence of pre-canonical data
