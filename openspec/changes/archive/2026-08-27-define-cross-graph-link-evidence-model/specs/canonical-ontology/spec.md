## ADDED Requirements

### Requirement: Canonical ontology represents cross-graph link claims and evidence
The system SHALL provide in-memory canonical models for cross-graph link claims, attributable candidate-evidence observations, their lifecycle states, and trusted semantic-link projections. These models SHALL use stable IDs and `CodeLocator` targets without adding OpenLore-specific graph or analysis models to the canonical ontology.

#### Scenario: Cross-graph models can be constructed locally
- **WHEN** local code constructs valid cross-graph link claims and candidate-evidence observations
- **THEN** the objects are created and serialized without requiring external services, API keys, database access, or OpenLore queries

#### Scenario: Existing graph construction remains compatible
- **WHEN** local code constructs a graph snapshot using only existing node, edge, and evidence collections
- **THEN** the snapshot remains constructible and serializes with empty cross-graph link collections

### Requirement: Graph snapshots merge cross-graph link data safely
The system SHALL include cross-graph link claims and candidate-evidence observations in graph snapshot merge semantics. It SHALL coalesce identical stable records, accumulate compatible candidate-evidence observations for the same claim, and reject conflicting immutable record values or dangling claim references.

#### Scenario: Compatible cross-graph snapshots merge
- **WHEN** two snapshots contain the same compatible claim and different valid observations that reference it
- **THEN** the merged snapshot contains one claim and all distinct observations in deterministic order

#### Scenario: Conflicting cross-graph snapshot data is rejected
- **WHEN** two snapshots contain records with the same cross-graph stable identifier but conflicting immutable values
- **THEN** snapshot merging raises a deterministic conflict error
