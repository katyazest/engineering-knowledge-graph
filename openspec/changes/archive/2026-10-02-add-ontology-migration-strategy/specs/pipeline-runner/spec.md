## MODIFIED Requirements

### Requirement: Runner migrates canonical ontology before downstream stages
The system SHALL migrate a configured persisted graph through the versioned snapshot migration boundary before persistence readback, graph derivation, graph integrity validation, or query-ready output consumes that graph. The runner SHALL pass only the validated current-version canonical snapshot to downstream stages. An unsupported schema version, missing migration path, migration integrity failure, or persistence commit failure SHALL produce a deterministic failed migration-stage result and stop downstream graph processing.

#### Scenario: Migration precedes downstream graph stages
- **WHEN** a pipeline run uses a configured local graph store containing a supported prior-version or supported legacy ontology document and executes persistence or later graph stages
- **THEN** the runner executes and validates ontology migration before exposing persistence readback to derivation or validation
- **THEN** derivation, validation, and query-ready output receive only the current-version canonical graph snapshot

#### Scenario: Migration failure stops the pipeline
- **WHEN** ontology migration reports an unsupported-version, integrity, or persistence failure
- **THEN** the runner reports a deterministic failed migration stage result
- **THEN** it does not execute derivation, validation, query wrapper, projection, wiki, or MCP wrapper stages for that run

### Requirement: Runner reports deterministic ontology migration metadata
The system SHALL expose deterministic payload-safe ontology migration metadata in the pipeline result whenever migration is attempted. The metadata SHALL include migration status, source and target schema versions or a safe legacy-descriptor identifier, applied migration identifiers, migrated record counts where applicable, diagnostics, and resulting graph counts; it SHALL exclude source payloads, persistence internals, credentials, tokens, and provider response data.

#### Scenario: Pipeline result includes version migration metadata
- **WHEN** ontology migration executes during a pipeline run
- **THEN** the pipeline result includes its version-migration status, source and target version information, applied migration identifiers, migrated record counts, safe diagnostics when present, and resulting graph counts
- **THEN** the metadata excludes full OpenSpec markdown bodies, source code, external API payloads, credentials, and tokens
