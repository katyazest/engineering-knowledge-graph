## ADDED Requirements

### Requirement: Graph integrity validation enforces declared scenario-to-test traceability boundaries
Graph integrity validation SHALL validate that every `VERIFIED_BY` edge evidenced by the `openspec-test-traceability` mapping artifact is sourced by an extracted canonical `REQUIREMENT` or `SCENARIO`, targets a canonical `TEST_CASE`, has complete mapping evidence/provenance, and conforms to the catalog. It SHALL validate every `EXECUTED_IN` relation admitted by the scenario-test-traceability source and every `reliable-test-code-resolution` candidate for the mapped test/run or mapped `TEST_CASE` endpoint, complete locator, complete evidence/provenance, observed/untrusted classification, candidate lifecycle, and `REFERENCES` relation kind. It SHALL report deterministic diagnostics and reject invalid graph input before persistence or validation-required query use; it SHALL not repair selectors, infer a mapping/execution/code link, turn an unexecuted mapping into an error, promote test-code evidence to implementation truth, or invalidate an otherwise valid generic EKG-48 verification relation solely because it has no declared OpenSpec mapping source.

#### Scenario: Invalid declared traceability is rejected
- **WHEN** a snapshot contains a declared test mapping edge with an invalid endpoint, missing/incomplete mapping provenance, or a test-code candidate using another relation kind, trust disposition, lifecycle, or an unrepresented mapped test
- **THEN** validation returns invalid with deterministic affected-record diagnostics
- **THEN** persistence and validation-required queries expose no partial trusted relation or candidate from that invalid record

#### Scenario: Valid unexecuted mapping remains valid
- **WHEN** a snapshot contains a complete declared target-to-test mapping but no execution observation for that test
- **THEN** validation remains valid with no missing-execution error
- **THEN** query can report the mapped test as not executed
