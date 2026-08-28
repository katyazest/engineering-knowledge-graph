## ADDED Requirements

### Requirement: Runner can execute PR code-candidate extraction after graph-producing inputs
The system SHALL allow the local pipeline runner to execute a `pr-code-candidate-extraction` stage after the configured stages that provide its `JIRA_STORY` engineering-change graph subjects and normalized PR change-set inputs, and before graph derivation and graph integrity validation. The stage SHALL merge only candidate claims, observations, lifecycle entries, provenance evidence, and deterministic extraction metadata into the canonical snapshot. If its required prior graph subjects or normalized input dependency is unavailable, the runner SHALL fail deterministically before candidate extraction and SHALL not emit partial candidates. An available subject with a kind other than `JIRA_STORY` SHALL be handled as a deterministic non-admission by the extractor, not as an eligible subject.

#### Scenario: Candidate stage executes in deterministic order
- **WHEN** a pipeline run is configured with its required graph-producing stages, normalized PR change-set input, `pr-code-candidate-extraction`, graph derivation, and graph integrity validation
- **THEN** the runner executes PR code-candidate extraction after its required inputs and before derivation and validation
- **THEN** the resulting graph and executed-stage list include the deterministic candidate-extraction output

#### Scenario: Missing candidate-stage dependency blocks extraction
- **WHEN** the pipeline configuration enables `pr-code-candidate-extraction` without an available normalized input dependency or required engineering-change graph subject
- **THEN** the runner reports a deterministic dependency error
- **THEN** the runner does not execute candidate extraction or later graph-mutation stages in that run

#### Scenario: Non-story prior subject does not produce a pipeline candidate
- **WHEN** the configured stage receives an otherwise eligible normalized change set whose available graph subject is a `WORKSPACE` or another non-`JIRA_STORY` kind
- **THEN** the stage completes with deterministic non-admission metadata for the ineligible subject kind
- **THEN** it merges no candidate claim, observation, or lifecycle entry for that change set

### Requirement: Runner reports payload-safe PR candidate extraction metadata
The pipeline result SHALL expose deterministic PR candidate extraction status, accepted change-set count, emitted candidate count, skipped-input count, admission diagnostics, and graph counts when the candidate stage executes. It SHALL not expose PR diff bodies, source code, symbol bodies, provider payloads, hierarchical or authority-bearing URL-like external links, credentials, tokens, or OpenLore data. A payload-safe opaque URI-shaped stable identifier, including `urn:example.org/link-42`, is permitted only as a stable identifier and is not an exposed external navigation link.

#### Scenario: Pipeline result exposes candidate stage metadata
- **WHEN** a configured PR code-candidate extraction stage completes
- **THEN** the pipeline result contains deterministic, payload-safe candidate-extraction metadata and final graph counts
- **THEN** repeated runs with unchanged normalized input produce the same stage metadata and graph snapshot
