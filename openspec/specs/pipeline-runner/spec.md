## Purpose

The `pipeline-runner` capability defines the local-first bootstrap execution contract for the Engineering KG MVP pipeline.

## Requirements

### Requirement: Local bootstrap runner starts
The system SHALL provide a local Python pipeline runner that can be started from the repository without requiring API keys, cloud services, compilation, publishing, external enterprise systems, OpenLore queries, or LadybugDB persistence.

#### Scenario: Runner starts successfully
- **WHEN** the user starts the bootstrap pipeline runner from the repository
- **THEN** the runner completes successfully without contacting external services or requiring credentials

#### Scenario: Runner remains local-first
- **WHEN** the bootstrap runner is executed in an environment without network access
- **THEN** the runner still completes using only local project code and files required by this bootstrap

### Requirement: Reusable pipeline function returns empty status
The system SHALL expose a reusable Python pipeline module/function that returns an empty but valid deterministic pipeline status/result with an empty canonical graph snapshot before any real pipeline stages are implemented.

#### Scenario: Empty status returned
- **WHEN** local code calls the reusable pipeline module/function
- **THEN** the returned status/result indicates that the pipeline completed with zero configured or executed stages
- **THEN** the returned status/result includes an empty canonical graph snapshot with zero nodes, zero edges, and zero evidence records

#### Scenario: Status is deterministic
- **WHEN** the reusable pipeline module/function is called multiple times with the same bootstrap configuration
- **THEN** each returned status/result has the same stable structure and values

### Requirement: Script wrapper delegates to reusable function
The system SHALL provide a Python script entry point that delegates pipeline execution to the reusable Python pipeline module/function.

#### Scenario: Script invokes pipeline function
- **WHEN** the user runs the bootstrap script entry point
- **THEN** the script invokes the reusable pipeline module/function and exits successfully

#### Scenario: Script output reflects empty bootstrap run
- **WHEN** the bootstrap script completes
- **THEN** its observable output or return behavior communicates that the pipeline completed with zero configured or executed stages

### Requirement: Bootstrap behavior is smoke-testable
The system SHALL include smoke tests that verify the reusable pipeline module/function and script entry point start successfully and produce the empty valid status/result.

#### Scenario: Smoke tests verify startup
- **WHEN** the project test suite runs
- **THEN** tests verify that the reusable pipeline module/function starts and returns the empty valid status/result

#### Scenario: Smoke tests verify script entry point
- **WHEN** the project test suite runs
- **THEN** tests verify that the Python script entry point starts successfully through the reusable pipeline module/function

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
