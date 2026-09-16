## Why

Plane task EKG-49 (source backlog item EKG-26; depends on EKG-25) requires an auditable answer to whether an OpenSpec requirement or scenario has an explicitly mapped acceptance or other relevant test, and whether that mapped test has executed. The verification ontology added by EKG-48 can represent tests and runs, but it does not yet admit declared OpenSpec-to-test mappings, distinguish mapping absence from execution absence, or expose reliable test-to-code evidence to cross-graph linking.

## What Changes

- Add a project-owned, versioned declarative test-traceability input that maps durable or change-scoped OpenSpec requirements and scenarios to stable test identities; mapping is explicit and deterministic rather than based on test-name similarity.
- Normalize declared mappings, optional test-execution observations, and optional reliable test-to-code resolution outcomes into the existing source-neutral verification ontology with complete evidence and provenance.
- Emit only catalog-valid `VERIFIED_BY` and `EXECUTED_IN` relationships for admitted mappings and executions; represent a reliable test-to-code result only as attributable, non-implementing cross-graph evidence.
- Add deterministic validation, pipeline metadata, and query projections that separately report: no declared test mapping, mapped tests with no represented execution, and represented execution evidence.
- Preserve source-neutral identities, payload-free graph/query boundaries, explicit trust/lifecycle rules, and the prohibition on treating tests or test-code associations as `IMPLEMENTS` evidence.
- Do not infer mappings from test names, requirement text, paths, source-code similarity, execution outcomes, coverage, or generic code reachability. Do not add a test runner, CI integration, coverage engine, or direct Graphify/OpenLore/CI network integration.

## Capabilities

### New Capabilities
- `scenario-test-traceability`: Declared OpenSpec requirement/scenario-to-test mapping, execution-observation admission, reliable test-to-code candidate evidence, deterministic diagnostics, and mapping/execution status classification.

### Modified Capabilities
- `openspec-graph-extraction`: Read and evidence the approved declarative traceability input from the validated OpenSpec store without changing canonical OpenSpec target identities.
- `canonical-relationship-vocabulary`: Register the source mappings and endpoint-conformant semantics for declared test traceability and test-to-code evidence.
- `graph-integrity-validation`: Validate declared test traceability references, execution bindings, and test-to-code candidate boundaries deterministically.
- `cross-graph-link-evidence`: Retain attributable reliable test-to-code observations as non-implementing candidate evidence without altering trust or lifecycle rules.
- `local-ekg-query-api`: Expose deterministic per-target mapping and execution states together with represented verification and test-to-code evidence.
- `pipeline-runner`: Run the optional local traceability-admission stage after OpenSpec graph extraction and before persistence, derivation, and validation.

## Impact

- **Project-owned code:** a reusable traceability normalizer/extractor, OpenSpec extraction, relationship catalog, graph validation, pipeline orchestration/result metadata, local query DTOs, and fixture-based tests.
- **Pipeline stages:** validated OpenSpec extraction supplies canonical requirement/scenario targets; the new optional traceability-admission stage merges declared mappings and supplied local execution/code-resolution inputs before persistence and integrity validation.
- **Integration boundary:** a future test framework, CI system, or Graphify/OpenLore-backed resolver may provide normalized, payload-free execution or exact code-resolution input. Their execution, reporting, and provider implementations remain outside this repository and are never called by the default local pipeline.
- **External infrastructure:** Graphify, OpenLore, test frameworks, CI vendors, Jira MCP, Bitbucket MCP, and LadybugDB are not modified. LadybugDB remains behind the existing project-owned persistence adapter.
- **Canonical/persisted data:** existing generic verification nodes, edges, evidence, provenance, and cross-graph candidate collections are populated with new admitted records; compatibility impact, if a persisted-schema revision is required, will be decided by the design after confirming the current codec contract.
- **Traceability:** this change implements Plane task EKG-49 and preserves the task's P0 source backlog traceability to EKG-26.
