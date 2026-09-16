## ADDED Requirements

### Requirement: OpenSpec verification mappings are declared and resolve deterministically
The system SHALL read an optional version-1 `openspec/test-traceability.yaml` artifact only from the validated OpenSpec store. Each mapping SHALL identify exactly one existing canonical OpenSpec `requirement` or `scenario` by its capability and normalized requirement heading, with a normalized scenario heading required for a scenario target, and SHALL identify one or more test cases by payload-safe `verification_scope_id` and `test_case_key`. The mapping document SHALL be the sole source for creating scenario/requirement-to-test traceability in this capability; test-name similarity, requirement/scenario body text, source-path similarity, framework naming rules, and repository scanning SHALL NOT create or select a mapping. An absent artifact or a target with no entry SHALL mean no declared test mapping. Unsupported document versions, duplicate conflicting mapping identities, incomplete/unsafe test identities, non-unique target selectors, or target selectors that resolve to no extracted OpenSpec target SHALL fail the traceability admission before it emits a partial traceability delta.

#### Scenario: Explicit scenario mapping is emitted
- **WHEN** a validated store contains a version-1 mapping that exactly selects one extracted scenario and declares one payload-safe test scope/key
- **THEN** traceability admission emits the deterministic canonical test case and an evidenced, catalog-valid `VERIFIED_BY` relationship from that scenario to that test case
- **THEN** repeated admission of unchanged OpenSpec contents emits the same node, relationship, evidence, provenance, and ordering

#### Scenario: Similar names do not create a mapping
- **WHEN** an extracted requirement or scenario has no mapping entry but a test identifier, source file, or test display name is textually similar to its heading
- **THEN** traceability admission emits no test case or `VERIFIED_BY` relationship for that target
- **THEN** query status identifies the target as having no declared mapping rather than treating similarity as evidence

#### Scenario: Invalid declared mapping fails closed
- **WHEN** a mapping document has an unsupported version, malformed selector, unresolved target, duplicate conflict, blank/unsafe test identity, or a scenario selector without its required requirement selector
- **THEN** traceability admission returns a deterministic mapping diagnostic before merging its graph delta
- **THEN** it emits no partial mapping node, `VERIFIED_BY` edge, evidence, provenance, execution record, or cross-graph candidate from that document

### Requirement: Test execution observations are explicit and target mapped tests
The system SHALL admit a normalized test-execution observation only when it identifies an already declared mapped test case by the same verification scope/key, supplies a payload-safe test-run key, and carries complete source-artifact identity, source evidence, and first-class external provenance for the observation. Each admitted observation SHALL emit or reuse a source-neutral `test-run` and an evidenced, catalog-valid `EXECUTED_IN` relationship from its test case to that run. The system SHALL represent execution presence only; it SHALL NOT derive a pass/fail outcome, coverage measurement, execution date default, test result from a source path, or execution from mapping presence. Missing execution input SHALL leave a mapped test explicitly unexecuted, not invalid.

#### Scenario: Mapped test execution is represented
- **WHEN** normalized execution input identifies a declared mapped test case and contains a complete test-run identity and source evidence/provenance
- **THEN** admission emits deterministic `test-run` and `EXECUTED_IN` facts with the supplied evidence and provenance
- **THEN** the mapped test is queryable as executed without inferring an outcome or coverage value

#### Scenario: Mapping without execution remains distinct from no mapping
- **WHEN** a requirement or scenario has one or more admitted declared test mappings but none of those test cases has an admitted `EXECUTED_IN` relationship
- **THEN** query output reports the target as mapped and each such test as not executed
- **THEN** it does not report the target as unmapped or create a synthetic test-run

#### Scenario: Execution for an unknown test is rejected
- **WHEN** normalized execution input names a test scope/key for which this stage has no admitted declared mapping, or has incomplete identity, evidence, or provenance
- **THEN** admission rejects that input with a deterministic execution diagnostic and emits no test-run or `EXECUTED_IN` relationship for it

### Requirement: Reliable test-to-code resolution is exposed as non-implementing candidate evidence
The system SHALL accept an optional normalized test-to-code resolution only for an admitted mapped test case when the input identifies one complete revision-qualified `CodeLocator`, a payload-safe resolver and observation identity, complete evidence/provenance, and an explicit reliable basis of `static-reachability` or `runtime-execution`. The result SHALL create an attributable observed, untrusted `REFERENCES` cross-graph candidate from the test case to that locator with an explicit candidate lifecycle, so the existing cross-graph linking model can inspect it. The system SHALL emit no candidate for an unresolved, ambiguous, incomplete, repository/revision-inconsistent, or unprovenanced resolution; it SHALL not use a test name, file name, path, line number, source text, or an unverified tool result to select code. Test-to-code resolution and its evidence SHALL NOT create an `IMPLEMENTS` claim, trusted implementation projection, coverage conclusion, or verification mapping.

#### Scenario: Exact reachable-code resolution becomes an auditable candidate
- **WHEN** a mapped test has a normalized runtime-execution or static-reachability result with one complete code locator and complete attributed evidence/provenance
- **THEN** the graph retains one observed, untrusted `REFERENCES` candidate and candidate lifecycle for that test case and locator
- **THEN** the candidate is available through the existing cross-graph link projection without being exposed as implementation truth

#### Scenario: Non-resolved code result cannot become a candidate
- **WHEN** a resolver reports zero or multiple code targets, unavailable/invalid output, an incomplete locator, or a repository/revision mismatch
- **THEN** admission records a deterministic non-emission diagnostic and creates no code-link claim, observation, lifecycle record, ordinary edge, or trusted projection

### Requirement: Scenario-to-test traceability status is deterministic and payload-free
The reusable local query API SHALL return a deterministic traceability status for a requested represented `requirement` or `scenario`, including its admitted declared mapping identifiers, every mapped test's execution state, represented run identifiers, and any represented test-to-code candidate identifiers. A target with no admitted mapping SHALL be reported as `unmapped`; a mapped test with no represented execution SHALL be reported as `not-executed`; and a mapped test with one or more represented executions SHALL be reported as `executed`. The query SHALL not collapse these states based on name similarity, omit an unexecuted mapped test because another test executed, retrieve test systems, or expose test framework/CI payloads, reports, logs, output, source code, URLs, credentials, tokens, pass/fail outcome, or coverage.

#### Scenario: Mixed mappings retain per-test execution state
- **WHEN** a scenario has two mapped tests, one with an admitted run and one without an admitted run
- **THEN** query output returns both mappings in deterministic order and reports their states respectively as `executed` and `not-executed`
- **THEN** it does not label the scenario unmapped or infer an execution for the second test

#### Scenario: No declaration is reported separately
- **WHEN** a represented requirement or scenario has no admitted declared mapping
- **THEN** query output returns `unmapped` with an empty mapping collection
- **THEN** it does not return `not-executed`, a test candidate, or a fabricated execution record

### Requirement: Scenario-to-test traceability verification matrix bounds admission testing
The change SHALL document and exercise this verification matrix at mapping parsing/admission, execution and code-resolution normalization, merge, validation, pipeline, persistence/readback, and query boundaries. Cases outside it SHALL be reported as change candidates unless they violate another approved requirement or applicable baseline.

| Input class | Expected admission or projection behavior | Compatibility anchor |
| --- | --- | --- |
| Version-1 mapping with one exact existing requirement/scenario selector and one or more complete payload-safe test scope/keys | Emit deterministic test cases and `VERIFIED_BY` relationships with OpenSpec evidence/provenance | EKG-49 explicit traceability; EKG-48 verification identity and relation baseline |
| Target with no mapping entry | Query as `unmapped`; emit no test/run/verification relation | EKG-49 no-mapping distinction |
| Valid mapping with no execution observation | Query every mapped test as `not-executed`; emit no run | EKG-49 mapped-not-executed distinction |
| Valid mapping with complete execution observation for a declared test | Emit deterministic test run and `EXECUTED_IN`; query that test as `executed` without outcome/coverage | EKG-49 execution evidence; EKG-48 explicit execution baseline |
| Unsupported mapping version, malformed/unresolved/non-unique selector, duplicate conflict, unsafe identity, or execution for an undeclared test | Reject before the traceability delta merges; return deterministic diagnostic | EKG-49 declared/deterministic mapping boundary; graph-integrity baseline |
| Textually similar test name, source path, or heading with no exact declaration | Emit no mapping or execution inference | EKG-49 similarity is insufficient evidence |
| Exact reliable static-reachability/runtime-execution result with complete locator and evidence/provenance | Retain observed untrusted `REFERENCES` candidate for the mapped test only | EKG-49 code-link availability; EKG-41 observed-evidence trust boundary |
| Unresolved, ambiguous, malformed, unprovenanced, or repository/revision-inconsistent code resolution | Diagnostic only; no candidate, edge, lifecycle, or trusted projection | EKG-49 reliable-tooling boundary; OpenLore bridge conservative-resolution baseline |
| Test/test-code resolution supplied as implementation evidence, pass/fail result, coverage, or provider/source payload | Reject or omit from graph/query; never create trusted `IMPLEMENTS` | EKG-48 promotion safety; EKG-41 implementation-trust and payload-free baselines |
| Existing snapshot with no traceability mappings, executions, or candidates | Remains constructible, mergeable, persistable, and queryable | Existing empty-verification and generic-snapshot compatibility baseline |

#### Scenario: Matrix cases are executable
- **WHEN** automated local fixture tests exercise each applicable matrix row
- **THEN** every row has the documented admission, rejection, non-emission, persistence/readback, or query outcome
- **THEN** tests verify that test-name similarity and framework/CI/source payloads cannot produce or alter traceability facts
