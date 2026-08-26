## ADDED Requirements

### Requirement: Runner migrates canonical ontology before downstream stages
The system SHALL migrate a configured persisted graph from retired OpenSpec-prefixed domain vocabulary to the revised canonical ontology before persistence readback, graph derivation, graph integrity validation, or query-ready output consumes that graph.

#### Scenario: Migration precedes downstream graph stages
- **WHEN** a pipeline run uses a configured local graph store containing legacy ontology records and executes persistence or later graph stages
- **THEN** the runner executes and validates ontology migration before exposing persistence readback to derivation or validation
- **THEN** derivation, validation, and query-ready output receive only the revised canonical graph snapshot

#### Scenario: Migration failure stops the pipeline
- **WHEN** ontology migration reports an integrity or persistence failure
- **THEN** the runner reports a deterministic failed migration stage result
- **THEN** the runner does not execute derivation, validation, query wrapper, projection, wiki, or MCP wrapper stages for that run

### Requirement: Runner reports deterministic ontology migration metadata
The system SHALL expose deterministic migration status and graph counts in the pipeline result without exposing source payloads or persistence internals.

#### Scenario: Pipeline result includes migration metadata
- **WHEN** ontology migration executes during a pipeline run
- **THEN** the pipeline result includes migration status, migrated record counts, conflict diagnostics when present, and resulting graph counts
- **THEN** the metadata excludes full OpenSpec markdown bodies, source code, external API payloads, credentials, and tokens
