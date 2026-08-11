## 1. OpenLore Source Validation Model

- [x] 1.1 Add reusable OpenLore source validation result data structures with deterministic serialization.
- [x] 1.2 Implement validation against the loaded `WorkspaceRegistry` using resolved workspace OpenLore path, federation settings, freshness policy, and federation repositories.
- [x] 1.3 Reject successful validation when an included federation repository has an empty OpenLore index reference.
- [x] 1.4 Ensure validation output excludes source code, call graph, dependency graph, symbol bodies, architecture analysis, impact analysis, credentials, tokens, and API responses.

## 2. Fixtures And Unit Tests

- [x] 2.1 Add a valid fixture whose pipeline stages include `workspace-registry` and `workspace-openlore-source`.
- [x] 2.2 Add invalid fixture coverage for an included federation repository with a missing OpenLore index reference.
- [x] 2.3 Add tests proving workspace OpenLore source paths resolve deterministically from explicit and default layout configuration.
- [x] 2.4 Add tests proving validation accepts generated OpenLore state outside repository roots and rejects repository-contained OpenLore source paths.
- [x] 2.5 Add tests proving federation-disabled registries do not require per-repository OpenLore index references and report zero federation repositories.
- [x] 2.6 Add tests proving repeated validation of the same registry returns identical serialized output.

## 3. Pipeline Runner Integration

- [x] 3.1 Extend `PipelineResult` to carry deterministic workspace OpenLore source validation metadata when the stage executes.
- [x] 3.2 Execute `workspace-openlore-source` after `workspace-registry` when both stages are configured.
- [x] 3.3 Preserve existing bootstrap, registry-only, persistence-only, and registry-plus-persistence behavior when the OpenLore validation stage is not configured.
- [x] 3.4 Ensure the OpenLore validation stage preserves the registry-produced canonical graph snapshot without adding OpenLore code graph contents.

## 4. Script Wrapper Verification

- [x] 4.1 Add script-level test coverage for a registry that configures `workspace-openlore-source`.
- [x] 4.2 Verify script output reports configured stages, executed stages, graph counts, and OpenLore validation metadata through the reusable pipeline function.
- [x] 4.3 Verify script execution remains local-first and does not require network access, API keys, external MCP servers, compilation, publishing, or generated documentation.

## 5. Validation

- [x] 5.1 Run the focused workspace OpenLore source validation tests.
- [x] 5.2 Run the focused pipeline runner tests.
- [x] 5.3 Run `openspec validate validate-workspace-openlore-source --strict`.
