## Why

Plane task `98f0f78a-5d98-40b2-8cd2-21d6b924c201` (`EKG-09`) requires a durable way to record prospective relationships between Engineering KG facts and OpenLore-resolvable code without treating unverified observations as semantic truth. The current ontology can retain individual evidence and `CodeLocator` references, but it has no attributable, lifecycle-aware cross-graph link record through which current and future linking strategies can accumulate support.

## What Changes

- Define a canonical cross-graph link-evidence model whose code-side target is a complete, stable `CodeLocator` identity.
- Represent candidate link evidence separately from a trusted semantic link, including the proposed EKG subject, semantic relation, linking-strategy attribution, and lifecycle state.
- Allow multiple attributable evidence observations to accumulate for one proposed link without changing either the proposed link identity or the target locator identity.
- Define deterministic serialization, stable identifiers, merge behavior, validation boundaries, and persistence compatibility for cross-graph link records.
- Preserve the ownership boundary: OpenLore remains authoritative for code intelligence and symbol resolution; this change stores locator identity and link evidence only.

## Capabilities

### New Capabilities
- `cross-graph-link-evidence`: Canonical, attributable, lifecycle-aware evidence records for proposed and trusted links from EKG facts to OpenLore-resolvable code locators.

### Modified Capabilities
- `canonical-ontology`: Extend the in-memory canonical graph contract with stable cross-graph link evidence and trusted-link representations while preserving existing graph records.

## Impact

- Affects project-owned canonical ontology, graph merge/serialization and validation behavior, the LadybugDB-compatible persistence adapter, and focused unit/integration tests.
- Does not require a live OpenLore instance, OpenLore MCP calls, Graphify changes, network access, or changes to external infrastructure. OpenLore is involved only as the resolver and owner of details behind the stored `CodeLocator` target.
- Canonical schemas and persisted graph data are affected. Existing snapshots without cross-graph link records must remain readable; no external-infrastructure configuration is introduced.
