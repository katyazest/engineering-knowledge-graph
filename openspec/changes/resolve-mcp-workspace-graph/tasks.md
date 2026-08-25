## 1. Resolver Tests

- [x] 1.1 Add deterministic unit tests for `--graph-store`, `--registry`, `--openspec-store`, and automatic OpenSpec project resolution precedence.
- [x] 1.2 Add unit tests for actionable startup failures when OpenSpec project context, registered store ids, `repo-index.yaml`, graph store path, or current repository membership cannot be resolved.
- [x] 1.3 Add tests proving automatic startup accepts only current Git repositories listed in `WorkspaceRegistry.repositories[*].resolved_path`.

## 2. Startup Resolver Implementation

- [x] 2.1 Implement an injectable MCP workspace resolver that accepts explicit startup options and OpenSpec/store discovery adapters.
- [x] 2.2 Load explicit registry or selected OpenSpec store `repo-index.yaml` through the existing workspace registry loader and return `WorkspaceRegistry.layout.resolved_graph_store_path`.
- [x] 2.3 Implement automatic OpenSpec project store resolution from current working directory without sibling-directory, nearest-registry, or arbitrary-store fallback.
- [x] 2.4 Implement current Git repository membership validation for automatic resolution and bypass it for explicit `--graph-store`.
- [x] 2.5 Normalize resolver errors so failures are local, actionable, and do not print secrets or sensitive payloads.

## 3. MCP CLI and Query Wrappers

- [x] 3.1 Add an `engineering-kg mcp` CLI command with `--graph-store`, `--registry`, and `--openspec-store` options using the resolver precedence.
- [x] 3.2 Update FactMCP/FastMCP server creation so query tools bind one resolved graph store before tool registration.
- [x] 3.3 Remove per-tool `graph_store` parameters from `list_requirements`, `list_services`, `list_changes`, and `get_traceability` MCP tool schemas.
- [x] 3.4 Keep startup behavior host-independent and avoid shell, alias, implicit `PATH`, network, external MCP, graph rebuild, and LLM dependencies.

## 4. Documentation and Validation

- [x] 4.1 Update README or user documentation for `engineering-kg mcp`, override precedence, OpenSpec store configuration, and startup failure remediation.
- [x] 4.2 Add a simple Gigacode-oriented MCP configuration example that uses command and argument arrays without shell substitutions or one-liners.
- [x] 4.3 Run focused unit tests for resolver, CLI startup, MCP wrapper schemas, and any affected query paths.
- [x] 4.4 Run `openspec validate "resolve-mcp-workspace-graph" --type change` and fix any artifact or spec validation issues.
