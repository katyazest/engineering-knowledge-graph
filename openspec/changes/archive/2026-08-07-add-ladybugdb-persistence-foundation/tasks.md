## 1. LadybugDB Dependency and Adapter Boundary

- [x] 1.1 Confirm the exact LadybugDB project dependency, Python import name, and minimal API for local store initialization, graph writes, and graph reads.
- [x] 1.2 Add or document the project dependency wiring needed for the active project environment to import LadybugDB.
- [x] 1.3 Create a reusable persistence module under `src/engineering_kg/` with a narrow adapter boundary that hides LadybugDB-native APIs from pipeline stages.
- [x] 1.4 Define explicit persistence errors for initialization, write, readback, and integrity failures.

## 2. Graph Snapshot Persistence

- [x] 2.1 Implement local Engineering KG store initialization at a configured filesystem path.
- [x] 2.2 Implement deterministic persistence for canonical `Node`, `Edge`, and `Evidence` objects keyed by stable IDs.
- [x] 2.3 Implement readback from the local store into canonical `GraphSnapshot` objects.
- [x] 2.4 Implement idempotent upsert behavior so repeated writes of the same snapshot do not duplicate stored objects.
- [x] 2.5 Preserve `CodeLocator` serialization with only repository, revision, file, and symbol fields.
- [x] 2.6 Preserve `ConfluencePageRef` serialization with only page_id.

## 3. Pipeline and Script Integration

- [x] 3.1 Extend the reusable pipeline function to accept optional persistence configuration.
- [x] 3.2 Execute the LadybugDB persistence stage after graph-producing stages when persistence is configured.
- [x] 3.3 Preserve the existing empty bootstrap behavior when no registry path or persistence path is provided.
- [x] 3.4 Preserve the existing workspace-registry-only behavior when a registry path is provided without persistence configuration.
- [x] 3.5 Update `scripts/build.py` to pass optional persistence configuration through to the reusable pipeline function without adding persistence business logic to the script.
- [x] 3.6 Report configured and executed stages deterministically, including workspace-registry before LadybugDB persistence when both run.

## 4. Tests

- [x] 4.1 Add tests for empty local store initialization and empty `GraphSnapshot` readback.
- [x] 4.2 Add tests for persisting and reading back a workspace registry graph snapshot.
- [x] 4.3 Add tests proving repeated writes of the same graph snapshot do not duplicate nodes, edges, or evidence.
- [x] 4.4 Add tests for evidence persistence with string locators, `CodeLocator`, and `ConfluencePageRef`.
- [x] 4.5 Add tests proving persisted/readback serialization does not contain source code, call graphs, dependency graphs, class bodies, function bodies, fetched page content, credentials, tokens, or external API response payloads.
- [x] 4.6 Add tests for explicit failure reporting on invalid or unwritable persistence paths.
- [x] 4.7 Add pipeline tests for registry plus persistence execution and deterministic stage ordering.
- [x] 4.8 Add script wrapper tests for registry plus persistence path invocation.
- [x] 4.9 Re-run existing bootstrap and workspace-registry tests to verify non-persistent behavior remains unchanged.

## 5. Validation

- [x] 5.1 Run the project test suite.
- [x] 5.2 Run `openspec validate add-ladybugdb-persistence-foundation`.
- [x] 5.3 Review implementation against proposal, design, and specs before marking tasks complete.
