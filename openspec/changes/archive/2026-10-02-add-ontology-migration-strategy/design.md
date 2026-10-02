## Context

Plane task `EKG-66` establishes the missing compatibility boundary for persisted Engineering Knowledge Graph snapshots. The current `graph.json` document carries only `catalog_revision`, which describes the relationship catalog but is being used as a broad persistence-format gate. `persistence.py` has a migration result type, an explicit pipeline stage, backup naming, and historical helper fragments, yet `read_snapshot`, `write_snapshot`, and `migrate_persisted_snapshot` currently reject any non-current catalog revision and do not identify a complete ontology schema version or migration chain.

The repository already defines the target semantics for the original canonicalization: retired `openspec-spec`, `openspec-requirement`, and `openspec-scenario` facts become canonical specification, requirement, and scenario facts using existing natural keys; approved structural, assertion, traceability, and related-spec mappings are rewritten with their references. Existing provenance, PR-evidence, verification, merge-conflict, relationship-catalog, and graph-integrity contracts remain authoritative. Where retained source data cannot meet one of those contracts, it must fail closed rather than be reconstructed.

This change affects only project-owned Python modules and logical snapshot fixtures. LadybugDB remains an external storage boundary; the local adapter currently uses JSON but must not become the owner of migration semantics. Graphify, Jira MCP, Bitbucket MCP, OpenLore, llmwiki-cli, and MkDocs are neither called nor modified.

## Goals / Non-Goals

**Goals:**

- Establish `ontology_schema_version: 1` as the explicit, top-level version of the project-owned logical snapshot envelope, separate from `catalog_revision`.
- Provide a reusable, deterministic, forward-only migration core that transforms raw logical documents before current-format decoding.
- Make source compatibility explicit: recognize only the two versionless source descriptors needed now, the current-canonical v4 shape and the already-approved OpenSpec-prefixed canonicalization shape, and provide a registry pattern for future adjacent version transitions.
- Preserve stable identities, evidence, provenance, relationship direction, derived-versus-asserted distinction, ordering, and idempotency whenever the approved source data supports them.
- Validate the complete target graph and commit it atomically with a recoverable source backup; fail without source replacement in every unsupported or invalid case.
- Expose payload-safe migration outcome metadata through the existing pipeline migration stage.

**Non-Goals:**

- Add a new graph database, query a database natively, or implement database-specific DDL, migration scripts, transactions, or configuration.
- Treat an absent schema version as automatically current, migrate arbitrary historical document shapes, or support downgrade/rollback conversion.
- Infer missing natural keys, relationship direction/meaning, provenance, PR base/head revisions or associations, verification evidence, trust, lifecycle, or implementation conclusions.
- Change current in-memory `GraphSnapshot` construction, extraction, derivation, query DTO semantics, or relationship admission other than routing persisted legacy conversion through the new boundary.
- Define a source-authority ranking, retain external payloads, or perform external acquisition while migrating.

## Decisions

### 1. Version the logical snapshot envelope, not `GraphSnapshot` or a database store

Add `ontology_schema_version` to the root of the serialized graph document. It is a positive JSON integer; `1` is the first explicit version and represents the repository's current canonical persisted representation. Serialization for an empty store, a new write, and any successful migration always emits `1`.

`GraphSnapshot` remains the current, storage-agnostic in-memory model. It does not gain a persistence-version field because callers construct current facts and should not choose historical compatibility behavior. The existing `catalog_revision` remains present as relationship-contract metadata. A per-schema-version format descriptor binds the expected catalog revision, so a mismatched catalog revision is invalid, but the revision never acts as a substitute for schema-version selection.

This separates full document evolution (collections, record fields, identity interpretation, and relationships) from catalog-only changes. It also means future storage adapters can exchange the same logical document without copying the LadybugDB adapter's metadata conventions.

Alternative: use `catalog_revision` as the only compatibility key. Rejected because non-relationship fields have evolved independently and catalog revision cannot describe a complete schema transform. Alternative: add the version to every graph record or `GraphSnapshot`. Rejected because it creates redundant per-record state, complicates identity/merge contracts, and couples current callers to historical storage format.

### 2. Extract a pure logical codec and migration core below the persistence adapter

Split the existing serialization/deserialization helpers into an internal logical snapshot codec, for example `engineering_kg.snapshot_codec`, and add an internal `engineering_kg.snapshot_migration` module. The codec owns deterministic document serialization and current-format reconstruction/validation. The migration module owns only:

- source descriptor matching and version parsing;
- the ordered migration registry;
- pure `Mapping[str, object] -> Mapping[str, object]` transitions;
- post-transform current-codec and graph-integrity validation; and
- a payload-safe `SnapshotMigrationResult`.

The migration module performs no filesystem, storage adapter, LadybugDB, database-driver, or network operation. It may call current canonical identity, relationship-vocabulary, provenance, merge, and graph-integrity APIs through the codec. The persistence adapter owns reading raw bytes into a mapping, committing an approved target document, and mapping migration errors into `PersistenceIntegrityError` without adding storage details to diagnostics.

Existing unreachable legacy migration code in `persistence.py` must be either moved into named, covered migration transitions or removed. The implementation must not retain dead alternate conversion paths that can drift from the registry.

Alternative: leave transformations embedded in `LadybugDbStore`. Rejected because it duplicates the logical contract in each future adapter and violates the required database independence. Alternative: deserialize every source using `GraphSnapshot` and migrate objects. Rejected because historical raw documents can fail current decoding before an object exists; source recognition and conversion need the raw logical document first.

### 3. Use strict source descriptors and adjacent forward transitions

The registry classifies a raw document before decoding it as current. A source descriptor has a stable identifier, strict matcher, source-version representation, target version, expected source invariants, and one pure transform. Matching is deterministic and mutually exclusive; a document matching zero or more than one descriptor fails before any transformation.

The initial registry contains exactly these compatibility entries:

1. `unversioned-current-canonical-v4` accepts only a document without `ontology_schema_version`, with the current relationship catalog revision, and with record shapes that already pass current decoding and validation. Its transition only adds `ontology_schema_version: 1`; it does not reinterpret graph data.
2. `unversioned-openspec-prefixed-canonicalization` accepts only a versionless legacy document whose retired OpenSpec node/edge shapes and retained evidence/provenance can satisfy the existing canonicalization requirements. It rewrites the known `openspec-*` domain node identities, affected endpoints, edge identities, and derived-edge input references; it coalesces only compatible canonical records and emits the current catalog revision and schema version.

The second transform reuses the approved mappings only: OpenSpec specification, requirement, and scenario hierarchy maps to the current canonical natural keys and `CONTAINS`; source assertion, derived traceability, and related-spec records map only to their approved current support or relationship representation. It does not reverse an edge, map an unknown label, or create any relationship not already specified by the existing canonicalization and catalog contracts. Legacy evidence and provenance use the same retained-field sufficiency check; legacy PR and verification records have no new inference path and are rejected if their target fields are incomplete.

Future schema changes must introduce a named `N-to-N+1` transition and version descriptor rather than modifying an earlier transform or writing a direct `N-to-current` shortcut. The registry resolves every adjacent step before running it, rejects a gap and rejects declared versions newer than the runtime. This makes the supported compatibility window visible in source control and keeps a future transform independently testable.

Alternative: infer source version from arbitrary labels, field absence, or input order. Rejected because it could apply a destructive mapping to an unknown document. Alternative: accept every old catalog revision and normalize it generically. Rejected because a relationship revision is insufficient evidence for natural-key, provenance, PR, verification, and trust compatibility. Alternative: rebuild data from external sources. Rejected because migration must work locally without external calls and must preserve supported persisted evidence.

### 4. Make migration transactional at each persistence operation

The persistence adapter follows this flow:

`load raw document` → `classify source descriptor/version` → `run complete in-memory migration chain` → `current codec + canonical validation + graph-integrity validation` → `optional current write merge and validation` → `write recoverable source backup` → `atomically replace document` → `current readback`.

`migrate_persisted_snapshot` executes the migration portion and commits only when it changes a document. `read_snapshot` invokes that path before exposing graph data, preserving the existing pipeline expectation that migration occurs before downstream stages. `write_snapshot` obtains the migrated current candidate in memory, merges the incoming current snapshot, and validates the full prospective document before a single backup/replacement; an incoming merge failure must therefore leave an older source document untouched rather than applying a schema-only upgrade incidentally.

For a real migration, the adapter writes a byte-equivalent backup of the original raw document in the store before replacing the graph. Use a deterministic, source-descriptor/version-qualified sibling backup name so diagnostics and restore instructions identify the source without embedding paths or content in public metadata. If an existing backup would be overwritten by non-equivalent data, backup creation fails rather than discarding recovery information. Existing `ontology_schema_version: 1` documents are no-ops and neither write nor replace a backup.

The adapter writes the target through the existing temporary-file-plus-atomic-replace mechanism. No source bytes are replaced until classification, every migration step, target decode, complete graph validation, and backup creation succeed. Failure leaves the original graph readable by a compatible earlier runtime or recoverable from the backup; it never exposes a partially migrated graph.

Alternative: migrate as a side effect of `read_snapshot` before validation. Rejected because malformed data could be written back. Alternative: commit each transition in a chain. Rejected because it risks an intermediate schema becoming persistent. Alternative: require a separate manual command only. Rejected because existing persistence and pipeline contracts require migration before normal readback/downstream use.

### 5. Treat migration result metadata as a safe operational contract

Enrich the existing `OntologyMigrationResult` (or adapt it from the new core result) with source schema version or source descriptor, target schema version, ordered applied migration identifiers, status, existing migrated node/edge counts, safe diagnostics, and final graph counts. Its `migrated` state must be true when a version-marker-only transition ran even if no graph record count changed.

`PipelineResult.as_dict()` continues to expose migration only when attempted, but supplies the enriched metadata. On migration failure it returns the existing deterministic failed status with no downstream stage execution. Diagnostics contain stable rule/migration identifiers, record IDs, and version identifiers only; they must omit paths, raw data, source bodies, competing values, provider payloads, credentials, and tokens.

Alternative: retain only node/edge counts. Rejected because a successful envelope-only migration would look like a no-op and an operator could not determine source compatibility safely. Alternative: expose raw documents or storage paths for debugging. Rejected because persistence metadata must remain payload-safe and storage-independent.

## Data Flow

For a supported legacy document:

`raw logical document` → `strict descriptor` → `registered pure transform(s)` → `current logical document (schema v1 + expected catalog revision)` → `codec reconstruction` → `identity/provenance/catalog/integrity validation` → `backup` → `atomic adapter commit` → `current GraphSnapshot` → `pipeline derivation/validation/query stages`.

For a current document, the descriptor is not invoked: version and catalog validation lead directly to current decoding and a `not-needed` result. For a malformed, unsupported, ambiguous, future, unchained, or invalid source document, the flow stops before backup, commit, graph readback, or pipeline downstream stages.

## Risks / Trade-offs

- [Versionless historical documents could resemble more than one descriptor] → Require strict, mutually exclusive descriptor predicates and fail ambiguity rather than selecting a migration.
- [A historical source lacks required identity, provenance, PR, or verification data] → Preserve the source unchanged and emit a safe compatibility failure; never backfill values from labels, paths, timestamps, or external systems.
- [A version-marker-only migration could be mistaken for a no-op] → Include applied migration IDs and source/target versions in the result and test that status explicitly.
- [A backup collision could destroy recovery evidence] → Use source-qualified backup names and reject non-equivalent overwrite attempts.
- [Migration and current codec logic drift] → Centralize all current serialization/decoding in the logical codec and use it for both direct persistence and post-migration validation.
- [Full-document migration has memory cost] → The local snapshot contract is already in-memory and correctness/atomicity take precedence; streaming or database-native execution is a future adapter-specific optimization that must preserve this logical contract.
- [Future changes add a schema version without a transition] → Make an adjacent transform, expected catalog revision, matrix fixture, and registry entry mandatory in the version-bump task.

## Migration Plan

1. Extract the deterministic current logical snapshot codec from the persistence adapter without changing current snapshot output other than adding the version marker on writes and empty-store initialization.
2. Add version parsing, source descriptors, pure migration registry/result types, and the two initial transforms; move only audited existing canonicalization helpers into the OpenSpec-prefixed transform and delete unreachable duplicate paths.
3. Route `LadybugDbStore` read, explicit migrate, and write paths through in-memory migration, final validation, version-qualified backup, and one atomic replacement. Preserve current merge conflict and payload-safety behavior.
4. Extend pipeline migration metadata and failed-stage handling with source/target version and applied-transition fields; do not add a new pipeline stage or external configuration.
5. Add fixture matrices for current v1, versionless-current marker upgrade, supported OpenSpec canonicalization, every invalid/unsupported class, backup/atomicity, rerun idempotency, and core-versus-adapter equivalence. Run targeted ontology, relationship, persistence, pipeline, and full local tests.
6. Deploy with the migration-capable runtime before introducing any subsequent persisted ontology version. A successful source backup supports operational rollback: restore the backup and run the earlier compatible runtime. Do not attempt an automatic downgrade or use rollback to admit a snapshot that failed validation.

## Open Questions

None. The initial compatibility set is deliberately limited to documented legacy descriptors; a newly discovered historical shape requires a separately approved source descriptor and migration matrix row.
