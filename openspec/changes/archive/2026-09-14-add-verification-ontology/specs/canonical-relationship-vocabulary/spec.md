## MODIFIED Requirements

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

### Requirement: Source mappings are explicit and conservative
The system SHALL maintain a deterministic source-mapping table that identifies the source-specific input, canonical relationship kind, relationship classification, and unsupported input behavior. OpenSpec hierarchy headings map to `CONTAINS`; an OpenSpec change's evidenced specification assertion is support for derived `TRACES_TO`, not a trusted edge by itself; OpenSpec `related` metadata maps only to non-confident `REFERENCES`; and explicitly linked merged-PR changed-symbol observations map only to candidate `TOUCHES` claims. An explicitly normalized source-neutral verification assertion may map only to `CONTAINS`, `VERIFIED_BY`, `EXECUTED_IN`, or `VALIDATES` when it satisfies the verification endpoint and provenance contracts. A test/test-code association or verification-evidence input SHALL NOT map to `IMPLEMENTS`. No currently supported source mapping SHALL produce `IMPLEMENTS`, `DEPENDS_ON`, `OWNED_BY`, or `PROVIDES` without separately supplied catalog-conformant asserted or derived evidence.

#### Scenario: Supported sources map deterministically
- **WHEN** equivalent supported OpenSpec, normalized merged-PR, or normalized verification inputs are processed repeatedly
- **THEN** they produce the same mapped kind, classification, record identities, and ordering

#### Scenario: Unsupported source claim is not guessed
- **WHEN** a supported adapter receives a relationship assertion for which no mapping exists
- **THEN** it emits no semantic edge or trusted link
- **THEN** it returns a deterministic diagnostic identifying the source mapping as unsupported
