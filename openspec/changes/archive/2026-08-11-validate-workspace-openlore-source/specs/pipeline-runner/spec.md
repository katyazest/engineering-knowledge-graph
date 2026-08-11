## ADDED Requirements

### Requirement: Runner can execute workspace OpenLore source validation stage
The system SHALL allow the local pipeline runner to execute a workspace OpenLore source validation stage after the workspace registry stage when that stage is configured.

#### Scenario: OpenLore source validation stage executes after registry stage
- **WHEN** local code starts the pipeline runner with a valid `repo-index.yaml` registry path whose configured stages include `workspace-registry` and `workspace-openlore-source`
- **THEN** the runner executes the workspace registry stage before the workspace OpenLore source validation stage
- **THEN** the returned pipeline result reports both stages in deterministic configured and executed stage order

#### Scenario: OpenLore source validation stage preserves registry graph output
- **WHEN** local code starts the pipeline runner with a valid registry path and configured workspace OpenLore source validation stage
- **THEN** the returned pipeline result includes the canonical graph snapshot produced from the workspace registry
- **THEN** the workspace OpenLore source validation stage does not add OpenLore code graph contents to the canonical graph snapshot

#### Scenario: Registry-only behavior remains available
- **WHEN** local code starts the pipeline runner with a valid registry path whose configured stages include only `workspace-registry`
- **THEN** the runner preserves the existing registry-only behavior with only the workspace registry stage configured and executed

### Requirement: Runner reports deterministic workspace OpenLore source validation metadata
The system SHALL expose deterministic workspace OpenLore source validation metadata in the pipeline result when the validation stage executes.

#### Scenario: Pipeline result includes OpenLore source validation metadata
- **WHEN** local code starts the pipeline runner with a valid registry path and configured workspace OpenLore source validation stage
- **THEN** the returned pipeline result includes validation metadata for the workspace OpenLore source path, federation setting, freshness policy, included repository references, and validation status
- **THEN** the returned pipeline result excludes source code, call graph, dependency graph, symbol bodies, architecture analysis, impact analysis, OpenLore query responses, credentials, tokens, and API responses

#### Scenario: Pipeline result is deterministic across repeated runs
- **WHEN** local code starts the pipeline runner multiple times with the same valid registry path and configured workspace OpenLore source validation stage
- **THEN** each returned pipeline result reports the same configured stages, executed stages, validation metadata, graph snapshot, and serialized status structure

### Requirement: Script wrapper can report workspace OpenLore source validation
The system SHALL allow the local script wrapper to report workspace OpenLore source validation through the reusable pipeline function without adding validation business logic to the script.

#### Scenario: Script runs with OpenLore source validation stage
- **WHEN** the user runs the build script with a local `repo-index.yaml` whose configured stages include `workspace-openlore-source`
- **THEN** the script delegates to the reusable pipeline function
- **THEN** the observable output reports successful workspace registry and workspace OpenLore source validation-stage execution

#### Scenario: Script OpenLore validation behavior remains local-first
- **WHEN** the build script runs with a local registry path and configured workspace OpenLore source validation stage in an environment without network access
- **THEN** the script completes without contacting external services or requiring credentials

