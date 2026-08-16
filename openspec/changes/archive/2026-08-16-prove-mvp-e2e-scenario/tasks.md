## 1. Fixture Preparation

- [x] 1.1 Add or update one local non-Git workspace registry fixture that configures the full MVP stage sequence: `workspace-registry`, `openspec-store-source`, `openspec-graph-extraction`, `graph-derivation`, and `graph-integrity-validation`.
- [x] 1.2 Ensure the fixture represents independent implementation repositories, exactly one requirements/OpenSpec store repository, workspace-generated OpenLore state, and workspace-generated Engineering KG graph storage outside repository roots.
- [x] 1.3 Reuse existing OpenSpec fixture files where possible so the scenario includes durable specs, active or archived changes, requirements, scenarios, and derivable change-to-spec traceability.

## 2. Pipeline Composition

- [x] 2.1 Add an end-to-end pipeline test that runs `run_pipeline(...)` with the fixture registry, matching `RegisteredOpenSpecStore` input, and a temporary persistence path.
- [x] 2.2 Assert the complete configured and executed stage order is deterministic and includes persistence before derivation and validation after derivation.
- [x] 2.3 Assert the pipeline result includes deterministic metadata for OpenSpec store source validation, OpenSpec graph extraction, graph derivation, graph integrity validation, stage counts, and graph counts.
- [x] 2.4 Assert repeated runs with unchanged fixture inputs return stable serialized pipeline results.

## 3. Persistence And Query Proof

- [x] 3.1 Read the persisted graph through the existing persistence readback boundary instead of parsing adapter storage files directly.
- [x] 3.2 Construct local query access from the persisted graph store or readback snapshot.
- [x] 3.3 Assert query operations can list represented requirements, services, OpenSpec changes, and traceability relationships from the final graph.
- [x] 3.4 Assert query results are deterministic and based only on canonical or derived graph relationships.

## 4. Boundary And Local-First Verification

- [x] 4.1 Assert serialized pipeline results, persisted readback, and query outputs exclude source code, call graphs, dependency graphs, symbol bodies, OpenLore analysis payloads, full OpenSpec markdown bodies, Jira payloads, Bitbucket payloads, Confluence content, generated graph internals, credentials, tokens, and external API responses.
- [x] 4.2 Assert the scenario does not infer service implementation ownership from service names, repository hints, prompt context, or manually maintained non-confident metadata.
- [x] 4.3 Keep the E2E path local-first with no network, cloud, OpenLore MCP, Jira, Bitbucket, Confluence, compilation, publishing, semantic extraction, LLM, or credential dependency.

## 5. Validation

- [x] 5.1 Run `openspec validate prove-mvp-e2e-scenario` and fix any planning artifact issues.
- [x] 5.2 Run the focused Python test coverage for the pipeline runner, persistence, derivation, validation, and query APIs.
- [x] 5.3 Run the full local test suite if focused tests pass.
