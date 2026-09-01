## ADDED Requirements

### Requirement: Cross-graph evidence retains first-class provenance by reference
The system SHALL require each cross-graph candidate observation and lifecycle evidence reference to resolve to complete first-class provenance and SHALL preserve those references through merge, persistence, and query. It SHALL not copy authoritative source content, provider payloads, or code intelligence into cross-graph claim, observation, or lifecycle records.

#### Scenario: Cross-graph candidate remains explainable without copied content
- **WHEN** a valid external or derived provenance record supports a cross-graph candidate observation or lifecycle revision
- **THEN** the persisted and queried cross-graph record retains its provenance reference and explanation chain
- **THEN** the cross-graph record contains no copied source content or authoritative provider payload
