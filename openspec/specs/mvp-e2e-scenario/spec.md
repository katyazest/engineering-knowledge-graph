## Purpose

The `mvp-e2e-scenario` capability defines the deterministic local end-to-end MVP scenario used to prove the full Engineering KG flow from configured workspace inputs through persisted, derived, validated, and queryable graph facts.

## Requirements

### Requirement: Local MVP end-to-end scenario proves full graph flow
The system SHALL provide one deterministic local MVP end-to-end scenario that starts from a workspace registry and OpenSpec store source and verifies the resulting Engineering KG through persistence readback, derivation, validation, and local query access.

#### Scenario: Scenario executes full local graph flow
- **WHEN** local test code runs the MVP end-to-end scenario with a representative non-Git workspace registry, a matching OpenSpec store source, and a temporary local graph persistence path
- **THEN** the scenario executes workspace registry loading, OpenSpec store source validation, OpenSpec graph extraction, adapter-compatible LadybugDB persistence, persistence readback, graph derivation, graph integrity validation, and local query access in the same local flow
- **THEN** the scenario completes without network access, API keys, cloud services, OpenLore MCP calls, Jira calls, Bitbucket calls, Confluence calls, compilation, publishing, semantic extraction, or LLM services

#### Scenario: Scenario uses representative MVP workspace layout
- **WHEN** the MVP end-to-end scenario prepares its local fixture inputs
- **THEN** the fixture represents a project workspace that is not required to be a Git repository
- **THEN** the fixture represents implementation repositories as independent repository entries under the workspace
- **THEN** the fixture represents exactly one requirements repository used as the OpenSpec store source
- **THEN** generated OpenLore index paths and Engineering KG graph storage paths remain workspace-generated state outside configured repository roots

### Requirement: Local MVP end-to-end scenario verifies deterministic output
The system SHALL verify that the full MVP graph flow returns deterministic pipeline, persistence, derivation, validation, and query outputs for unchanged local inputs.

#### Scenario: Repeated scenario runs are stable
- **WHEN** local test code runs the MVP end-to-end scenario multiple times with the same registry fixture, matching OpenSpec store source, and unchanged OpenSpec files
- **THEN** each run reports the same configured stages, executed stages, graph counts, stage metadata structure, persisted readback graph, derivation metadata, validation metadata, and query result structure

#### Scenario: Persisted graph can be queried after readback
- **WHEN** the MVP end-to-end scenario persists the pipeline graph to the local graph store and constructs query access from that persisted store
- **THEN** local query operations can list represented requirements, services, OpenSpec changes, and traceability relationships from the persisted graph
- **THEN** query results are ordered deterministically by stable graph identity

### Requirement: Local MVP end-to-end scenario preserves ownership boundaries
The system SHALL prove that end-to-end pipeline metadata, persisted graph readback, and query outputs preserve source ownership and sensitive-data boundaries.

#### Scenario: Scenario output excludes source-owned payloads
- **WHEN** the MVP end-to-end scenario serializes pipeline results, persisted graph readback, and query results
- **THEN** serialized outputs exclude source code, call graphs, dependency graphs, symbol bodies, OpenLore analysis payloads, full OpenSpec markdown bodies, Jira payloads, Bitbucket payloads, Confluence content, generated graph internals, credentials, tokens, and external API responses

#### Scenario: Scenario does not infer service implementation ownership
- **WHEN** the MVP end-to-end scenario queries requirements, services, OpenSpec changes, or traceability relationships
- **THEN** query results include only facts and relationships represented in the canonical graph or deterministic derived graph
- **THEN** the scenario does not treat service names, repository hints, prompt context, or manually maintained non-confident metadata as authoritative implementation ownership
