## Why

Plane task `EKG-66` requires an explicit, safe strategy for evolving persisted Engineering Knowledge Graph snapshots. The current persistence boundary overloads relationship-catalog revision as a readback guard and contains historical migration paths without a durable schema-version contract, leaving canonical ontology and relationship refactors either ambiguously handled or rejected without a defined compatibility policy.

## What Changes

- Define a persisted logical snapshot schema version, its top-level location, and its relationship to the existing relationship-catalog revision.
- Add a deterministic, forward-only migration policy and reusable migration boundary for supported snapshot versions, including the already-defined OpenSpec-prefixed-to-canonical ontology transition when its retained natural-key and provenance data is sufficient.
- **BREAKING** require persisted snapshots to declare a supported ontology schema version after migration; missing, malformed, future, or otherwise unsupported versions fail before graph data is exposed or replaced.
- Preserve fail-closed admission for legacy data whose required facts cannot be reconstructed; migration must not invent canonical identities, relationship direction, provenance, PR evidence, verification facts, or trust decisions.
- Integrate version migration with local persistence and pipeline migration reporting while keeping the migration logic independent of LadybugDB or any future graph-database implementation.
- Add fixture-based migration, compatibility, failure-atomicity, and idempotency coverage.

## Capabilities

### New Capabilities

- `ontology-snapshot-migration`: Versioned logical snapshot contract, migration-chain policy, compatibility diagnostics, and migration verification matrix.

### Modified Capabilities

- `canonical-ontology`: Limit canonical in-memory admission to the current ontology while allowing explicitly versioned persisted-snapshot migration to produce that current representation.
- `canonical-relationship-vocabulary`: Distinguish current-format relationship admission from approved, version-scoped persisted relationship conversions.
- `ladybugdb-persistence`: Store the logical snapshot schema version and invoke validated, atomic migrations through the storage adapter without making LadybugDB the migration owner.
- `pipeline-runner`: Report deterministic, payload-safe version-migration outcome metadata and stop downstream stages when migration fails.

## Impact

Affected project-owned components are the canonical snapshot serialization contract, ontology and relationship migration helpers, persistence adapter, pipeline migration result, and fixture-based tests. Persisted `graph.json` snapshots are affected; valid supported historical snapshots may be rewritten only after validation and backup, while unsupported snapshots remain untouched. LadybugDB is an external storage integration boundary only: this change neither changes its internals nor adds database-specific schema migrations, infrastructure configuration, network access, or external-service calls. The proposal is traceable to Plane task `EKG-66`.
