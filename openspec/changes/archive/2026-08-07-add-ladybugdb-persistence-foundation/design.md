## Context

The current MVP pipeline has three working local-first foundations: a reusable runner, canonical in-memory ontology objects, and a workspace registry stage that turns stable repository topology into a `GraphSnapshot`. The product docs define LadybugDB as the canonical Engineering Knowledge Graph store, but the repository currently has no persistence boundary and no concrete LadybugDB integration.

This change is the persistence foundation only. It should make canonical graph snapshots durable locally while preserving the rule that OpenLore owns code intelligence and LadybugDB stores engineering knowledge plus `CodeLocator` identity references.

## Goals / Non-Goals

**Goals:**

- Add a reusable persistence module that can initialize a local Engineering KG store.
- Persist and read back canonical `GraphSnapshot` content deterministically.
- Keep persistence independent from scripts and future MCP wrappers.
- Integrate persistence as an optional pipeline stage after graph-producing stages.
- Keep tests local, deterministic, and independent of live external infrastructure.
- Preserve the existing empty bootstrap and workspace-registry-only runner behavior.

**Non-Goals:**

- No OpenLore MCP calls, OpenLore index creation, or code graph duplication.
- No Jira, Bitbucket, Confluence, or enterprise MCP extraction.
- No OpenSpec extraction beyond using existing planning artifacts as requirements context for this change.
- No graph derivation, broad validation engine, projections, generated wiki, MkDocs, llmwiki-cli, or dotMD.
- No cloud LLMs, API keys, publishing, compilation, Docker, or package release workflow.
- No final semantic schema migration for every future node and edge kind beyond what the current canonical ontology requires.

## Decisions

1. Add a persistence boundary under reusable package code.

   Persistence should live behind a small module/API in `src/engineering_kg/`, for example a storage or persistence package, rather than inside `scripts/build.py`. The script remains a wrapper over reusable functions so the same behavior can later be exposed through MCP without duplicating business logic.

   Alternative considered: write directly from the build script. Rejected because it would violate the existing architecture rule: scripts and future MCP wrappers call reusable Python modules.

2. Treat `GraphSnapshot` as the persistence input and readback output.

   The persistence API should accept canonical ontology objects and return canonical ontology objects, not raw database rows. This keeps stage boundaries stable: upstream stages produce graph snapshots, persistence stores them, and downstream derivation/validation can read the same contract.

   Alternative considered: expose LadybugDB-native records throughout the pipeline. Rejected because it would leak storage details into extractors and make later adapter changes harder.

3. Use deterministic upsert semantics keyed by canonical IDs.

   Persisted nodes, edges, and evidence should be keyed by their stable IDs. Running the same pipeline input repeatedly should produce the same stored graph and the same readback serialization rather than duplicate records.

   Alternative considered: append every run as new records. Deferred because the MVP needs deterministic current-state behavior first; run history/provenance can be added later if needed.

4. Use the confirmed LadybugDB dependency through a narrow adapter boundary.

   LadybugDB is available locally as the global Node package `@ladybugdb/core@0.19.1`. The package exposes an in-process Node API (`Database`, `Connection`, query/prepare/execute helpers) and does not install a `ladybugdb` CLI command. The active project Python environment does not expose an importable LadybugDB package, so implementation should isolate persistence behind a local adapter interface. The first MVP implementation can satisfy the canonical persistence contract with deterministic local storage, while a later adapter can bind to `@ladybugdb/core`, a Python `ladybug` binding, or an approved CLI without changing pipeline callers.

   Alternative considered: design directly against an assumed LadybugDB API. Rejected because inventing an API would make the MVP brittle and harder to transfer to the isolated enterprise machine.

5. Store only canonical Engineering KG data and locator identities.

   Persistence must store canonical node, edge, evidence, `CodeLocator`, and `ConfluencePageRef` serialized fields. It must not store source code, call graphs, dependency graphs, function bodies, class bodies, OpenLore analysis payloads, fetched Confluence page content, credentials, tokens, or external API responses.

   Alternative considered: cache external records for convenience. Rejected because it conflicts with the ownership boundaries and enterprise safety constraints.

6. Make persistence opt-in through pipeline configuration.

   The runner should preserve current behavior when no persistence output is configured. When a registry or explicit pipeline configuration includes a persistence stage and output path, the runner should execute persistence after graph objects are produced and report the stage deterministically.

   Alternative considered: always write a database for every run. Rejected because existing bootstrap smoke tests and local exploration benefit from side-effect-free runs.

## Risks / Trade-offs

- LadybugDB is installed as a Node package while the MVP runner is Python-based -> Keep a narrow Python persistence boundary and defer Node bridge or Python binding selection to a later adapter-focused change.
- Upsert semantics may hide historical changes -> Treat run history as a later capability; MVP validates deterministic current-state persistence first.
- A generic serialized graph can become a dumping ground -> Persist only fields from canonical ontology models and add tests for forbidden OpenLore/code/content payloads.
- Optional persistence configuration can make runner behavior harder to reason about -> Report configured and executed stages explicitly, preserving existing deterministic stage counts.
- Real LadybugDB constraints may require schema adjustments later -> Keep this change focused on initialization, write, and readback so later migration work is explicit.

## Migration Plan

This is an additive MVP change. Existing bootstrap and workspace-registry tests should continue to pass without persistence configuration. New tests should use temporary local storage paths and clean them up through test fixtures.

Rollback is straightforward: disable the persistence stage in pipeline configuration and the runner should return the same in-memory graph behavior as before.

## Open Questions

- Should persisted graph state represent only the latest snapshot, or should run history become a separate future capability?
