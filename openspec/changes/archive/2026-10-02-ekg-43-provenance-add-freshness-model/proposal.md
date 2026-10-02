## Why

Plane task `EKG-43` (`8a974c15-bb39-4bfb-b633-291d78a7c163`, sourced from `EKG-07`) requires agents to know whether graph evidence may be out of date relative to its authoritative source. EKG-40 supplies immutable revision-bearing provenance, but a stored observation timestamp or revision alone cannot establish that the source is still at that revision; treating old evidence as current would mislead queries and current-evidence readiness decisions.

## What Changes

- Define `fresh`, `stale`, and `unknown` assessments for external observations and derived evidence using retained source revision/version, extraction metadata, and an explicitly checked current revision for the same authoritative artifact. No age-only inference or unverified source resolution.
- Return per-support freshness and its comparison basis through local fact/traceability queries and the existing agent-facing query wrappers, including `unknown` when a current revision cannot be checked.
- Provide a reusable current-evidence eligibility guard: a check that explicitly requires current evidence cannot count stale or unknown support as current, without introducing new readiness policies or changing existing trust classifications.
- Preserve fact/provenance IDs, source payload boundaries, deterministic merge, and existing persistence format: freshness is assessed against a supplied checked revision, not written into immutable historical provenance.

## Capabilities

### New Capabilities
- `evidence-freshness`: Tri-state assessment, source-revision comparison contract, derived-chain semantics, current-evidence eligibility, and verification matrix.

### Modified Capabilities
- `local-ekg-query-api`: Expose freshness per represented evidence/provenance support in existing fact and traceability query results, with an optional checked-revision input.
- `ekg-mcp-query-wrappers`: Preserve the query freshness projection and optional checked-revision input for existing agent-facing tools without duplicating assessment logic.

## Impact

- Project-owned provenance-assessment logic, local query DTOs, thin MCP query wrappers, documentation, and fixture-based tests are affected; graph extraction/derivation and persistence retain their existing immutable facts and IDs. Query response shapes gain additive freshness fields; existing callers without checked revisions receive `unknown` rather than a guessed status.
- Canonical stored provenance schemas and persisted graph data are **not** changed; the ephemeral freshness assessment input/output model and public query surface are changed. No migration or external infrastructure configuration is needed.
- Graphify, Jira MCP, Bitbucket MCP, OpenLore, and LadybugDB remain external identity/source/storage boundaries. This repository does not implement their internals or call them during freshness assessment; any current revision must be checked outside the graph and passed in by the caller.
- Non-goals: downstream EKG-64 agent rules or EKG-67 diagnostics, source polling or index freshness, timestamp TTLs, confidence/trust promotion, invented source revisions, retroactive readiness decisions, or a new release/readiness workflow. Plane supplies no explicit acceptance criteria or list of critical checks; this change defines a current-required guard but does not designate new checks as critical.
