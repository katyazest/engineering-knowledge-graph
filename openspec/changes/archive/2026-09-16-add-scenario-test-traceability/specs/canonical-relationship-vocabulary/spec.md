## MODIFIED Requirements

### Requirement: Source mappings are explicit and conservative
The system SHALL maintain a deterministic source-mapping table that identifies the source-specific input, canonical relationship kind, relationship classification, and unsupported input behavior. OpenSpec hierarchy headings map to `CONTAINS`; an OpenSpec change's evidenced specification assertion is support for derived `TRACES_TO`, not a trusted edge by itself; OpenSpec `related` metadata maps only to non-confident `REFERENCES`; and explicitly linked merged-PR changed-symbol observations map only to candidate `TOUCHES` claims. A version-1 OpenSpec declared test-traceability mapping may map only an exact extracted `REQUIREMENT` or `SCENARIO` to an explicit source-neutral `TEST_CASE` through `VERIFIED_BY`; a normalized execution observation for that declared test may map only to `EXECUTED_IN`; and a reliable normalized test-to-code resolution may map only to an observed candidate `REFERENCES` claim from that `TEST_CASE` to a complete `CodeLocator`. An explicitly normalized source-neutral verification assertion may map only to `CONTAINS`, `VERIFIED_BY`, `EXECUTED_IN`, or `VALIDATES` when it satisfies the verification endpoint and provenance contracts. A test/test-code association or verification-evidence input SHALL NOT map to `IMPLEMENTS`. No currently supported source mapping SHALL produce `IMPLEMENTS`, `DEPENDS_ON`, `OWNED_BY`, or `PROVIDES` without separately supplied catalog-conformant asserted or derived evidence.

#### Scenario: Supported sources map deterministically
- **WHEN** equivalent supported OpenSpec, declared test-traceability, normalized execution, normalized test-to-code, or merged-PR inputs are processed repeatedly
- **THEN** they produce the same mapped kind, classification, record identities, and ordering

#### Scenario: Declared test mapping has exact verification endpoints
- **WHEN** a version-1 mapping exactly resolves an extracted requirement or scenario and one declared test case with complete provenance
- **THEN** it emits only the directed `VERIFIED_BY` relationship from that target to the test case
- **THEN** it does not infer a reverse relation, a test execution, a code link, or an implementation relation

#### Scenario: Unsupported source claim is not guessed
- **WHEN** a supported adapter receives a relationship assertion for which no mapping exists
- **THEN** it emits no semantic edge or trusted link
- **THEN** it returns a deterministic diagnostic identifying the source mapping as unsupported
