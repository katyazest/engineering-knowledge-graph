## Context

The MVP pipeline already separates workspace registry loading, OpenLore source validation, OpenSpec store source validation, canonical ontology objects, and adapter-compatible persistence. The validated OpenSpec store is the durable source for specifications, intended changes, wiki content, and versioned Engineering KG configuration. The Engineering KG graph is local generated state and must not become the authoring source for requirements.

This change adds the first OpenSpec extraction stage after store-source validation. The extractor should read the selected store's `openspec/specs` and `openspec/changes` trees, convert durable intended-behavior artifacts into canonical graph nodes and edges, and attach local source evidence sufficient to trace each fact back to an OpenSpec file and object identity. It should not query Jira, Bitbucket, Confluence, OpenLore MCP, or LadybugDB-native APIs.

## Goals / Non-Goals

**Goals:**

- Extract OpenSpec specifications, optional specification frontmatter, requirements, scenarios, active changes, archived changes, and change planning artifacts into canonical graph facts.
- Preserve deterministic traceability between changes, capabilities/specifications, requirements, scenarios, source files, and archive state.
- Preserve active and archived changes as distinct node kinds because an active change is work in progress and may not be implemented in code, while an archived change records a completed or historical OpenSpec artifact state.
- Represent manually maintained related-spec metadata as non-confident relationships because optional frontmatter can be stale or wrong.
- Extend the canonical ontology only as much as needed for OpenSpec-originated facts and source-file evidence.
- Add a configurable pipeline stage that runs after `workspace-registry` and `openspec-store-source`.
- Return deterministic extraction metadata and graph counts in the pipeline result.
- Keep execution local-first and independent of network access, credentials, cloud services, OpenLore queries, Jira, Bitbucket, Confluence, compilation, publishing, semantic extraction, and LLM calls.

**Non-Goals:**

- Interpret natural-language requirement meaning beyond the explicit OpenSpec structure.
- Infer service ownership, API contracts, code symbols, Jira issue links, Bitbucket PR links, or Confluence content unless those identifiers are explicitly present and represented as references.
- Treat optional frontmatter as authoritative implementation truth.
- Validate whether requirements are well written, implemented, complete, or mutually consistent.
- Modify OpenSpec files, archive changes, generate wiki pages, rebuild OpenLore indexes, or write LadybugDB-native storage directly.
- Replace existing OpenSpec CLI validation.

## Decisions

### Add a dedicated OpenSpec graph extractor module

Create an extraction boundary under the OpenSpec ingestion package, likely near `engineering_kg.ingest.openspec`, that accepts the validated OpenSpec store source result and returns an `OpenSpecExtractionResult` containing a canonical `GraphSnapshot` plus deterministic metadata.

Rationale: store-source validation proves where extraction may read from; graph extraction owns what durable OpenSpec content becomes graph facts. Keeping this boundary separate avoids coupling pipeline orchestration to parsing details.

Alternative considered: parse OpenSpec content directly in the pipeline runner. That would make stage orchestration hard to test and would mix file parsing, ontology mapping, and status reporting in one place.

### Parse a constrained OpenSpec markdown subset

For MVP, parse only deterministic structure already used by local specs and change artifacts:

- `openspec/specs/<capability>/spec.md` purpose text, `### Requirement:` headings, and `#### Scenario:` headings, matching the local OpenSpec spec instructions.
- optional YAML frontmatter in `openspec/specs/<capability>/spec.md`, including `repo`, `created`, `updated`, `title`, and `related` when present.
- active changes under `openspec/changes/<change>/` with `.openspec.yaml`, `proposal.md`, `design.md`, `tasks.md`, and `specs/**/*.md` when present.
- archived changes under `openspec/changes/archive/<archive-dir>/` with the same planning artifact names.
- capability names from spec directory names and proposal `Capabilities` sections when available.

The parser should be line-oriented but structured around headings and known artifact paths, not free-form semantic extraction. It should not treat `## Requirement:` as a valid requirement heading for this repository unless the local OpenSpec schema/templates are changed, because `##` is currently used for spec operation sections such as `## ADDED Requirements`.

Rationale: the existing OpenSpec files are Markdown, and the MVP needs deterministic facts from explicit structure. A narrow parser is sufficient and avoids introducing markdown/LLM dependencies.

Alternative considered: call OpenSpec CLI `show` commands for every spec and change. That may be useful later, but a local file parser is simpler to test, works without relying on CLI output format for every artifact, and keeps extraction tied to the validated store path rather than current working directory.

### Represent OpenSpec entities as canonical graph vocabulary

Extend the canonical ontology with stable node kinds for:

- `openspec-active-change`
- `openspec-archived-change`
- `openspec-spec`
- `openspec-requirement`
- `openspec-scenario`
- `openspec-artifact`

Add edge kinds for explicit relationships:

- change defines or modifies a spec/capability;
- spec contains requirement;
- requirement contains scenario;
- change has planning artifact;
- archived change records a historical intended-behavior artifact state from the archive path and available archive metadata;
- spec has a non-confident related-spec relationship to another spec when optional `related` frontmatter names another spec title.

Every node ID should be generated from the selected store identity plus explicit OpenSpec identity parts, such as change directory name, archive directory, spec capability, requirement heading, and scenario heading. Change directory names should be treated as opaque OpenSpec change identifiers: they may include a date, a Jira issue ID, both, or only a Jira issue ID. Jira-looking tokens in change directory names may be exposed as optional metadata/reference hints, but they must not replace the directory name as the stable change identity. Source file paths should be stored as paths relative to the selected OpenSpec store repository or OpenSpec root so repeated runs from different absolute workspace roots remain as stable as possible.

Archived change delta specs should be modeled as change-scoped or archive-scoped spec facts, not blindly merged with current durable specs under `openspec/specs`. The same intended behavior may appear in an archived change and in the current specification tree, and that duplication is meaningful: the archived copy records the change artifact state while `openspec/specs` records the current durable specification state. The extractor should not infer a transition or equivalence relation between active and archived changes unless a future OpenSpec metadata field explicitly carries that link.

Rationale: OpenSpec facts need to be queryable as first-class graph objects while retaining source traceability. Requirements and scenarios are first-class traceability units for intended behavior, so their granularity must be preserved rather than collapsed into document-level facts. Stable identities prevent duplicate graph rows across repeated extraction runs.

### Treat specification frontmatter as optional and non-authoritative

When a spec contains YAML frontmatter, the extractor should parse the supported keys `repo`, `created`, `updated`, `title`, and `related`. Missing frontmatter or missing keys should not fail extraction. The spec directory name remains the deterministic capability identity; `title` is a display label when present. `created` and `updated` are source metadata when parseable. `repo` is a manually maintained repository hint, not proof of implementation ownership.

The `related` list should create non-confident related-spec edges by matching listed titles against extracted spec titles and, when no unique title match exists, by preserving an unresolved related-spec reference as evidence/metadata rather than inventing a target.

Rationale: frontmatter can improve navigation and analysis, but it is manually inserted and may be incomplete, stale, or wrong. The graph should surface it with lower confidence instead of treating it as a verified dependency.

Alternative considered: ignore frontmatter entirely for MVP. That would lose useful analyst-authored navigation links, especially external integration references that should point to related specs.

Alternative considered: treat `related` as a normal confident edge. That would overstate manually maintained metadata and could mislead downstream traceability queries.

### Attach source evidence without embedding source bodies

Introduce or reuse an evidence shape that can point to a local source file plus an OpenSpec object identity and optional line range when available. Evidence may include artifact type, relative file path, heading text, and deterministic object identity. It must not include full requirement bodies, implementation source code, generated graph records, credentials, tokens, or external API payloads.

Rationale: EKG needs traceability back to source artifacts, but the graph should remain canonical generated facts rather than a duplicate content store.

Alternative considered: store full Markdown blocks on graph nodes for easier querying. That would blur source ownership and make graph persistence larger and more sensitive than needed for MVP.

### Merge extracted graph facts into the pipeline snapshot

Add a configured stage name such as `openspec-graph-extraction`. The runner should execute it after `openspec-store-source` when both are configured. If persistence is configured, persistence should run after extraction so the stored snapshot includes OpenSpec facts.

The stage should merge extracted nodes, edges, and evidence into the current `GraphSnapshot` using deterministic ID-based replacement or de-duplication. The pipeline result should report configured stage order, executed stage order, OpenSpec extraction metadata, and graph counts.

Rationale: all source extractors should contribute to the same canonical snapshot before persistence, derivation, validation, and MCP query wrappers consume it.

Alternative considered: write extractor output directly to the persistence adapter. That would bypass the reusable in-memory contract and make testing harder.

## Risks / Trade-offs

- OpenSpec Markdown shape may evolve beyond the MVP heading subset -> Mitigation: isolate parsing behind a narrow adapter and add fixtures for every supported heading/path pattern.
- Requirement or scenario headings may not be globally unique -> Mitigation: include spec capability, parent requirement, change/archive identity, and source file identity in stable ID parts.
- Change directory names may include dates, Jira issue IDs, both, or only Jira issue IDs -> Mitigation: treat change directory names as opaque stable OpenSpec identities and expose Jira-looking tokens only as optional metadata/reference hints.
- Archived delta specs can duplicate current durable specs under `openspec/specs` -> Mitigation: keep archive/change-scoped spec facts distinct from current durable spec facts and relate them only when identity or metadata supports it.
- Proposal capability lists may be incomplete or inconsistent with delta spec files -> Mitigation: extract both explicit proposal relationships and actual delta spec paths, then let later validation stages report drift.
- Manual frontmatter can be missing, stale, or wrong -> Mitigation: treat frontmatter as optional metadata and mark `related` edges as non-confident.
- Relative paths improve portability but may hide which physical store was used -> Mitigation: keep deterministic store-source metadata in the pipeline result while evidence uses relative source paths.
- Stage ordering errors could persist incomplete graph snapshots -> Mitigation: tests should assert extraction runs only after OpenSpec store source validation and before persistence when both are configured.
