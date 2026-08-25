"""MCP startup graph-store resolution for Engineering KG."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from engineering_kg.ingest.openspec import RegisteredOpenSpecStore, parse_registered_openspec_stores
from engineering_kg.project import WorkspaceRegistry, load_workspace_registry


class McpStartupResolutionError(RuntimeError):
    """Raised when MCP startup cannot resolve a local graph store."""


@dataclass(frozen=True)
class McpStartupOptions:
    """Explicit startup inputs for Engineering KG MCP."""

    graph_store: str | Path | None = None
    registry: str | Path | None = None
    openspec_store: str | None = None
    cwd: str | Path | None = None
    openspec_command: str | Path | None = None
    git_command: str | Path | None = None


@dataclass(frozen=True)
class OpenSpecProjectContext:
    """OpenSpec project context relevant to MCP startup."""

    store_id: str = ""
    root_path: Path | None = None


@dataclass(frozen=True)
class McpGraphStoreResolution:
    """Resolved graph store and supporting startup metadata."""

    graph_store_path: Path
    source: str
    registry_path: Path | None = None
    openspec_store_id: str = ""
    openspec_store_path: Path | None = None


OpenSpecContextResolver = Callable[[Path, Path], OpenSpecProjectContext]
GitRootResolver = Callable[[Path, Path], Path]
RegistryLoader = Callable[[str | Path], WorkspaceRegistry]
StoreDiscovery = Callable[[], Iterable[RegisteredOpenSpecStore | dict[str, Any]]]


def resolve_mcp_graph_store(
    options: McpStartupOptions,
    *,
    openspec_context_resolver: OpenSpecContextResolver | None = None,
    store_discovery: StoreDiscovery | None = None,
    registry_loader: RegistryLoader = load_workspace_registry,
    git_root_resolver: GitRootResolver | None = None,
) -> McpGraphStoreResolution:
    """Resolve the graph store once before MCP tools are exposed."""

    cwd = Path(options.cwd or Path.cwd()).expanduser().resolve()
    if options.graph_store is not None:
        return McpGraphStoreResolution(
            graph_store_path=Path(options.graph_store).expanduser().resolve(),
            source="graph-store-override",
        )

    if options.registry is not None:
        registry = _load_registry(registry_loader, options.registry)
        return _resolution_from_registry(registry, source="registry-override")

    discovery = store_discovery or (
        lambda: discover_registered_openspec_stores_for_mcp(
            _require_absolute_command(options.openspec_command, "OpenSpec", "--openspec-command")
        )
    )
    if options.openspec_store:
        store = _select_store(discovery(), options.openspec_store)
        return _resolution_from_store(
            store,
            registry_loader=registry_loader,
            source="openspec-store-override",
        )

    context_resolver = openspec_context_resolver or resolve_openspec_project_context
    openspec_command = _require_absolute_command(
        options.openspec_command,
        "OpenSpec",
        "--openspec-command",
    )
    context = context_resolver(cwd, openspec_command)
    if not context.store_id and context.root_path is None:
        raise McpStartupResolutionError(
            "OpenSpec project context could not be resolved from the current working directory. "
            "Configure openspec/config.yaml with store: <id>, register the store, use "
            "--openspec-store, or use --registry."
        )

    if context.store_id:
        store = _select_store(discovery(), context.store_id)
        resolution = _resolution_from_store(
            store,
            registry_loader=registry_loader,
            source="openspec-project-context",
        )
    else:
        store_path = _expect_context_root(context)
        resolution = _resolution_from_store_path(
            store_path,
            registry_loader=registry_loader,
            source="openspec-project-context",
        )

    git_resolver = git_root_resolver or resolve_current_git_root
    git_command = _require_absolute_command(options.git_command, "Git", "--git-command")
    current_repo = git_resolver(cwd, git_command).resolve()
    registry = _load_registry(registry_loader, _expect_registry_path(resolution))
    _require_current_repository_member(current_repo, registry)
    return resolution


def discover_registered_openspec_stores_for_mcp(
    openspec_command: str | Path,
) -> tuple[RegisteredOpenSpecStore, ...]:
    """Read registered OpenSpec stores through an explicit OpenSpec command."""

    command = _require_absolute_command(openspec_command, "OpenSpec", "--openspec-command")
    try:
        completed = subprocess.run(
            [str(command), "store", "list", "--json"],
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise McpStartupResolutionError("Registered OpenSpec stores could not be discovered") from exc

    try:
        return parse_registered_openspec_stores(json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise McpStartupResolutionError("OpenSpec store discovery output is not valid JSON") from exc


def resolve_openspec_project_context(
    cwd: str | Path,
    openspec_command: str | Path,
) -> OpenSpecProjectContext:
    """Resolve project-associated OpenSpec context through the OpenSpec CLI."""

    command = _require_absolute_command(openspec_command, "OpenSpec", "--openspec-command")
    try:
        completed = subprocess.run(
            [str(command), "context", "--json"],
            cwd=Path(cwd),
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise McpStartupResolutionError(
            "OpenSpec project context could not be resolved from the current working directory. "
            "Configure openspec/config.yaml with store: <id>, register the store, use "
            "--openspec-store, or use --registry."
        ) from exc

    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise McpStartupResolutionError("OpenSpec context output is not valid JSON") from exc

    store_id = _find_store_id(raw)
    root_path = _find_root_path(raw)
    return OpenSpecProjectContext(store_id=store_id, root_path=root_path)


def resolve_current_git_root(cwd: str | Path, git_command: str | Path) -> Path:
    """Resolve the current Git repository root without shell dependencies."""

    command = _require_absolute_command(git_command, "Git", "--git-command")
    try:
        completed = subprocess.run(
            [str(command), "rev-parse", "--show-toplevel"],
            cwd=Path(cwd),
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise McpStartupResolutionError(
            "Current Git repository root could not be resolved for automatic MCP startup. "
            "Use --graph-store or --registry for explicit startup."
        ) from exc
    return Path(completed.stdout.strip()).expanduser().resolve()


def _require_absolute_command(
    command: str | Path | None,
    label: str,
    option_name: str,
) -> Path:
    if command is None:
        raise McpStartupResolutionError(
            f"{label} command path is required for this MCP startup mode. "
            f"Pass {option_name} with an absolute executable path."
        )
    path = Path(command).expanduser()
    if not path.is_absolute():
        raise McpStartupResolutionError(
            f"{label} command path must be absolute for MCP startup: {command}"
        )
    return path


def _resolution_from_store(
    store: RegisteredOpenSpecStore,
    *,
    registry_loader: RegistryLoader,
    source: str,
) -> McpGraphStoreResolution:
    return _resolution_from_store_path(
        store.path,
        registry_loader=registry_loader,
        source=source,
        openspec_store_id=store.id,
    )


def _resolution_from_store_path(
    store_path: Path,
    *,
    registry_loader: RegistryLoader,
    source: str,
    openspec_store_id: str = "",
) -> McpGraphStoreResolution:
    registry_path = store_path.expanduser().resolve() / "repo-index.yaml"
    if not registry_path.is_file():
        raise McpStartupResolutionError(f"Workspace registry is missing: {registry_path}")
    registry = _load_registry(registry_loader, registry_path)
    return _resolution_from_registry(
        registry,
        source=source,
        openspec_store_id=openspec_store_id,
        openspec_store_path=store_path.expanduser().resolve(),
    )


def _resolution_from_registry(
    registry: WorkspaceRegistry,
    *,
    source: str,
    openspec_store_id: str = "",
    openspec_store_path: Path | None = None,
) -> McpGraphStoreResolution:
    graph_store_path = registry.layout.resolved_graph_store_path
    if not graph_store_path:
        raise McpStartupResolutionError("Workspace registry does not resolve a graph store path")
    return McpGraphStoreResolution(
        graph_store_path=graph_store_path,
        source=source,
        registry_path=registry.source_path,
        openspec_store_id=openspec_store_id,
        openspec_store_path=openspec_store_path,
    )


def _load_registry(loader: RegistryLoader, path: str | Path) -> WorkspaceRegistry:
    try:
        return loader(path)
    except Exception as exc:
        if isinstance(exc, McpStartupResolutionError):
            raise
        raise McpStartupResolutionError(f"Workspace registry could not be loaded: {Path(path)}") from exc


def _select_store(
    stores: Iterable[RegisteredOpenSpecStore | dict[str, Any]],
    store_id: str,
) -> RegisteredOpenSpecStore:
    normalized = [_normalize_store(item) for item in stores]
    for store in normalized:
        if store.id == store_id:
            return store
    raise McpStartupResolutionError(f"Registered OpenSpec store id was not found: {store_id}")


def _normalize_store(item: RegisteredOpenSpecStore | dict[str, Any]) -> RegisteredOpenSpecStore:
    if isinstance(item, RegisteredOpenSpecStore):
        return item
    raw_id = item.get("id") or item.get("name") or item.get("key")
    raw_path = item.get("path") or item.get("root") or item.get("directory")
    if not isinstance(raw_id, str) or not raw_id:
        raise McpStartupResolutionError("OpenSpec store discovery returned a store without an id")
    if not isinstance(raw_path, str) or not raw_path:
        raise McpStartupResolutionError(f"OpenSpec store discovery returned no path for store id: {raw_id}")
    return RegisteredOpenSpecStore(id=raw_id, path=Path(raw_path).expanduser().resolve())


def _require_current_repository_member(current_repo: Path, registry: WorkspaceRegistry) -> None:
    registered_paths = {repo.resolved_path.resolve() for repo in registry.repositories}
    if current_repo not in registered_paths:
        raise McpStartupResolutionError(
            "Current repository is not part of the selected Engineering workspace: "
            f"{current_repo}"
        )


def _expect_context_root(context: OpenSpecProjectContext) -> Path:
    if context.root_path is None:
        raise McpStartupResolutionError(
            "OpenSpec project context did not include a store path. Use --openspec-store or --registry."
        )
    return context.root_path


def _expect_registry_path(resolution: McpGraphStoreResolution) -> Path:
    if resolution.registry_path is None:
        raise McpStartupResolutionError("Workspace registry path was not resolved")
    return resolution.registry_path


def _find_store_id(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ""
    candidates = (
        raw.get("store"),
        raw.get("storeId"),
        raw.get("store_id"),
        raw.get("openspecStore"),
        raw.get("openspec_store"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, dict):
            value = candidate.get("id") or candidate.get("name")
            if isinstance(value, str) and value:
                return value
    return ""


def _find_root_path(raw: Any) -> Path | None:
    if not isinstance(raw, dict):
        return None
    root = raw.get("root")
    if isinstance(root, dict):
        path = root.get("path")
        if isinstance(path, str) and path:
            return Path(path).expanduser().resolve()
    path = raw.get("rootPath") or raw.get("root_path") or raw.get("path")
    if isinstance(path, str) and path:
        return Path(path).expanduser().resolve()
    return None
