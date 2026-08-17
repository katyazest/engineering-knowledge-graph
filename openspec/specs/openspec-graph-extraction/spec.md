## Purpose

The `openspec-graph-extraction` capability extracts OpenSpec changes, specifications, requirements, and scenarios from the validated OpenSpec store into canonical Engineering KG graph facts with deterministic IDs and source evidence.

## Requirements

### Requirement: OpenSpec graph extraction reads from validated store source
The system SHALL extract OpenSpec graph facts only from the OpenSpec root resolved by the validated OpenSpec store source.

#### Scenario: Extraction uses validated OpenSpec root
- **WHEN** local code executes OpenSpec graph extraction after successful OpenSpec store source validation
- **THEN** the extractor reads specifications from the validated `specs` path
- **THEN** the extractor reads changes from the validated `changes` path
- **THEN** the extractor does not resolve specifications or changes from process current working directory or nearest-root discovery

#### Scenario: Extraction remains local-first
- **WHEN** local code executes OpenSpec graph extraction in an environment without network access
- **THEN** extraction completes using only local OpenSpec store files and existing in-process code
- **THEN** extraction does not call Jira, Bitbucket, Confluence, OpenLore MCP, cloud services, external APIs, compilation, publishing, semantic extraction, or LLM services

### Requirement: Durable specifications are extracted with requirement and scenario granularity
The system SHALL extract durable OpenSpec specifications, requirements, and scenarios from every `spec.md` file discovered recursively under `openspec/specs/` into canonical graph facts.

#### Scenario: Current specification graph facts are produced
- **WHEN** the extractor reads a durable spec file containing `### Requirement:` and `#### Scenario:` headings
- **THEN** it produces an OpenSpec specification node for the capability identity derived from the spec path
- **THEN** it produces one OpenSpec requirement node for each `### Requirement: <name>` heading
- **THEN** it produces one OpenSpec scenario node for each `#### Scenario: <name>` heading under a requirement
- **THEN** it links the specification to its requirements and each requirement to its scenarios

#### Scenario: Nested durable specification graph facts are produced
- **WHEN** the extractor reads `openspec/specs/service/payments/spec.md`
- **THEN** it produces an OpenSpec specification node with capability `service/payments`
- **THEN** the specification node uses the same namespaced capability identity in its deterministic OpenSpec identity
- **THEN** source evidence identifies the nested spec file path

#### Scenario: Flat durable capability identity is preserved
- **WHEN** the extractor reads `openspec/specs/payments/spec.md`
- **THEN** it produces an OpenSpec specification node with capability `payments`
- **THEN** it does not rename the capability to a namespaced value

#### Scenario: Local heading schema is respected
- **WHEN** the extractor reads a durable spec file
- **THEN** it treats `### Requirement: <name>` as the supported requirement heading shape
- **THEN** it treats `#### Scenario: <name>` as the supported scenario heading shape
- **THEN** it does not treat `## Requirement: <name>` as a valid requirement heading

### Requirement: Active and archived changes are extracted as distinct facts
The system SHALL extract active OpenSpec changes and archived OpenSpec changes as distinct canonical graph facts.

#### Scenario: Active change is extracted from change directory
- **WHEN** the extractor reads `openspec/changes/<change>/` outside the `archive` directory
- **THEN** it produces an active OpenSpec change node using the change directory name as an opaque stable identity
- **THEN** it links the active change to its local change artifacts when those artifacts are present

#### Scenario: Archived change is extracted from archive directory
- **WHEN** the extractor reads `openspec/changes/archive/<archive-directory>/`
- **THEN** it produces an archived OpenSpec change node using the archive directory name as an opaque stable identity
- **THEN** it records archive state from the archive path and available archive metadata
- **THEN** it does not infer equivalence or transition from an active change unless explicit OpenSpec metadata supplies that relation

#### Scenario: Change directory names are opaque
- **WHEN** an active or archived change directory name includes a date, a Jira issue ID, both, or only a Jira issue ID
- **THEN** the extractor uses the full directory name as the stable OpenSpec change identity
- **THEN** Jira-looking tokens may be exposed only as optional metadata or reference hints

### Requirement: Change-local specs remain scoped to their change artifact state
The system SHALL extract change-local spec delta files discovered recursively under a change's `specs/` directory as change-scoped or archive-scoped facts without blindly merging them into current durable specification facts.

#### Scenario: Archived delta spec duplicates durable spec
- **WHEN** an archived change contains a delta spec for a capability that also exists under `openspec/specs`
- **THEN** the extractor preserves the archived delta spec as an archive-scoped spec fact
- **THEN** the extractor preserves the durable spec as the current specification fact
- **THEN** it does not collapse the two facts into one node solely because their capability names match

#### Scenario: Active delta spec is linked to active change
- **WHEN** an active change contains `specs/<capability>/spec.md`
- **THEN** the extractor links the change-scoped spec fact to the active change
- **THEN** the extractor preserves the capability identity from the delta spec path

#### Scenario: Nested active delta spec preserves namespaced capability identity
- **WHEN** an active change contains `specs/service/payments/spec.md`
- **THEN** the extractor links the change-scoped spec fact to the active change
- **THEN** the change-scoped spec fact has capability `service/payments`
- **THEN** the change-to-spec relationship preserves capability `service/payments`

#### Scenario: Nested archived delta spec preserves namespaced capability identity
- **WHEN** an archived change contains `specs/service/payments/spec.md`
- **THEN** the extractor preserves the archived delta spec as an archive-scoped spec fact
- **THEN** the archived spec fact has capability `service/payments`
- **THEN** the change-to-spec relationship preserves capability `service/payments`

### Requirement: OpenSpec spec capability identity is derived from relative spec path
The system SHALL derive OpenSpec spec capability identity from the spec file path relative to the relevant `specs/` directory with the trailing `/spec.md` segment removed.

#### Scenario: Durable nested capability identity is namespaced
- **WHEN** the extractor reads a durable spec at `openspec/specs/service/directory1-n/spec.md`
- **THEN** it derives capability `service/directory1-n`
- **THEN** it uses `service/directory1-n` in specification, requirement, scenario, and relationship properties that identify capability

#### Scenario: Change-scoped nested capability identity is namespaced
- **WHEN** the extractor reads a change-scoped spec at `openspec/changes/add-x/specs/service/directory1-n/spec.md`
- **THEN** it derives capability `service/directory1-n`
- **THEN** it uses `service/directory1-n` in specification, requirement, scenario, and relationship properties that identify capability

#### Scenario: Recursive discovery remains deterministic
- **WHEN** local code runs OpenSpec graph extraction multiple times against unchanged nested and flat spec files
- **THEN** each extraction result contains the same node IDs, edge IDs, evidence IDs, graph counts, and serialized extraction metadata

### Requirement: Optional specification frontmatter is extracted as non-authoritative metadata
The system SHALL parse optional YAML frontmatter in durable spec files without requiring frontmatter or any individual frontmatter key.

#### Scenario: Supported frontmatter keys are present
- **WHEN** a durable spec file contains YAML frontmatter with `repo`, `created`, `updated`, `title`, or `related`
- **THEN** the extractor records supported values as optional source metadata
- **THEN** the capability directory name remains the deterministic specification identity
- **THEN** the frontmatter `repo` value is treated as a manually maintained repository hint, not proof of implementation ownership

#### Scenario: Frontmatter is missing or partial
- **WHEN** a durable spec file has no frontmatter or omits supported frontmatter keys
- **THEN** extraction still produces specification, requirement, and scenario facts from supported headings
- **THEN** missing frontmatter does not cause extraction failure

### Requirement: Related frontmatter creates non-confident relationships
The system SHALL represent `related` frontmatter entries as non-confident related-spec relationships or unresolved related-spec references.

#### Scenario: Related title has unique match
- **WHEN** a spec frontmatter `related` entry names a title that uniquely matches another extracted spec title
- **THEN** the extractor creates a related-spec edge to that matched spec
- **THEN** the related-spec edge is marked non-confident because frontmatter is manually maintained

#### Scenario: Related title is unresolved or ambiguous
- **WHEN** a spec frontmatter `related` entry does not uniquely match another extracted spec title
- **THEN** the extractor preserves the related title as unresolved reference metadata or evidence
- **THEN** it does not invent a target specification node

### Requirement: OpenSpec extraction produces deterministic graph output
The system SHALL produce deterministic graph facts and extraction metadata for the same OpenSpec store contents.

#### Scenario: Repeated extraction is stable
- **WHEN** local code runs OpenSpec graph extraction multiple times against unchanged OpenSpec store files
- **THEN** each extraction result contains the same node IDs, edge IDs, evidence IDs, graph counts, and serialized extraction metadata

#### Scenario: Source evidence excludes full content
- **WHEN** extraction serializes source evidence for OpenSpec-originated facts
- **THEN** evidence identifies local source file paths, artifact types, heading names, and OpenSpec object identities as needed
- **THEN** evidence excludes full requirement bodies, full markdown artifact bodies, implementation source code, OpenLore analysis details, generated graph records, credentials, tokens, and external API payloads
