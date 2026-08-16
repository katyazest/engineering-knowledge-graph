## Context

The Engineering KG MVP is intentionally local-first and deterministic. Existing capabilities already define individual contracts for loading the workspace registry, selecting the OpenSpec store source, extracting OpenSpec graph facts, persisting canonical graph snapshots through the LadybugDB-compatible adapter boundary, deriving relationships, validating graph integrity, and querying graph facts.

The missing piece is a single representative local run that proves these contracts compose correctly. The scenario must be useful to a system analyst validating the full requirements-to-graph flow while preserving service boundaries and avoiding source-owned payloads, external systems, credentials, OpenLore-owned code intelligence, and generated graph internals in durable or queryable outputs.

## Goals / Non-Goals

**Goals:**

- Prove one full local MVP flow from `repo-index.yaml` and OpenSpec store source to persisted, derived, validated, and queryable Engineering KG facts.
- Keep the scenario deterministic across repeated runs with the same fixture input and local filesystem shape.
- Reuse the existing pipeline runner, persistence boundary, derivation, validation, and query API contracts.
- Verify the final graph through user-facing query APIs, not by asserting only internal storage files.
- Preserve the existing boundary that OpenLore owns code intelligence and the Engineering KG stores only canonical facts and locator identities.

**Non-Goals:**

- Replace the adapter-compatible local persistence implementation with the native LadybugDB Node API.
- Add cloud, network, Jira, Bitbucket, Confluence, OpenLore MCP, semantic extraction, LLM, compilation, publishing, or credential dependencies.
- Add a generalized scenario framework or multiple scenario suites.
- Infer service implementation ownership from names, repository hints, or manually maintained OpenSpec metadata.
- Store source code, OpenSpec markdown bodies, external-system payload bodies, generated graph internals, credentials, or tokens in scenario outputs.

## Decisions

### Use one fixture-backed E2E scenario

The E2E proof should use one focused fixture workspace under the existing test fixture area. The fixture should represent the MVP layout: a non-Git project workspace, independent implementation repositories, one requirements repository registered or supplied as the OpenSpec store, configured local graph storage, and pipeline stages covering the full MVP sequence.

Alternative considered: reuse only existing stage-specific fixtures. That keeps fixtures small but does not prove the combined stage ordering, persistence readback, derivation, validation, and query behavior in one run.

### Verify through public module boundaries

The scenario should invoke `run_pipeline(...)` with a registry path, local persistence path, and deterministic OpenSpec store discovery input. It should validate the returned `PipelineResult`, then construct query access from the persisted graph store through the existing persistence readback boundary.

Alternative considered: inspect the persisted `graph.json` adapter file directly. That would overfit to the current adapter internals and weaken the future path to a native LadybugDB bridge.

### Keep scripts thin

Any script-level coverage should confirm that script wrappers delegate to reusable Python modules and report deterministic stage metadata. The script should not implement graph traversal, query filtering, derivation rules, validation rules, or persistence internals.

Alternative considered: add E2E orchestration logic directly to `scripts/build.py`. That would make the script harder to test and would duplicate behavior owned by reusable modules.

### Treat query results as the final analyst-facing proof

The scenario should assert that local query APIs can list requirements, services, OpenSpec changes, and traceability from the final graph. These assertions prove the output is usable for analyst navigation without requiring direct knowledge of storage internals.

Alternative considered: stop after graph validation. That proves graph shape but not that downstream agent-facing query contracts can consume the graph correctly.

### Preserve deterministic ordering and explicit boundaries

The scenario should assert exact configured and executed stage order, stable serialized results for repeated runs, and absence of forbidden payload fields in serialized pipeline and query outputs. Query assertions should use graph relationships already present or deterministically derived, and should not depend on prompt context or service-name matching.

Alternative considered: use broad count-only assertions. Counts are useful smoke checks, but they do not catch accidental stage reordering, missing traceability, or boundary leaks.

## Risks / Trade-offs

- Fixture becomes too broad and brittle -> Keep the scenario to one representative MVP path and assert stable public contracts rather than incidental object ordering beyond deterministic API output.
- Existing stage fixtures diverge from the E2E fixture -> Reuse fixture patterns and data shapes already covered by stage-specific tests where possible.
- Persistence assertions overfit to the current JSON adapter -> Read persisted data through `read_graph_snapshot(...)` or query APIs instead of parsing adapter files directly.
- Query assertions accidentally encode unsupported inference -> Use only graph object IDs, capability identities, and relationships produced by extraction or derivation.
- Stage failures become hard to diagnose in one large test -> Keep stage metadata assertions explicit so failures identify the stage that did not execute or returned invalid metadata.

## Migration Plan

1. Add the new and modified OpenSpec requirements for the E2E scenario and full runner composition.
2. Add or extend one local fixture registry so it configures the complete MVP sequence.
3. Add focused E2E tests that run the pipeline with a temporary persistence path, assert deterministic pipeline output, validate persisted readback, and query the final graph through public APIs.
4. Add script wrapper coverage only where needed to prove delegation and deterministic observable output.
5. Keep existing stage-specific tests in place as the lower-level diagnostic coverage.

Rollback is straightforward because the change is local and test-scoped: remove the E2E fixture/test additions and any small runner or wrapper composition changes introduced for the scenario.

## Open Questions

- Should the E2E scenario use only an injected `RegisteredOpenSpecStore` test input, or should it also exercise real `openspec store list` discovery through a wrapper layer?
- Should the build script accept a persistence path and registered store selection for this scenario, or should those remain reusable Python API inputs only for the MVP?
