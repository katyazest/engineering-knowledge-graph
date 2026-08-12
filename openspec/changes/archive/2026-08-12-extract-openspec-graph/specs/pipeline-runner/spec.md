## ADDED Requirements

### Requirement: Runner can execute OpenSpec graph extraction stage
The system SHALL allow the local pipeline runner to execute an OpenSpec graph extraction stage after OpenSpec store source validation when that stage is configured.

#### Scenario: OpenSpec graph extraction stage executes after store validation
- **WHEN** local code starts the pipeline runner with a valid `repo-index.yaml` whose configured stages include `workspace-registry`, `openspec-store-source`, and `openspec-graph-extraction`
- **THEN** the runner executes the workspace registry stage before the OpenSpec store source validation stage
- **THEN** the runner executes the OpenSpec store source validation stage before the OpenSpec graph extraction stage
- **THEN** the returned pipeline result reports all three stages in deterministic configured and executed stage order

#### Scenario: Extraction graph output is merged into pipeline snapshot
- **WHEN** the OpenSpec graph extraction stage executes successfully
- **THEN** the returned pipeline result includes canonical graph objects extracted from the validated OpenSpec store
- **THEN** the graph snapshot contains OpenSpec nodes, edges, and evidence before later persistence, derivation, validation, or MCP query stages run

#### Scenario: Store validation is required before extraction
- **WHEN** the configured stages include `openspec-graph-extraction` without a successful `openspec-store-source` result
- **THEN** the runner reports a deterministic stage ordering or dependency error before extraction reads OpenSpec files

### Requirement: Runner reports deterministic OpenSpec graph extraction metadata
The system SHALL expose deterministic OpenSpec graph extraction metadata in the pipeline result when the extraction stage executes.

#### Scenario: Pipeline result includes extraction metadata
- **WHEN** local code starts the pipeline runner with OpenSpec graph extraction configured
- **THEN** the returned pipeline result includes metadata for extracted durable specs, active changes, archived changes, requirements, scenarios, artifacts, unresolved related-spec references, and graph counts
- **THEN** the returned pipeline result excludes full requirement bodies, full markdown artifact bodies, implementation source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads

#### Scenario: Pipeline result is deterministic across repeated runs
- **WHEN** local code starts the pipeline runner multiple times with the same valid registry path and unchanged OpenSpec store files
- **THEN** each returned pipeline result reports the same configured stages, executed stages, extraction metadata, graph snapshot, and serialized status structure

### Requirement: Script wrapper can report OpenSpec graph extraction
The system SHALL allow the local script wrapper to report OpenSpec graph extraction through the reusable pipeline function without adding extraction business logic to the script.

#### Scenario: Script runs with OpenSpec graph extraction stage
- **WHEN** the user runs the build script with a local `repo-index.yaml` whose configured stages include `openspec-graph-extraction`
- **THEN** the script delegates to the reusable pipeline function
- **THEN** the observable output reports successful OpenSpec graph extraction-stage execution and graph counts

#### Scenario: Script extraction behavior remains local-first
- **WHEN** the build script runs with local OpenSpec graph extraction configured in an environment without network access
- **THEN** the script completes without contacting external services or requiring credentials
