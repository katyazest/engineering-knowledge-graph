## Purpose

The `canonical-relationship-vocabulary` capability defines the versioned, deterministic vocabulary and admission contracts for canonical Engineering KG relationships.
## Requirements
### Requirement: Stable canonical relationship catalog
The system SHALL expose one versioned, deterministic canonical relationship catalog for EKG semantic edges and trusted cross-graph links. The catalog SHALL define the following directed relationship kinds, their meanings, allowed source and target entity-kind sets, and cardinality: `TRACES_TO`, `IMPLEMENTS`, `VERIFIED_BY`, `EXECUTED_IN`, `VALIDATES`, `TOUCHES`, `DEPENDS_ON`, `REFERENCES`, `OWNED_BY`, and `PROVIDES`. It SHALL also retain `CONTAINS` as the structural containment relationship required by the existing OpenSpec and optional test-suite model. Relationship kinds outside this catalog SHALL NOT be admitted as canonical semantic edges or trusted links.

#### Scenario: Catalog is serializable and stable
- **WHEN** a caller reads the relationship catalog repeatedly
- **THEN** it receives the same kind names, direction, semantics, endpoint-kind sets, and cardinality definitions in deterministic order

#### Scenario: Unsupported relationship is not admitted
- **WHEN** a caller supplies an edge or trusted link with a kind not in the catalog
- **THEN** canonical admission rejects it with a deterministic vocabulary diagnostic

### Requirement: Relationship direction and endpoint contracts are enforced
The catalog SHALL define these directed endpoint contracts and maximum cardinality per ordered endpoint pair: `CONTAINS` (`SPECIFICATION` to `REQUIREMENT`, `REQUIREMENT` to `SCENARIO`, `TEST_SUITE` to `TEST_CASE`, or source-specific `OPENSPEC_*_CHANGE` to `OPENSPEC_ARTIFACT`; many-to-many); `TRACES_TO` (`OPENSPEC_*_CHANGE`, `REQUIREMENT`, `SCENARIO`, or `JIRA_STORY` to `SPECIFICATION`, `REQUIREMENT`, `SCENARIO`, or `JIRA_STORY`; many-to-many); `IMPLEMENTS` (`JIRA_STORY`, `PULL_REQUEST`, `SERVICE`, `REPOSITORY`, `CONTRACT`, or `BUSINESS_PROCESS` to `SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, or a complete `CodeLocator`; many-to-many); `VERIFIED_BY` (`REQUIREMENT`, `SCENARIO`, `JIRA_STORY`, `CONTRACT`, `SERVICE`, or `BUSINESS_PROCESS` to `SCENARIO`, `PULL_REQUEST`, `CONTRACT`, `TEST_CASE`, `TEST_SUITE`, or a complete `CodeLocator`; many-to-many); `EXECUTED_IN` (`TEST_CASE` or `TEST_SUITE` to `TEST_RUN`; many-to-many); `VALIDATES` (`VERIFICATION_EVIDENCE` to `TEST_CASE`, `TEST_SUITE`, `TEST_RUN`, `REQUIREMENT`, `SCENARIO`, `JIRA_STORY`, `CONTRACT`, `SERVICE`, or `BUSINESS_PROCESS`; many-to-many); `TOUCHES` (`JIRA_STORY` or `PULL_REQUEST` to `SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, or a complete `CodeLocator`; many-to-many); `DEPENDS_ON` (`SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, `JIRA_STORY`, `PULL_REQUEST`, `SPECIFICATION`, `REQUIREMENT`, or `SCENARIO` to the same set; many-to-many); `REFERENCES` (any canonical node kind to any canonical node kind or complete `CodeLocator`; many-to-many); `OWNED_BY` (`SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, `SPECIFICATION`, or `ADR` to `WORKSPACE`, `SERVICE`, or `EXTERNAL_SYSTEM`; exactly zero or one target per source); and `PROVIDES` (`SERVICE`, `REPOSITORY`, or `EXTERNAL_SYSTEM` to `CONTRACT`, `BUSINESS_PROCESS`, or `EXTERNAL_SYSTEM`; many-to-many). A relationship SHALL be interpreted only source-to-target as listed; its inverse SHALL NOT be inferred.

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
The system SHALL maintain a deterministic source-mapping table that identifies the source-specific input, canonical relationship kind, relationship classification, and unsupported input behavior. OpenSpec hierarchy headings map to `CONTAINS`; an OpenSpec change's evidenced specification assertion is support for derived `TRACES_TO`, not a trusted edge by itself; OpenSpec `related` metadata maps only to non-confident `REFERENCES`; and explicitly linked merged-PR changed-symbol observations map only to candidate `TOUCHES` claims. An explicitly normalized source-neutral verification assertion may map only to `CONTAINS`, `VERIFIED_BY`, `EXECUTED_IN`, or `VALIDATES` when it satisfies the verification endpoint and provenance contracts. A test/test-code association or verification-evidence input SHALL NOT map to `IMPLEMENTS`. No currently supported source mapping SHALL produce `IMPLEMENTS`, `DEPENDS_ON`, `OWNED_BY`, or `PROVIDES` without separately supplied catalog-conformant asserted or derived evidence.

#### Scenario: Supported sources map deterministically
- **WHEN** equivalent supported OpenSpec or normalized merged-PR inputs are processed repeatedly
- **THEN** they produce the same mapped kind, classification, record identities, and ordering

#### Scenario: Unsupported source claim is not guessed
- **WHEN** a supported adapter receives a relationship assertion for which no mapping exists
- **THEN** it emits no semantic edge or trusted link
- **THEN** it returns a deterministic diagnostic identifying the source mapping as unsupported

### Requirement: Relationship verification matrix bounds admission testing
The change SHALL document and test the following verification matrix: catalog kind with permitted ordered endpoints and complete provenance is admitted; catalog kind with reversed/disallowed endpoints is rejected; two `OWNED_BY` targets for one source are rejected; relationship kinds outside the current canonical vocabulary are rejected at current-format and in-memory admission; OpenSpec hierarchy, traceability support, related metadata, and PR changed-symbol observations are mapped as specified; candidate, rejected, and superseded claims are not trusted; and only an explicitly trusted, catalog-conformant claim is projected as trusted. A version-scoped persisted-snapshot migration may convert a retired relationship only when its registered source descriptor, deterministic mapping, complete retained identity/provenance data, and target catalog validation are all satisfied. It SHALL reject rather than guess a legacy alias, reversed direction, endpoint, mapping, or trust classification outside that approved migration. The EKG-38 greenfield compatibility exclusion is superseded for persisted-snapshot migration by Plane task `EKG-66`; other cases outside this matrix remain change candidates unless another approved requirement or baseline is violated.

#### Scenario: Matrix cases are executable
- **WHEN** the relationship and persisted-snapshot migration test suites run the approved matrix cases
- **THEN** every current-format admission case and version-scoped migration case has the documented outcome

#### Scenario: Current admission does not accept a legacy relationship
- **WHEN** a caller supplies a retired, aliased, or reversed relationship outside an approved migration input document
- **THEN** canonical admission rejects it with a deterministic vocabulary or endpoint-contract diagnostic
- **THEN** it does not convert the relationship merely because a migration for another source version exists

#### Scenario: Ambiguous legacy relationship is not migrated
- **WHEN** a supported migration source document contains a legacy relationship whose retained data cannot establish the registered direction, endpoint contract, or relationship meaning
- **THEN** migration rejects the complete snapshot with a deterministic compatibility or integrity diagnostic
- **THEN** no replacement snapshot contains a guessed relationship

### Requirement: Catalog admission applies evidence-trust eligibility to implementation relations
The system SHALL apply the cross-graph evidence-trust model after relationship kind and endpoint validation and before trusted-link projection. Catalog validity and complete provenance are necessary but not sufficient for trusted `IMPLEMENTS`: the implementation-trust boundary SHALL require qualifying authoritative declared support and an explicit trusted lifecycle decision. The catalog SHALL not treat confidence labels, observed PR/file mappings, or inferred support as aliases for declared implementation authority.

#### Scenario: Catalog-valid observed implementation claim remains non-trusted
- **WHEN** an `IMPLEMENTS` claim satisfies the catalog endpoint contract but has only observed PR/file or LLM-only inferred support
- **THEN** it remains non-trusted and is not counted as a trusted semantic implementation relationship

### Requirement: PR implementation-evidence relationship mappings distinguish declaration from observation
The relationship catalog SHALL define the directed `PULL_REQUEST REFERENCES OPENSPEC_ACTIVE_CHANGE|OPENSPEC_ARCHIVED_CHANGE|JIRA_STORY` mapping as a declared explicit-association relation and the directed `PULL_REQUEST TOUCHES REPOSITORY` mapping as an observed revision-evidence relation. It SHALL permit an `OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, or `JIRA_STORY` subject to carry an observed candidate `TOUCHES` cross-graph claim to a complete `CodeLocator`. The catalog revision SHALL advance with these mapping and endpoint changes and persistence SHALL admit only that current revision; no prior catalog mapping is converted or migrated. No PR mapping in this capability SHALL emit `IMPLEMENTS`, and unsupported/reversed endpoint pairs SHALL be rejected with deterministic diagnostics.

#### Scenario: Declared and observed PR relations use their distinct catalog mappings
- **WHEN** valid PR implementation evidence is associated explicitly with an active OpenSpec change, archived OpenSpec change, or Jira work item and references one repository
- **THEN** the graph admits the directed declared `REFERENCES` association and observed `TOUCHES` repository relation
- **THEN** a resolved symbol observation may produce only the catalog-valid observed candidate `TOUCHES` claim for that same intended-change scope

#### Scenario: PR evidence cannot use an implementation mapping
- **WHEN** a PR association, repository revision record, or changed-symbol observation requests `IMPLEMENTS`, a reversed endpoint order, or an unsupported intended-change kind
- **THEN** relationship admission returns a deterministic catalog diagnostic
- **THEN** it emits no semantic implementation edge or trusted implementation projection

