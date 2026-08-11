## ADDED Requirements

### Requirement: Runner can execute workspace registry stage
The system SHALL allow the local pipeline runner to execute a workspace registry stage when a registry path is configured.

#### Scenario: Registry stage executes
- **WHEN** local code starts the pipeline runner with a valid `repo-index.yaml` registry path
- **THEN** the runner configures and executes the workspace registry stage
- **THEN** the returned pipeline result includes canonical graph objects produced from the workspace registry

#### Scenario: Registry stage is reported deterministically
- **WHEN** local code starts the pipeline runner with the same valid `repo-index.yaml` registry path multiple times
- **THEN** each returned pipeline result reports the same configured stages, executed stages, graph snapshot, and serialized status structure

#### Scenario: Bootstrap behavior remains available
- **WHEN** local code starts the pipeline runner without a registry path
- **THEN** the runner preserves the existing empty bootstrap behavior with zero configured stages, zero executed stages, and an empty canonical graph snapshot

### Requirement: Script wrapper can accept registry input
The system SHALL allow the local script wrapper to pass an optional workspace registry path into the reusable pipeline function.

#### Scenario: Script runs with registry path
- **WHEN** the user runs the build script with a local `repo-index.yaml` path
- **THEN** the script delegates to the reusable pipeline function with that registry path
- **THEN** the observable output reports successful registry-stage execution and graph counts

#### Scenario: Script remains local-first with registry input
- **WHEN** the build script runs with a local registry path in an environment without network access
- **THEN** the script completes without contacting external services or requiring credentials
