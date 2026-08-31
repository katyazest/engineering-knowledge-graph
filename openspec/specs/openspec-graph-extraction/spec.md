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
The system SHALL extract every durable `spec.md` file beneath `openspec/specs/` into canonical specification, requirement, and scenario facts, each supported by OpenSpec evidence.

#### Scenario: Current specification graph facts are produced
- **WHEN** the extractor reads a durable spec file containing `### Requirement:` and `#### Scenario:` headings
- **THEN** it produces canonical specification, requirement, and scenario nodes using source-independent identities
- **THEN** it links the specification to its requirements and each requirement to its scenarios with canonical relationship kinds
- **THEN** every emitted fact references evidence for the source file and supported heading

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
The system SHALL retain an active or archived OpenSpec change as a source-specific fact while emitting its delta specification, requirement, and scenario content as canonical facts supported by change-scoped OpenSpec evidence.

#### Scenario: Change delta converges on a canonical specification
- **WHEN** an active or archived change contains `specs/<capability>/spec.md`
- **THEN** the extractor emits or reuses the canonical specification for that repository and capability
- **THEN** it links the source-specific change to the canonical specification with asserted OpenSpec evidence
- **THEN** it does not create an `openspec-spec` node or encode the change identity in the canonical specification ID

#### Scenario: Durable specification is absent
- **WHEN** a change delta names a capability that has no durable spec file
- **THEN** the extractor creates the canonical specification using the same repository-and-capability identity
- **THEN** the emitted fact remains supported by the change-scoped OpenSpec evidence without inventing a durable source file

### Requirement: OpenSpec spec capability identity is derived from relative spec path
The system SHALL derive the capability component of a canonical OpenSpec-backed specification identity from the relative spec path with the trailing `/spec.md` segment removed.

#### Scenario: Same capability across OpenSpec scopes has one identity
- **WHEN** durable and change-scoped spec files represent the same repository and capability
- **THEN** extraction assigns the same canonical specification ID to their compatible facts
- **THEN** both source locations are retained as provenance rather than separate scoped specification nodes

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

### Requirement: OpenSpec extraction merges canonical provenance deterministically
The system SHALL coalesce compatible OpenSpec assertions of one canonical identity, sort resulting records and evidence identifiers deterministically, and reject conflicting canonical identity fields.

#### Scenario: Repeated extraction is idempotent
- **WHEN** extraction runs repeatedly against unchanged durable and change-scoped OpenSpec files
- **THEN** it returns the same canonical node IDs, relationship IDs, evidence IDs, ordering, and extraction metadata
- **THEN** it does not duplicate canonical facts or discard existing source evidence

### Requirement: OpenSpec extraction supplies authoritative artifact identity before canonical fact construction
The system SHALL construct and validate explicit OpenSpec source-artifact identity from the validated store source and repository-relative artifact locator before emitting canonical facts or evidence. It SHALL use the validated store repository's resolved Git `HEAD` commit as the OpenSpec artifact `revision_or_version` and SHALL reject extraction when that context cannot supply a required identity component, rather than substituting a change display name or local absolute path. Canonical specification, requirement, scenario, change, node, and edge identifiers SHALL remain source-independent and unchanged by this provenance identity.

#### Scenario: Validated OpenSpec context produces stable provenance
- **WHEN** extraction runs against the same validated OpenSpec source contents and authoritative source context from different local checkout locations
- **THEN** it produces the same canonical fact IDs, source-artifact IDs, evidence IDs, counts, and serialized metadata
- **THEN** repository-relative source locators remain available for source navigation without becoming canonical identity

#### Scenario: Required OpenSpec identity context is unavailable
- **WHEN** validated OpenSpec source context lacks a required authoritative repository/store identity or resolved Git `HEAD` commit
- **THEN** extraction fails with a deterministic source-artifact-identity diagnostic before producing graph facts
- **THEN** it does not fall back to a display name, current working directory, or absolute source path

