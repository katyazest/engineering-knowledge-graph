## ADDED Requirements

### Requirement: Runner can execute complete MVP graph scenario
The system SHALL allow the local pipeline runner to execute the complete MVP graph stage sequence in one configured local run so an end-to-end scenario can verify workspace registry input, OpenSpec store input, persistence, derivation, validation, and query readiness together.

#### Scenario: Complete MVP graph stages execute in deterministic order
- **WHEN** local code starts the pipeline runner with a valid `repo-index.yaml`, a matching OpenSpec store source, configured graph-producing stages, a configured adapter-compatible LadybugDB persistence output path, configured `graph-derivation`, and configured `graph-integrity-validation`
- **THEN** the runner executes workspace registry loading before OpenSpec store source validation
- **THEN** the runner executes OpenSpec store source validation before OpenSpec graph extraction
- **THEN** the runner executes graph-producing stages before adapter-compatible LadybugDB persistence
- **THEN** the runner executes adapter-compatible LadybugDB persistence before graph derivation
- **THEN** the runner executes graph derivation before graph integrity validation
- **THEN** the returned pipeline result reports the configured stages and executed stages in deterministic order

#### Scenario: Complete MVP graph run returns query-ready graph
- **WHEN** the complete MVP graph stage sequence finishes successfully
- **THEN** the returned pipeline result includes the canonical graph snapshot returned after persistence readback, derivation, and graph integrity validation
- **THEN** local query APIs can inspect the final graph through canonical graph snapshots or the existing persistence readback boundary

#### Scenario: Complete MVP graph run remains local-first
- **WHEN** the complete MVP graph stage sequence runs in an environment without network access
- **THEN** the runner completes using only local project code, local fixture files, configured local paths, and the existing reusable Python modules
- **THEN** the runner does not require API keys, cloud services, OpenLore MCP calls, Jira calls, Bitbucket calls, Confluence calls, compilation, publishing, semantic extraction, LLM services, credentials, or external API calls

### Requirement: Runner reports complete MVP graph metadata without payload leakage
The system SHALL expose enough deterministic pipeline metadata for the complete MVP graph scenario to verify each executed stage while excluding source-owned payloads and sensitive values.

#### Scenario: Complete MVP graph metadata identifies stage results
- **WHEN** the local pipeline runner completes the full MVP graph stage sequence
- **THEN** the returned pipeline result includes deterministic metadata for OpenSpec store source validation, OpenSpec graph extraction, adapter-compatible LadybugDB persistence readback through the graph snapshot, graph derivation, graph integrity validation, configured stage count, executed stage count, and graph counts

#### Scenario: Complete MVP graph metadata excludes forbidden payloads
- **WHEN** the complete MVP graph pipeline result is serialized
- **THEN** the serialized result excludes source code, call graphs, dependency graphs, symbol bodies, OpenLore analysis payloads, full OpenSpec markdown bodies, Jira payloads, Bitbucket payloads, Confluence content, generated graph internals, credentials, tokens, and external API responses
