## Context

The graph already has generic node kinds such as `service`, `repository`,
`specification`, `requirement`, `contract`, and `work_item`, but OpenSpec
extraction currently emits separate `openspec-spec`, `openspec-requirement`,
and `openspec-scenario` nodes. Their stable IDs include the OpenSpec scope and
change identity, so the same domain fact represented by a durable spec, a
change delta, Jira, Bitbucket, or later sources cannot converge on one
canonical node. OpenSpec-specific change and planning-artifact nodes are
genuinely source-owned and must remain distinct.

This is a breaking ontology migration affecting the canonical schema,
OpenSpec adapter, derivation and validation rules, persistence format and
stored records, pipeline output, local query DTOs, FactMCP wrappers, and
their tests. External systems remain boundaries: the project adapts and
orchestrates LadybugDB, Graphify, Jira MCP, Bitbucket MCP, llmwiki-cli, and
MkDocs without changing their internals.

## Goals / Non-Goals

**Goals:**

- Model shareable engineering concepts as source-independent canonical nodes
  with stable IDs that do not encode source, file path, line number, or
  display name.
- Preserve every source assertion as evidence and retain OpenSpec change and
  artifact entities where their lifecycle and payload are provider-specific.
- Replace OpenSpec-prefixed domain containment, related-spec, and
  traceability relationships with canonical relationship kinds and validate
  their endpoint shapes.
- Make ingestion, migration, persistence, derivation, queries, and repeated
  pipeline runs deterministic and idempotent.
- Expose canonical result shapes and source provenance through the local API
  and thin FactMCP wrappers.

**Non-Goals:**

- Matching independently authored facts across sources using semantic,
  probabilistic, or LLM-based entity resolution.
- Ingesting generated wiki pages as canonical facts or changing external
  provider schemas and infrastructure.
- Retaining source-prefixed canonical node or edge types as a compatibility
  layer after migration.

## Decisions

### Separate canonical facts from source evidence

Canonical nodes will use source-independent vocabulary: `service`,
`repository`, `specification`, `requirement`, `scenario`, `contract`,
`decision`, `test`, and `work_item` where applicable. Canonical edges will
express domain relationships such as specification-to-requirement,
requirement-to-scenario, related-specification, and change-to-specification
traceability without `openspec` in their kind.

`openspec-active-change`, `openspec-archived-change`, and
`openspec-artifact` remain source-specific nodes. Their lifecycle, names, and
planning-file structure have no provider-neutral equivalent. The change to
canonical-specification link remains an asserted OpenSpec relationship and
the derived change-to-specification trace is marked with `derived: true` and
the existing explicit rule ID.

Every canonical node and edge keeps `evidence_ids`; OpenSpec records use
`Evidence(source="openspec", locator=OpenSpecLocator(...))`. OpenSpec-only
fields, including artifact type, scope, relative path, heading, and line
range, stay in the locator or evidence metadata rather than canonical node
identity or properties. This lets later adapters attach their own evidence to
the same canonical fact without provider models leaking into the ontology.

Alternative considered: retain OpenSpec-prefixed nodes and add equivalence
edges. Rejected because it leaves duplicate domain entities as the primary
model and shifts deduplication complexity to every consumer.

### Define stable identities from canonical natural keys

The canonical schema will define one explicit natural key per canonical kind.
For the OpenSpec facts available today, identifiers will be based on the
requirements repository and capability for a specification; on the canonical
specification ID plus a normalized requirement key for a requirement; and on
the canonical requirement ID plus a normalized scenario key for a scenario.
The stable-ID helper remains the sole implementation of normalization and
hashing. Display names remain presentation values, not identity inputs.

An OpenSpec change-scoped delta is evidence of the matching canonical
capability rather than a separate canonical specification. If a matching
durable specification is absent, extraction creates the canonical
specification using the same repository-plus-capability key, allowing the
future durable assertion to merge deterministically. Requirements and
scenarios from all OpenSpec scopes then attach to that canonical hierarchy.

Alternative considered: use the current OpenSpec scope and change name in
canonical IDs. Rejected because these values make a source artifact's
lifecycle part of a cross-source fact's identity and prevent convergence.

### Normalize at adapters and merge canonical records deterministically

The OpenSpec adapter will parse source files into canonical fact candidates
and separate source-owned change/artifact candidates. It will collect all
evidence IDs for a canonical identity, merge compatible properties using a
documented deterministic precedence rule, sort records and evidence IDs, and
reject conflicting values for identity-defining fields rather than silently
choosing one. Provider response or parsing models stay private to the
adapter.

The graph snapshot merge and persistence merge will merge repeated canonical
records by ID without discarding provenance. A canonical record written again
with the same content is a no-op; a record with the same ID but incompatible
canonical shape is rejected by validation. This replaces the current
last-record-wins behavior for evidence-bearing duplicates.

Alternative considered: rely on the generic snapshot `merged_with` overwrite
behavior. Rejected because extraction order could lose provenance and conceal
identity conflicts.

### Preserve asserted-versus-derived traceability

Derivation will locate canonical specifications by their canonical identity
rather than `openspec-spec` scope properties. It will derive a canonical
traceability edge only from a valid source-owned OpenSpec change assertion to
a canonical specification. The result retains the asserted edge evidence,
sets `derived: true`, and records the derivation rule ID and input IDs.

Validation will replace OpenSpec-prefixed domain-shape checks with canonical
kind checks, while retaining specific checks for source-owned OpenSpec change
endpoints. It will require valid evidence references, enforce canonical
identity consistency, report conflicting duplicate records as errors, and
keep unresolved related-spec references as deterministic diagnostics.

Alternative considered: make all change-to-spec links derived. Rejected
because the extractor's source assertion and the inferred durable
traceability have different provenance and must remain distinguishable.

### Migrate persisted snapshots atomically before normal writes

The persistence adapter will recognize the previous ontology record kinds and
convert them in memory to the revised canonical nodes and edges. It will
recompute IDs from canonical natural keys, coalesce compatible records and
evidence, rewrite endpoints and derived-edge input references, validate the
result, then atomically replace the persisted snapshot. Migration is safe to
rerun: a snapshot already using the revised vocabulary produces no additional
records or IDs.

Migration failure leaves the original graph file unchanged and reports the
conflicting source records. Rollback consists of restoring the pre-migration
graph backup produced before replacement and running the prior compatible
version; no external LadybugDB schema migration is required because the
project-owned adapter owns the serialized graph contract.

Alternative considered: migrate only during a full rebuild. Rejected because
local persisted graphs and query users need a deterministic transition path
independent of re-ingesting all inputs.

### Make consumer contracts canonical and provenance-aware

Pipeline orchestration will run migration before persistence read/write and
then execute extraction, derivation, validation, and query-ready output over
the canonical graph. Local query DTOs will return canonical kind, ID, name,
canonical properties, and source provenance/evidence; FactMCP tools remain
thin wrappers around those DTOs. Source-specific OpenSpec fields are exposed
only as provenance, never as alternate canonical entity types.

This intentionally breaks callers that filter for `openspec-spec`,
`openspec-requirement`, `openspec-scenario`, or their former edge kinds.
Tests and documented query examples will move to canonical kinds and use
evidence source or locator data when they need OpenSpec-only context.

## Risks / Trade-offs

- [Natural keys may collide for independently authored concepts] -> Scope
  each key with the owning repository or canonical parent and reject
  incompatible records with the same ID.
- [OpenSpec change deltas may not exactly match durable requirements] -> Keep
  separate source evidence and only coalesce records with the defined
  canonical key; report conflicts rather than inferring equivalence.
- [Existing graph files contain stale IDs and endpoints] -> Perform an
  idempotent, validated atomic migration with a backup before replacement.
- [Breaking query contracts affect consumers] -> Update project-owned DTOs,
  FactMCP wrappers, CLI output, tests, and examples in the same change; do
  not maintain duplicate source-prefixed response shapes.
- [Evidence merging can make ordering nondeterministic] -> Sort all IDs and
  canonicalize serialized properties before merge and persistence.

## Migration Plan

1. Introduce the revised canonical node and edge vocabulary, natural-key
   helpers, and validation rules with unit fixtures for durable and
   change-scoped OpenSpec facts.
2. Update OpenSpec extraction to emit canonical facts plus OpenSpec evidence
   and retain only source-owned change/artifact entities; update derivation
   to consume the revised identities.
3. Implement and test in-memory persisted-snapshot migration, including ID
   and endpoint rewrites, evidence coalescing, validation failure, rerun
   idempotency, and backup/atomic replacement behavior.
4. Run migration before normal pipeline persistence, then update queries,
   DTOs, FactMCP wrappers, scripts, and test fixtures to the canonical
   contract.
5. Validate a migrated persisted snapshot and a clean rebuild produce the
   same canonical graph for equivalent OpenSpec input. On failure, restore
   the backup and stop the pipeline before exposing query results.

## Open Questions

- The initial natural keys need confirmation for canonical `service`,
  `repository`, `contract`, `decision`, `test`, and `work_item` as their
  adapters are introduced; this change defines the OpenSpec-backed
  specification hierarchy first.
- Determine the exact durable backup naming and retention policy for local
  graph files when implementing the persistence migration.
