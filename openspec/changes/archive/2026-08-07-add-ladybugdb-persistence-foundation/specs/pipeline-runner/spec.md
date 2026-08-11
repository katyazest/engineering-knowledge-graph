## ADDED Requirements

### Requirement: Runner can execute adapter-compatible LadybugDB persistence stage
The system SHALL allow the local pipeline runner to execute an adapter-compatible LadybugDB persistence stage after canonical graph-producing stages when persistence is configured.

#### Scenario: Persistence stage executes after registry stage
- **WHEN** local code starts the pipeline runner with a valid workspace registry path and configured adapter-compatible LadybugDB persistence output path
- **THEN** the runner executes the workspace registry stage before the adapter-compatible LadybugDB persistence stage
- **THEN** the runner persists the canonical graph snapshot produced from the registry
- **THEN** the returned pipeline result reports both stages in deterministic configured and executed stage order

#### Scenario: Persistence stage returns stored graph snapshot
- **WHEN** local code starts the pipeline runner with persistence configured
- **THEN** the returned pipeline result includes a canonical graph snapshot that matches the graph read back from the local store

### Requirement: Runner preserves non-persistent behavior
The system SHALL preserve existing side-effect-free bootstrap and workspace-registry-only behavior when LadybugDB persistence is not configured.

#### Scenario: Bootstrap run remains side-effect-free
- **WHEN** local code starts the pipeline runner without a registry path or persistence output path
- **THEN** the runner preserves the existing empty bootstrap behavior with zero configured stages, zero executed stages, and an empty canonical graph snapshot
- **THEN** the runner does not create or update LadybugDB storage

#### Scenario: Registry-only run remains side-effect-free
- **WHEN** local code starts the pipeline runner with a valid workspace registry path but without persistence configured
- **THEN** the runner executes only the workspace registry stage
- **THEN** the runner returns the in-memory canonical graph snapshot produced from the registry
- **THEN** the runner does not create or update LadybugDB storage

### Requirement: Script wrapper can pass persistence configuration
The system SHALL allow the local script wrapper to pass optional LadybugDB persistence configuration into the reusable pipeline function without adding persistence business logic to the script.

#### Scenario: Script runs with registry and persistence path
- **WHEN** the user runs the build script with a local `repo-index.yaml` path and a local persistence output path
- **THEN** the script delegates registry and persistence inputs to the reusable pipeline function
- **THEN** the observable output reports successful registry-stage and adapter-compatible LadybugDB persistence-stage execution

#### Scenario: Script persistence behavior remains local-first
- **WHEN** the build script runs with local persistence configuration in an environment without network access
- **THEN** the script completes without contacting external services or requiring credentials
