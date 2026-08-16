## ADDED Requirements

### Requirement: Runner can execute graph derivation stage
The system SHALL allow the local pipeline runner to execute a graph derivation stage after configured graph-producing and persistence stages when `graph-derivation` is configured.

#### Scenario: Graph derivation runs after persistence readback
- **WHEN** local code starts the pipeline runner with a valid `repo-index.yaml`, configured graph-producing stages, a configured adapter-compatible LadybugDB persistence output path, and configured `graph-derivation`
- **THEN** the runner executes graph-producing stages before the adapter-compatible LadybugDB persistence stage
- **THEN** the runner executes the adapter-compatible LadybugDB persistence stage before the graph derivation stage
- **THEN** graph derivation receives the canonical graph snapshot returned by persistence readback
- **THEN** the returned pipeline result reports all executed stages in deterministic configured and executed stage order

#### Scenario: Graph derivation runs without persistence when persistence is not configured
- **WHEN** local code starts the pipeline runner with configured graph-producing stages and configured `graph-derivation` but no persistence output path
- **THEN** graph derivation receives the in-memory canonical graph snapshot produced by the prior configured stages
- **THEN** the runner does not create or update LadybugDB storage

#### Scenario: Empty graph derivation is deterministic
- **WHEN** local code starts the pipeline runner with configured `graph-derivation` and no configured graph-producing stage
- **THEN** graph derivation runs against an empty canonical graph snapshot
- **THEN** the returned pipeline result reports zero derived relationships and deterministic derivation metadata

### Requirement: Runner reports deterministic graph derivation metadata
The system SHALL expose deterministic graph derivation metadata in the pipeline result when the graph derivation stage executes.

#### Scenario: Pipeline result includes derivation metadata
- **WHEN** local code starts the pipeline runner with graph derivation configured
- **THEN** the returned pipeline result includes graph derivation metadata with status, derived relationship counts, skipped input counts, unresolved input counts, and graph counts
- **THEN** the returned pipeline result excludes full requirement bodies, full markdown artifact bodies, implementation source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads

#### Scenario: Pipeline derivation result is deterministic across repeated runs
- **WHEN** local code starts the pipeline runner multiple times with the same registry path, unchanged source files, unchanged persistence input, and configured graph derivation stage
- **THEN** each returned pipeline result reports the same configured stages, executed stages, derivation metadata, graph snapshot, and serialized status structure

### Requirement: Runner can execute graph integrity validation stage
The system SHALL allow the local pipeline runner to execute graph integrity validation after all prior configured graph mutation stages and before later query wrapper stages when `graph-integrity-validation` is configured.

#### Scenario: Validation runs after derivation
- **WHEN** local code starts the pipeline runner with configured graph-producing stages, configured `graph-derivation`, and configured `graph-integrity-validation`
- **THEN** the runner executes graph derivation before graph integrity validation
- **THEN** graph integrity validation receives the canonical graph snapshot returned by graph derivation
- **THEN** the returned pipeline result reports both stages in deterministic configured and executed stage order

#### Scenario: Validation runs without derivation
- **WHEN** local code starts the pipeline runner with configured graph-producing stages and configured `graph-integrity-validation` but without configured `graph-derivation`
- **THEN** graph integrity validation receives the canonical graph snapshot produced by the prior configured stages
- **THEN** the returned pipeline result reports graph integrity validation metadata

#### Scenario: Invalid graph blocks later stages
- **WHEN** graph integrity validation returns an invalid status during a pipeline run
- **THEN** the runner reports graph integrity validation failure deterministically
- **THEN** the runner does not execute later query wrapper, projection, wiki, or MCP wrapper stages in that run

### Requirement: Runner reports deterministic graph integrity validation metadata
The system SHALL expose deterministic graph integrity validation metadata in the pipeline result when graph integrity validation executes.

#### Scenario: Pipeline result includes validation metadata
- **WHEN** local code starts the pipeline runner with graph integrity validation configured
- **THEN** the returned pipeline result includes validation metadata with status, diagnostics, severity counts, and graph counts
- **THEN** the returned pipeline result excludes full requirement bodies, full markdown artifact bodies, implementation source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads

#### Scenario: Pipeline validation result is deterministic across repeated runs
- **WHEN** local code starts the pipeline runner multiple times with the same registry path, unchanged source files, unchanged persistence input, and configured graph integrity validation stage
- **THEN** each returned pipeline result reports the same configured stages, executed stages, validation metadata, graph snapshot, and serialized status structure

### Requirement: Script wrapper can report graph derivation and validation
The system SHALL allow the local script wrapper to report graph derivation and graph integrity validation through the reusable pipeline function without adding graph rule logic to the script.

#### Scenario: Build script reports derivation and validation stages
- **WHEN** the user runs the build script with a local `repo-index.yaml` whose configured stages include `graph-derivation` and `graph-integrity-validation`
- **THEN** the script delegates to the reusable pipeline function
- **THEN** the observable output reports graph derivation and graph integrity validation stage execution and metadata

#### Scenario: Script derivation and validation behavior remains local-first
- **WHEN** the build script runs with local graph derivation and graph integrity validation configured in an environment without network access
- **THEN** the script completes without contacting external services or requiring credentials
