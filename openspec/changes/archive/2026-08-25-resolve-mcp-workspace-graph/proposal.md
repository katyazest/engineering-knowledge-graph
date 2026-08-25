## Why

Engineering KG MCP should be usable from a requirements repository or a configured code repository without requiring the agent to know local graph storage paths. The current MCP wrapper exposes graph store selection too late, inside tool calls, which makes the model responsible for workspace storage details that should be resolved once at MCP startup.

## What Changes

- Add MCP startup resolution that uses the current project's OpenSpec store association as the discovery anchor.
- Support explicit CLI overrides with unambiguous names: `--graph-store`, `--registry`, and `--openspec-store`.
- Resolve `repo-index.yaml` from the selected OpenSpec store, then use the loaded `WorkspaceRegistry` as the authoritative source for the Engineering KG graph store path.
- Validate during automatic resolution that the current Git repository is represented in `WorkspaceRegistry.repositories[*].resolved_path`.
- Add an `engineering-kg mcp` command that starts the FactMCP/FastMCP server with one fixed graph store.
- **BREAKING** Remove per-tool `graph_store` override parameters from MCP query tool schemas; graph store override remains available only at MCP startup through `--graph-store`.
- Make startup behavior independent of whether the MCP host is Gigacode, Codex, Claude Desktop, or another CLI agent; startup configuration remains host-specific.
- Treat Gigacode as the primary constrained enterprise host and avoid assumptions that only work in a permissive CLI environment.
- Require MCP startup to avoid Codex-specific behavior, `AGENTS.md`, interactive shell environment, aliases, or implicit `PATH`.
- Recommend MCP host configuration that passes simple command and argument arrays without shell substitutions or complex one-liners.
- Require startup failure to return an actionable error when OpenSpec project context cannot be resolved from the current working directory, including guidance to configure `openspec/config.yaml`, use `--openspec-store`, or use `--registry`.
- Preserve local-first behavior without cloud services, external APIs, OpenLore MCP, Jira MCP, Bitbucket MCP, Confluence, semantic extraction, graph rebuilding, or LLM services during MCP startup.
- Prohibit startup from using web fetchers, `curl`, `wget`, browser fetchers, ad hoc HTTP, secrets, or external network access.
- Ensure the graph store path is resolved before MCP tools are exposed and does not appear as an MCP tool parameter.

## Capabilities

### New Capabilities
- `mcp-startup-resolution`: Resolves the Engineering workspace and graph store for MCP startup from explicit CLI overrides, OpenSpec project store association, registered OpenSpec store paths, and `repo-index.yaml`.

### Modified Capabilities
- `ekg-mcp-query-wrappers`: MCP tools use a server-level graph store resolved at startup and no longer expose `graph_store` arguments in tool schemas.

## Impact

- Affected code: CLI entry point/module, MCP startup code, OpenSpec store/context resolution boundary, workspace registry loading, current-repository membership guardrail, and FactMCP/FastMCP query wrappers.
- Affected tests: new resolver tests with injectable OpenSpec context/store discovery, CLI startup tests, current-repository membership guardrail tests, and wrapper schema tests for removal of `graph_store`.
- Affected docs: README and user documentation for `engineering-kg mcp`, override precedence, OpenSpec store configuration, and actionable startup errors.
- Affected enterprise usage: Gigacode MCP configuration examples should use explicit, simple command/argument configuration and should not rely on shell conveniences or Codex-only behavior.
- Dependencies remain local; no credentials, network access, generated graph rebuild, or external MCP calls are introduced.
