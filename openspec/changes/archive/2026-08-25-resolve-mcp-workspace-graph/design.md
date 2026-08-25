## Context

Engineering KG already has a reusable local query API and thin FactMCP/FastMCP wrappers, but the current MCP wrapper still allows graph store selection inside individual tool calls. That makes the LLM responsible for a local storage path and weakens the intended semantics that one MCP server process represents one Engineering workspace.

The workspace topology and generated graph location already live in `repo-index.yaml` through `WorkspaceRegistry`. In the enterprise workflow, `repo-index.yaml` is stored in the OpenSpec store repository, and OpenSpec already resolves the project-associated store from the current project context, including code repositories that declare `openspec/config.yaml` with `store: <id>`. Engineering KG should reuse that OpenSpec resolution boundary instead of implementing separate filesystem discovery.

Gigacode is the primary constrained host for this startup path. The design must avoid Codex-only assumptions, interactive shell behavior, aliases, implicit `PATH`, web fetchers, ad hoc HTTP, credentials, external network access, and complex shell one-liners in MCP configuration examples.

## Goals / Non-Goals

**Goals:**

- Provide `engineering-kg mcp` as the normal startup path for the MCP server.
- Resolve the Engineering workspace through the current project's OpenSpec store association.
- Use explicit startup override precedence: `--graph-store`, then `--registry`, then `--openspec-store`, then OpenSpec project resolution from current working directory.
- Load `repo-index.yaml` from the selected OpenSpec store or explicit registry path.
- Use `WorkspaceRegistry.layout.resolved_graph_store_path` as the default graph store for MCP tools.
- Verify during automatic resolution that the current Git repository belongs to the loaded workspace registry.
- Remove graph store path selection from MCP tool schemas.
- Keep resolver dependencies injectable for deterministic unit tests.

**Non-Goals:**

- Do not rebuild, refresh, derive, validate, or persist the graph during MCP startup.
- Do not query OpenLore MCP, Jira MCP, Bitbucket MCP, Confluence, cloud services, external APIs, or LLM services.
- Do not infer workspace layout from sibling directories, nearest `.engineering-kg`, nearest requirements repository, or an arbitrary registered store.
- Do not make the MCP startup path depend on a specific host such as Codex, Gigacode, Claude Desktop, or another agent.
- Do not store secrets, tokens, credentials, source payloads, OpenLore analysis bodies, Jira payloads, Bitbucket payloads, or generated graph records in startup metadata.

## Decisions

### Decision: Resolve the workspace through OpenSpec project context

`engineering-kg mcp` without explicit overrides should ask the OpenSpec boundary to resolve the store associated with the current project. The current working directory is only an input to OpenSpec project resolution; Engineering KG must not use it to infer workspace layout directly.

Alternative considered: list registered OpenSpec stores and select the only available store. That is unsafe on enterprise machines with multiple projects and also bypasses the project-level `openspec/config.yaml` association that OpenSpec already owns.

Alternative considered: walk up or across sibling directories looking for `repo-index.yaml`. That duplicates workspace discovery outside OpenSpec and can attach the MCP server to the wrong project.

### Decision: Keep startup overrides explicit and unambiguous

The CLI should use three distinct flags:

- `--graph-store` for low-level debug or CI startup from a known LadybugDB-compatible store.
- `--registry` for startup from a known `repo-index.yaml`.
- `--openspec-store` for startup from a known OpenSpec store id.

The precedence is:

```text
--graph-store
--registry
--openspec-store
OpenSpec project store resolution from cwd
error
```

This avoids overloading `--store`, which could mean either an OpenSpec store or an Engineering KG graph store.

Alternative considered: keep a generic `--store`. That creates avoidable ambiguity in a system with both OpenSpec stores and graph stores.

### Decision: Treat `repo-index.yaml` as the workspace authority after OpenSpec selection

Once the OpenSpec store path is selected, Engineering KG should load `<store path>/repo-index.yaml` through the existing workspace registry loader. From that point, `WorkspaceRegistry` is authoritative for workspace layout and graph store path resolution, especially `registry.layout.resolved_graph_store_path`.

Alternative considered: pass the selected OpenSpec store path directly to query APIs. That confuses the requirements repository with generated Engineering KG storage and bypasses existing registry validation.

### Decision: Validate current repository membership for automatic resolution

When startup uses automatic OpenSpec project resolution from the current working directory, Engineering KG should resolve the current Git repository root and verify that it matches one of `WorkspaceRegistry.repositories[*].resolved_path`. If the repository is not part of the registry, startup should fail with an actionable error.

This prevents accidental attachment to a different workspace when several OpenSpec stores are registered on the same machine.

Alternative considered: trust the resolved OpenSpec store without checking membership. That is simpler, but it makes misconfigured project context harder to detect and risks returning facts from the wrong Engineering workspace.

### Decision: Bind graph store once before registering tools

The MCP server should resolve the graph store path before exposing tools. Query tools should close over that server-level store and omit `graph_store` parameters from their signatures.

Alternative considered: keep per-tool `graph_store` overrides. That supports ad hoc debugging, but it leaks local filesystem details into the LLM tool schema and lets the model select a storage path. Debugging remains available through `engineering-kg mcp --graph-store`.

### Decision: Make OpenSpec resolution and store discovery injectable

The resolver should isolate interactions with OpenSpec CLI/configuration behind a small dependency boundary. Unit tests can inject project resolution results and registered store records instead of depending on machine-local OpenSpec state.

Alternative considered: call the OpenSpec CLI directly throughout startup code. That would be harder to test deterministically and would make empty or differently configured developer machines produce noisy failures.

### Decision: Keep Gigacode configuration simple and host-specific

The MCP startup behavior should be host-independent, but each host's MCP configuration is host-specific. Gigacode examples should pass a simple command and argument list, avoid shell substitutions and complex one-liners, and avoid assumptions about interactive shell environment, aliases, or implicit `PATH`.

Alternative considered: document shell-based startup snippets. That is fragile in Gigacode because enterprise policy and shell restrictions may reject advanced shell syntax or fail to inherit the user's interactive environment.

## Risks / Trade-offs

- OpenSpec project resolution behavior may not have a stable Python API -> keep it behind an adapter and allow a narrow CLI subprocess implementation if that is the only available local interface.
- The current development machine may have no registered OpenSpec stores -> use injected resolver data in unit tests and return a clear runtime error instead of falling back to filesystem guessing.
- Current Git repository detection can fail outside a Git checkout -> fail only for automatic project resolution where membership guardrail is required; explicit `--registry` and `--graph-store` remain available for CI/debug use.
- Removing `graph_store` from tool schemas is a breaking MCP contract change -> document the startup-level `--graph-store` replacement and update wrapper tests.
- Gigacode may require absolute executable paths in MCP configuration -> document simple host-specific configuration without baking local absolute paths into reusable project behavior.
