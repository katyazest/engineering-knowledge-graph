## ADDED Requirements

### Requirement: Query API separates declared mapping from test execution status
The local query API SHALL expose a deterministic scenario-to-test traceability projection for a represented canonical `REQUIREMENT` or `SCENARIO`. The projection SHALL return `unmapped` only when no admitted declared mapping exists; otherwise it SHALL return every mapped `TEST_CASE` in stable order, each test's `executed` or `not-executed` state, represented `TEST_RUN` identifiers, mapping relationship/evidence/provenance references, and any represented reliable test-to-code cross-graph candidate identifiers and lifecycle/trust disposition. Query execution SHALL use only the supplied snapshot or persistence readback, shall not infer mappings/executions from names or text, and SHALL not expose test reports, framework/CI payloads, logs, output, source code, URLs, credentials, tokens, outcome, coverage, or implementation conclusions.

#### Scenario: Query reports unmapped target
- **WHEN** a caller requests scenario-to-test traceability for a represented requirement or scenario with no admitted mapping
- **THEN** the response reports `unmapped` and an empty deterministic mapping collection
- **THEN** it does not represent the target as an unexecuted test or infer a candidate from a similar test name

#### Scenario: Query reports executed and unexecuted mappings independently
- **WHEN** a caller requests a target that has multiple mapped tests with different represented execution relationships
- **THEN** the response includes every mapping in stable order and reports execution state and run IDs for each test independently
- **THEN** it does not infer pass/fail, coverage, or code implementation from execution presence
