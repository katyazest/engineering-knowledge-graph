## ADDED Requirements

### Requirement: Runner can execute OpenSpec store source validation stage
The system SHALL allow the local pipeline runner to execute an OpenSpec store source validation stage after the workspace registry stage and before later OpenSpec extraction stages when that stage is configured.

#### Scenario: OpenSpec store source validation stage executes after registry stage
- **WHEN** local code starts the pipeline runner with a valid `repo-index.yaml` registry path whose configured stages include `workspace-registry` and `openspec-store-source`
- **THEN** the runner executes the workspace registry stage before the OpenSpec store source validation stage
- **THEN** the returned pipeline result reports both stages in deterministic configured and executed stage order

#### Scenario: OpenSpec store source validation uses configured requirements repository
- **WHEN** local code starts the pipeline runner with a valid registry path and configured OpenSpec store source validation stage
- **THEN** the OpenSpec store source validation stage cross-checks OpenSpec's registered store configuration against the requirements repository identified by `engineering_kg.store_repository`
- **THEN** the stage selects the registered store that matches the requirements repository when one or more stores are registered
- **THEN** the stage falls back to `engineering_kg.store_repository` only when no OpenSpec store is registered
- **THEN** the stage requires explicit store selection when registered stores and the requirements repository do not identify the same store
- **THEN** the stage does not resolve specifications or changes from the process current working directory or a nearest local OpenSpec root outside the selected store

#### Scenario: Registry-only behavior remains available
- **WHEN** local code starts the pipeline runner with a valid registry path whose configured stages include only `workspace-registry`
- **THEN** the runner preserves the existing registry-only behavior with only the workspace registry stage configured and executed

### Requirement: Runner reports deterministic OpenSpec store source validation metadata
The system SHALL expose deterministic OpenSpec store source validation metadata in the pipeline result when the validation stage executes.

#### Scenario: Pipeline result includes OpenSpec store source validation metadata
- **WHEN** local code starts the pipeline runner with a valid registry path and configured OpenSpec store source validation stage
- **THEN** the returned pipeline result includes validation metadata for the selection source, store id when available, store repository id, store repository role, resolved store repository path, resolved OpenSpec root, specs path, changes path, and validation status
- **THEN** the returned pipeline result excludes specification bodies, change bodies, source code, call graph, dependency graph, symbol bodies, generated graph records, credentials, tokens, and external API responses

#### Scenario: Pipeline result is deterministic across repeated runs
- **WHEN** local code starts the pipeline runner multiple times with the same valid registry path and configured OpenSpec store source validation stage
- **THEN** each returned pipeline result reports the same configured stages, executed stages, validation metadata, graph snapshot, and serialized status structure

### Requirement: Script wrapper can report OpenSpec store source validation
The system SHALL allow the local script wrapper to report OpenSpec store source validation through the reusable pipeline function without adding validation business logic to the script.

#### Scenario: Script runs with OpenSpec store source validation stage
- **WHEN** the user runs the build script with a local `repo-index.yaml` whose configured stages include `openspec-store-source`
- **THEN** the script delegates to the reusable pipeline function
- **THEN** the observable output reports successful workspace registry and OpenSpec store source validation-stage execution

#### Scenario: Script OpenSpec validation behavior remains local-first
- **WHEN** the build script runs with a local registry path and configured OpenSpec store source validation stage in an environment without network access
- **THEN** the script completes without contacting external services or requiring credentials
