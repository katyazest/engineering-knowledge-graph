## ADDED Requirements

### Requirement: Runner admits optional local scenario-to-test traceability after OpenSpec extraction
The local pipeline runner SHALL support an optional `scenario-test-traceability` stage that executes only after successful `openspec-store-source` and `openspec-graph-extraction` stages and before persistence, derivation, and graph-integrity validation. The stage SHALL accept only local normalized execution and reliable code-resolution inputs supplied by its caller, merge its validated graph delta with the extracted OpenSpec graph, and expose deterministic payload-free counts and diagnostics for declared mappings, execution observations, code-link candidates, and skipped/non-emitted resolutions. If either prerequisite stage or required traceability source context is unavailable, the runner SHALL fail deterministically before the traceability stage emits a partial graph delta. Unconfigured pipeline behavior SHALL remain unchanged, and the stage SHALL not execute tests or call test frameworks, CI systems, Graphify, OpenLore, Jira, Bitbucket, or other external services.

#### Scenario: Traceability stage runs in dependency order
- **WHEN** a pipeline is configured with validated OpenSpec source, OpenSpec graph extraction, scenario-test-traceability, and later persistence/derivation/validation stages
- **THEN** the runner executes traceability admission after OpenSpec extraction and before each later graph mutation or validation stage
- **THEN** its result includes deterministic traceability metadata and the merged canonical graph

#### Scenario: Missing prerequisite blocks traceability admission
- **WHEN** a pipeline enables scenario-test-traceability without successful OpenSpec source/extraction context
- **THEN** the runner returns a deterministic dependency error before reading mapping or normalized traceability input
- **THEN** it does not execute tests, call external tools, or merge a partial traceability delta
