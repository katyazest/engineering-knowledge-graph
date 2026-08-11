# Engineering KG MVP Backlog

| OpenSpec Change | Capability | User Story Intent |
| --- | --- | --- |
| `bootstrap-ekg-pipeline-runner` | `pipeline-runner` | As an EKG maintainer, I want a local Python pipeline runner, so that the MVP has a deterministic executable entry point for later stages. |
| `add-canonical-ontology-core` | `canonical-ontology` | As an EKG maintainer, I want canonical graph models for nodes, edges, evidence, and code locators, so that all pipeline stages exchange the same deterministic graph objects. |
| `evolve-repo-index-workspace-registry` | `workspace-registry` | As an EKG maintainer, I want `repo-index.yaml` to describe workspace repositories and service ownership, so that the graph can start from a stable local workspace inventory. |
| `add-ladybugdb-persistence-foundation` | `ladybugdb-persistence` | As an EKG maintainer, I want a local LadybugDB-compatible persistence boundary, so that canonical graph snapshots can be stored and read back deterministically. |
| `support-local-workspace-layout` | `workspace-registry` | As an EKG maintainer, I want the registry to support a non-git project workspace with workspace-level OpenLore, code repositories, one OpenSpec store repo, and local graph storage, so that generated state is separated from versioned requirements and source code. |
| `validate-workspace-openlore-source` | `openlore-source` | As an EKG maintainer, I want to validate the workspace-level OpenLore source, so that EKG can rely on OpenLore for code intelligence without duplicating the code graph. |
| `validate-openspec-store-repository` | `openspec-store` | As a system analyst, I want EKG to validate the requirements repository as the OpenSpec store, so that specifications and intended changes are extracted from the correct source of truth. |
| `extract-openspec-graph` | `openspec-extraction` | As a system analyst, I want EKG to extract OpenSpec changes, specifications, and requirements into canonical graph facts, so that intended behavior becomes traceable in the Engineering KG. |
| `derive-and-validate-mvp-graph` | `graph-derivation`, `graph-validation` | As a system analyst, I want EKG to derive deterministic relationships and validate graph integrity, so that broken links, missing mappings, and invalid traceability are detected before use. |
| `add-local-ekg-query-interfaces` | `graph-query-api`, `mcp-wrappers` | As an LLM agent user, I want local query APIs and thin MCP wrappers over the Engineering KG, so that agents can inspect requirements, services, changes, and traceability without duplicating graph logic. |
| `prove-mvp-e2e-scenario` | Multiple capabilities | As a system analyst, I want one end-to-end local MVP scenario, so that I can verify the full flow from workspace registry and OpenSpec store to local graph persistence, derivation, validation, and queries. |
