## Context

The MVP pipeline currently has a runnable local bootstrap runner and an empty status/result contract. The next MVP stage needs a canonical in-memory vocabulary for Engineering KG data before service registry loading, extractors, normalization, LadybugDB persistence, derivation, validation, or MCP wrappers are added.

The full project goal is a product-level Engineering Knowledge Graph that links services, repositories, requirements, specifications, OpenSpec changes, Jira stories, Bitbucket pull requests, contracts, provenance, deterministic relationships, and code locators while keeping OpenLore authoritative for code intelligence. The MVP scope is narrower: local-first, deterministic, no cloud dependency, no API keys, no publishing, and no semantic extraction.

## Goals / Non-Goals

**Goals:**

- Define minimal in-memory models for `Node`, `Edge`, `Evidence`, `CodeLocator`, `ConfluencePageRef`, and `GraphSnapshot`.
- Define a small fixed set of node and edge kind constants/enums that cover known MVP artifact families without service-specific logic.
- Provide deterministic stable ID generation for canonical objects.
- Provide JSON/dict serialization with stable ordering where relevant.
- Extend the existing pipeline runner result so an empty run includes an empty canonical graph snapshot.
- Keep all behavior local, deterministic, dependency-light, and independently testable.

**Non-Goals:**

- No LadybugDB persistence or database schema.
- No service registry YAML loading.
- No OpenSpec, Jira, Bitbucket, or OpenLore extraction.
- No OpenLore MCP calls and no duplication of OpenLore's code graph.
- No derivation rules beyond model-level ID helpers.
- No graph integrity validator beyond simple model invariants.
- No wiki, MkDocs, llmwiki-cli, dotMD, semantic extraction, cloud LLM, API key, compilation, or publishing behavior.

## Decisions

1. Use dependency-free Python dataclasses for the MVP ontology core.

   Pydantic is listed in the full development plan, but it is not installed in the current local environment. Adding it now would make the next change depend on package installation instead of remaining immediately testable. Dataclasses keep the MVP local-first and dependency-free. A later change can migrate or wrap these models with Pydantic if the enterprise environment provides the dependency.

2. Represent canonical graph data separately from pipeline execution status.

   `GraphSnapshot` should own graph content: nodes, edges, and evidence. `PipelineResult` should continue to own execution status and stage counts, and include a graph snapshot. This keeps orchestration concerns separate from canonical graph semantics.

3. Keep `CodeLocator` deliberately small.

   `CodeLocator` will include only `repository`, `revision`, `file`, and `symbol`, matching the MVP and full project constraints. It must not include class bodies, function signatures, call graphs, dependency graphs, metrics, or any other OpenLore-owned code intelligence details.

4. Keep Confluence page identity separate from page content.

   `ConfluencePageRef` will identify a Confluence source page by `page_id` only in this MVP slice. It must not fetch, embed, cache, or serialize Confluence page content, credentials, access tokens, URLs, comments, attachments, or sensitive production data. If later stages need richer Atlassian metadata, they can add it through a separate tested change.

5. Generate stable IDs from explicit object kind and normalized identity parts.

   Stable IDs should be deterministic across repeated runs with the same inputs. The implementation can use a canonical string format and a standard-library hash. This avoids random UUIDs and avoids relying on database-assigned IDs before persistence exists.

6. Use plain dictionaries for extensibility, but keep required identity fields explicit.

   Nodes and edges can carry `properties` for future stage-specific metadata, while required fields such as `id`, `kind`, and endpoints remain explicit. This balances early flexibility with a stable core contract.

## Risks / Trade-offs

- Dataclasses provide less runtime validation than Pydantic -> Keep model invariants small and covered by tests; revisit Pydantic in a later dependency-focused change if needed.
- A too-large enum set can freeze premature ontology decisions -> Start with a minimal set for known artifact families and allow later OpenSpec changes to add kinds as stages need them.
- A too-flexible `properties` map can hide inconsistent modeling -> Keep identity and relationship fields explicit, and defer broader validation rules to a later validation stage.
- Confluence identifiers may be confused with page content access -> Store only `page_id` in this change and keep Confluence extraction/MCP behavior out of scope.
- Changing `PipelineResult` can affect existing tests -> Update bootstrap tests in the same change so the runner contract remains explicit and deterministic.
