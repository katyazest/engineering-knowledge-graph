## ADDED Requirements

### Requirement: Pipeline accepts enriched PR implementation evidence without external acquisition
When `pr-code-candidate-extraction` is configured, the local pipeline runner SHALL accept the enriched normalized PR implementation-evidence input containing base/head revisions and explicit intended-change source associations, merge only validated resulting graph records, and report deterministic payload-safe PR-evidence metadata. It SHALL fail before graph mutation for missing required normalized input or invalid PR evidence, preserve unconfigured pipeline behavior, and SHALL not call Jira, Bitbucket, Graphify, OpenLore, or another external service to acquire or complete the input.

#### Scenario: Enriched PR evidence stage is local and deterministic
- **WHEN** a configured local pipeline receives the same valid enriched PR evidence fixture twice
- **THEN** it produces the same configured/executed stage sequence, PR-evidence metadata, graph snapshot, and candidate scope references
- **THEN** it does not expose raw input payloads or contact external infrastructure
