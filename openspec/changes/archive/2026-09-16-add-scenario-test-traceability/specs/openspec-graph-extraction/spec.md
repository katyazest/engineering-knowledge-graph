## ADDED Requirements

### Requirement: OpenSpec extraction supplies declared test-traceability source evidence
The OpenSpec extraction source helper SHALL locate `openspec/test-traceability.yaml` only beneath the validated OpenSpec root and expose its repository-relative source-artifact identity, revision, and payload-free source context to the optional scenario-test-traceability admission component. That component SHALL resolve mapping selectors only against the canonical requirement and scenario facts produced from that same validated store extraction, retain the mapping artifact as OpenSpec evidence rather than canonicalizing its YAML body, and leave canonical OpenSpec requirement/scenario identities unchanged. The standard OpenSpec graph extraction stage SHALL remain independent of traceability admission when the optional stage is not configured. Neither component SHALL discover test files, scan repositories for names, call a test framework, CI system, Graphify, OpenLore, Jira, Bitbucket, or another external system.

#### Scenario: Mapping source is bound to the validated store
- **WHEN** a validated OpenSpec store contains `openspec/test-traceability.yaml` and extracted requirement/scenario facts
- **THEN** the extractor supplies a deterministic repository-relative mapping-artifact identity and OpenSpec evidence/provenance context for exact selector resolution
- **THEN** canonical target IDs do not depend on the mapping file path, test identity, or mapping order

#### Scenario: Absent mapping artifact does not change OpenSpec extraction
- **WHEN** the validated OpenSpec store has no `openspec/test-traceability.yaml`
- **THEN** standard specification, requirement, scenario, change, artifact, evidence, and metadata extraction remains successful and deterministic
- **THEN** it does not scan for or infer tests
